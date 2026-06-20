import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic_ai.capabilities.process_history import ProcessHistory
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    RetryPromptPart,
    SystemPromptPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.run import AgentRunResult
from pydantic_ai.ui.ag_ui import AGUIAdapter

from app.core.config import get_settings
from app.core.llm_provider import chat_provider_is_configured, resolve_chat_provider
from app.notebooks.agent import (
    NotebookChatDeps,
    notebook_chat_agent,
)
from app.notebooks.events import (
    build_document_snapshots,
    build_report_snapshots,
    event_bus,
)
from app.notebooks.memory import (
    append_notebook_chat_history,
    extract_notebook_chat_transcript,
    load_notebook_chat_history,
)
from app.notebooks.models import (
    NotebookDocument,
    NotebookDocumentChunk,
    NotebookReport,
)
from app.notebooks.rag.ingestion_service import ingest_document_by_id
from app.notebooks.schemas import (
    NotebookChatHistoryMessage,
    NotebookCreate,
    NotebookDocumentRead,
    NotebookPopulateRead,
    NotebookRead,
    NotebookReportRead,
    NotebookUpdate,
    NoteCreate,
    ReportGenerateRequest,
)
from app.notebooks.service import (
    build_report_context,
    create_notebook,
    delete_notebook,
    delete_notebook_document,
    get_notebook,
    list_notebook_documents,
    list_notebooks,
    populate_notebook_metrics,
    run_report_generation,
    touch_notebook,
    update_notebook,
)
from app.users.dependencies import get_current_user
from app.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notebooks", tags=["Notebooks"])

# Idle interval between SSE keep-alive comments on the events stream.
SSE_PING_SECONDS = 30.0


@router.get("/", response_model=list[NotebookRead])
async def read_notebooks(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list:
    return await list_notebooks(current_user)


@router.post("/", response_model=NotebookRead, status_code=status.HTTP_201_CREATED)
async def create_notebook_route(
    payload: NotebookCreate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> object:
    return await create_notebook(payload, current_user)


@router.get("/events")
async def read_notebook_events(
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    async def event_generator() -> AsyncIterator[str]:
        documents = await NotebookDocument.find({"user_id": current_user.id}).to_list()
        reports = await NotebookReport.find({"user_id": current_user.id}).to_list()

        # Replay current state so a (re)connecting client is immediately in sync.
        for event in (
            *build_document_snapshots(documents),
            *build_report_snapshots(reports),
        ):
            yield f"data: {json.dumps(event)}\n\n"

        async with event_bus.subscribe(current_user.id) as queue:
            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=SSE_PING_SECONDS
                    )
                    yield f"data: {json.dumps(event)}\n\n"
                except TimeoutError:
                    yield ": ping\n\n"  # keep-alive comment; ignored by EventSource

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/{notebook_id}", response_model=NotebookRead)
async def read_notebook(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> object:
    return await get_notebook(notebook_id, current_user)


@router.patch("/{notebook_id}", response_model=NotebookRead)
async def update_notebook_route(
    notebook_id: UUID,
    payload: NotebookUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> object:
    return await update_notebook(notebook_id, payload, current_user)


@router.post("/{notebook_id}/touch", response_model=NotebookRead)
async def touch_notebook_route(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> object:
    return await touch_notebook(notebook_id, current_user)


@router.get("/{notebook_id}/populate", response_model=NotebookPopulateRead)
async def populate_notebook_route(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> object:
    return await populate_notebook_metrics(notebook_id, current_user)


@router.get("/{notebook_id}/documents", response_model=list[NotebookDocumentRead])
async def read_notebook_documents(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> list:
    return await list_notebook_documents(notebook_id, current_user)


def _run_background_note_ingestion(
    document_id: UUID,
) -> None:
    settings = get_settings()
    try:
        asyncio.run(ingest_document_by_id(document_id, settings))
    except Exception:
        logger.exception(
            "Background note ingestion failed for document %s", document_id
        )


@router.delete(
    "/{notebook_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_notebook_document_route(
    notebook_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    await delete_notebook_document(notebook_id, document_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{notebook_id}/notes",
    response_model=NotebookDocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_notebook_note(
    notebook_id: UUID,
    payload: NoteCreate,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
) -> object:
    notebook = await get_notebook(notebook_id, current_user)

    filename = payload.title.strip()
    if not filename.endswith(".txt") and not filename.endswith(".md"):
        filename += ".txt"

    now = datetime.now(UTC)
    doc_id = uuid4()
    document = NotebookDocument(
        id=doc_id,
        notebook_id=notebook.id,
        user_id=current_user.id,
        s3_bucket=None,
        s3_key=f"db-notes/{doc_id}",
        filename=filename,
        content_type="text/plain",
        size=len(payload.content.encode("utf-8")),
        status="uploaded",
        content=payload.content,
        created_at=now,
        updated_at=now,
    )

    report = NotebookReport(
        notebook_id=notebook.id,
        user_id=current_user.id,
        report_type="note",
        status="completed",
        content={
            "title": payload.title,
            "content": payload.content,
            "document_id": str(doc_id),
        },
        created_at=now,
        updated_at=now,
    )

    await document.insert()
    await report.insert()

    background_tasks.add_task(
        _run_background_note_ingestion,
        document_id=document.id,
    )

    return document


@router.post("/{notebook_id}/chat")
async def chat_notebook_route(
    notebook_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    notebook = await get_notebook(notebook_id, current_user)
    message_history = await load_notebook_chat_history(notebook)
    settings = get_settings()

    deps = NotebookChatDeps(
        notebook=notebook,
        current_user=current_user,
        settings=settings,
    )

    async def persist_chat_history(result: AgentRunResult[object]) -> None:
        all_new = result.all_messages()[len(message_history) :]
        await append_notebook_chat_history(notebook, all_new)

    async def keep_recent(messages: list[ModelMessage]) -> list[ModelMessage]:
        system_prompts = []
        other_messages = []
        for msg in messages:
            is_system = False
            if isinstance(msg, ModelRequest):
                has_system_part = any(
                    isinstance(part, SystemPromptPart) for part in msg.parts
                )
                has_conversational_part = any(
                    isinstance(part, (UserPromptPart, ToolReturnPart, RetryPromptPart))
                    for part in msg.parts
                )
                if has_system_part or (
                    msg.instructions and not has_conversational_part
                ):
                    is_system = True

            if is_system:
                system_prompts.append(msg)
            else:
                other_messages.append(msg)

        recent_limit = 15
        recent_others = (
            other_messages[-recent_limit:]
            if len(other_messages) > recent_limit
            else other_messages
        )

        keep_set = {id(msg) for msg in system_prompts} | {
            id(msg) for msg in recent_others
        }
        return [msg for msg in messages if id(msg) in keep_set]

    return await AGUIAdapter.dispatch_request(
        request,
        agent=notebook_chat_agent,
        model=resolve_chat_provider(),
        deps=deps,
        message_history=message_history,
        conversation_id=str(notebook.id),
        on_complete=persist_chat_history,
        capabilities=[ProcessHistory(keep_recent)],
    )


@router.get(
    "/{notebook_id}/chat/history", response_model=list[NotebookChatHistoryMessage]
)
async def read_notebook_chat_history(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    include_reasoning: bool = False,
) -> list[dict[str, object]]:
    notebook = await get_notebook(notebook_id, current_user)
    return await extract_notebook_chat_transcript(
        notebook, include_reasoning=include_reasoning
    )


@router.get("/{notebook_id}/documents/chunks", response_model=list[dict[str, object]])
async def read_document_chunks(
    notebook_id: UUID,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> list:
    notebook = await get_notebook(notebook_id, current_user)
    document = await NotebookDocument.find_one(
        {"notebook_id": notebook.id, "filename": filename, "user_id": current_user.id},
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    chunks = (
        await NotebookDocumentChunk.find({"document_id": document.id})
        .sort(("chunk_index", 1))
        .to_list()
    )

    return [
        {
            "id": str(c.id),
            "document_id": str(c.document_id),
            "chunk_index": c.chunk_index,
            "content": c.content,
            "metadata": c.chunk_metadata,
        }
        for c in chunks
    ]


@router.get(
    "/{notebook_id}/documents/{document_id}/chunks",
    response_model=list[dict[str, object]],
)
async def read_document_chunks_by_id(
    notebook_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict[str, object]]:
    notebook = await get_notebook(notebook_id, current_user)
    document = await NotebookDocument.find_one(
        {"_id": document_id, "notebook_id": notebook.id, "user_id": current_user.id},
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    chunks = (
        await NotebookDocumentChunk.find({"document_id": document.id})
        .sort(("chunk_index", 1))
        .to_list()
    )

    return [
        {
            "id": str(c.id),
            "document_id": str(c.document_id),
            "chunk_index": c.chunk_index,
            "content": c.content,
            "metadata": c.chunk_metadata,
        }
        for c in chunks
    ]


@router.get("/{notebook_id}/documents/{document_id}/chunks/{chunk_index}")
async def read_single_chunk(
    notebook_id: UUID,
    document_id: UUID,
    chunk_index: int,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    notebook = await get_notebook(notebook_id, current_user)
    document = await NotebookDocument.find_one(
        {"_id": document_id, "notebook_id": notebook.id, "user_id": current_user.id},
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    chunk = await NotebookDocumentChunk.find_one(
        {"document_id": document.id, "chunk_index": chunk_index},
    )
    if not chunk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found"
        )

    return {
        "id": str(chunk.id),
        "document_id": str(chunk.document_id),
        "filename": document.filename,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "metadata": chunk.chunk_metadata,
    }


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notebook_route(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    await delete_notebook(notebook_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{notebook_id}/reports",
    response_model=NotebookReportRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_notebook_report(
    notebook_id: UUID,
    payload: ReportGenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
) -> object:
    notebook = await get_notebook(notebook_id, current_user)

    if not chat_provider_is_configured():
        provider = get_settings().chat_provider.strip().lower()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service is not configured. Set the API key for the '{provider}' chat provider.",
        )

    context = await build_report_context(notebook, current_user)
    if not context:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No indexed documents found in this notebook. Upload and wait for indexing to complete.",
        )

    instructions = (payload.additional_instructions or "").strip() or None
    if payload.report_type == "custom" and not instructions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="additional_instructions is required for report_type 'custom'.",
        )

    question_count: int | None = None
    if payload.report_type == "quiz":
        question_count = {"fewer": 10, "standard": 20, "more": 30}.get(
            (payload.number_of_questions or "standard").strip().lower(), 20
        )
    elif payload.report_type == "flashcards":
        question_count = {"fewer": 10, "standard": 20, "more": 30}.get(
            (payload.number_of_cards or "standard").strip().lower(), 20
        )

    now = datetime.now(UTC)
    report = NotebookReport(
        notebook_id=notebook.id,
        user_id=current_user.id,
        report_type=payload.report_type,
        status="pending",
        additional_instructions=instructions,
        detail_level=payload.detail_level,
        content={},
        created_at=now,
        updated_at=now,
    )
    await report.insert()

    background_tasks.add_task(
        run_report_generation,
        report_id=report.id,
        report_type=payload.report_type,
        context=context,
        instructions=instructions,
        detail_level=payload.detail_level,
        question_count=question_count,
    )

    return report


@router.post(
    "/{notebook_id}/reports/{report_id}/cancel",
    response_model=NotebookReportRead,
)
async def cancel_notebook_report(
    notebook_id: UUID,
    report_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> object:
    notebook = await get_notebook(notebook_id, current_user)
    report = await NotebookReport.find_one(
        {"_id": report_id, "notebook_id": notebook.id, "user_id": current_user.id},
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )

    if report.status not in ("pending", "generating"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel report with status '{report.status}'.",
        )

    report.status = "cancelled"
    report.updated_at = datetime.now(UTC)
    await report.save()
    return report


@router.delete(
    "/{notebook_id}/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_notebook_report(
    notebook_id: UUID,
    report_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    notebook = await get_notebook(notebook_id, current_user)
    report = await NotebookReport.find_one(
        {"_id": report_id, "notebook_id": notebook.id, "user_id": current_user.id},
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )

    if report.report_type == "note" and isinstance(report.content, dict):
        doc_id_str = report.content.get("document_id")
        if doc_id_str:
            try:
                doc_id = UUID(doc_id_str)
                document = await NotebookDocument.find_one(
                    {
                        "_id": doc_id,
                        "notebook_id": notebook.id,
                        "user_id": current_user.id,
                    },
                )
                if document:
                    await NotebookDocumentChunk.find(
                        {"document_id": document.id}
                    ).delete()
                    await document.delete()
            except Exception:
                logger.exception(
                    "Failed to delete corresponding note document %s", doc_id_str
                )
    await report.delete()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{notebook_id}/reports", response_model=list[NotebookReportRead])
async def list_notebook_reports(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> list:
    notebook = await get_notebook(notebook_id, current_user)
    return (
        await NotebookReport.find(
            {"notebook_id": notebook.id, "user_id": current_user.id},
        )
        .sort(("created_at", -1))
        .to_list()
    )


@router.get("/{notebook_id}/reports/{report_id}", response_model=NotebookReportRead)
async def get_notebook_report(
    notebook_id: UUID,
    report_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> object:
    notebook = await get_notebook(notebook_id, current_user)
    report = await NotebookReport.find_one(
        {"_id": report_id, "notebook_id": notebook.id, "user_id": current_user.id},
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )
    return report
