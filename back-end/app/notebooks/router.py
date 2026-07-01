import asyncio
import functools
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated
from urllib.parse import quote
from uuid import UUID, uuid4

import obstore
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Request,
    Response,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic_ai.capabilities.process_history import ProcessHistory
from pydantic_ai.run import AgentRunResult
from pydantic_ai.ui.ag_ui import AGUIAdapter

from app.billing.service import check_quota_and_raise, record_usage_event
from app.core.config import Settings, get_settings
from app.core.llm_provider import resolve_chat_provider
from app.core.s3 import generate_presigned_get_url, get_s3_store
from app.notebooks.agent import (
    NotebookChatDeps,
    notebook_chat_agent,
)
from app.notebooks.events import (
    build_document_snapshots,
    build_report_snapshots,
    event_bus,
)
from app.notebooks.exceptions import (
    DocumentContentUnavailableError,
    DocumentNotFoundError,
)
from app.notebooks.memory import (
    append_notebook_chat_history,
    build_user_message_from_agui_payload,
    extract_notebook_chat_transcript,
    extract_scoped_document_ids,
    keep_recent_messages,
    load_notebook_chat_history,
)
from app.notebooks.models import Notebook, NotebookDocument
from app.notebooks.rag.ingestion_service import ingest_document_by_id
from app.notebooks.schemas import (
    NotebookChatHistoryMessage,
    NotebookCreate,
    NotebookDocumentPreviewRead,
    NotebookDocumentRead,
    NotebookPopulateRead,
    NotebookRead,
    NotebookReportRead,
    NotebookUpdate,
    NoteCreate,
    ReportGenerateRequest,
)
from app.notebooks.service import (
    build_chunk_image_url,
    cancel_report,
    create_note,
    create_notebook,
    create_pending_report,
    delete_notebook,
    delete_notebook_document,
    delete_report,
    get_chunks_by_document_id,
    get_chunks_by_filename,
    get_notebook,
    get_report,
    get_single_chunk,
    get_user_event_snapshot,
    list_notebook_documents,
    list_notebooks,
    list_reports,
    populate_notebook_metrics,
    resolve_scoped_document_ids,
    run_report_generation,
    touch_notebook,
    update_notebook,
)
from app.users.dependencies import get_current_user
from app.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notebooks", tags=["Notebooks"])

SSE_PING_SECONDS = 30.0


async def _get_owned_notebook_document(
    notebook_id: UUID,
    document_id: UUID,
    current_user: User,
) -> NotebookDocument:
    document = await NotebookDocument.find_one(
        {
            "_id": document_id,
            "notebook_id": notebook_id,
            "user_id": current_user.id,
        }
    )
    if document is None:
        raise DocumentNotFoundError()
    return document


def _safe_pdf_filename(filename: str) -> str:
    safe_name = filename.replace("\\", "_").replace("/", "_").replace('"', "'")
    safe_name = safe_name.strip() or "document.pdf"
    if not safe_name.lower().endswith(".pdf"):
        safe_name = f"{safe_name}.pdf"
    return safe_name


def _safe_download_filename(filename: str) -> str:
    return (
        filename.replace("\\", "_").replace("/", "_").replace('"', "'").strip()
        or "document"
    )


async def _notebook_event_generator(current_user: User) -> AsyncIterator[str]:
    documents, reports = await get_user_event_snapshot(current_user.id)
    for event in (
        *build_document_snapshots(documents),
        *build_report_snapshots(reports),
    ):
        yield f"data: {json.dumps(event)}\n\n"

    async with event_bus.subscribe(current_user.id) as queue:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=SSE_PING_SECONDS)
                yield f"data: {json.dumps(event)}\n\n"
            except TimeoutError:
                yield ": ping\n\n"


async def _persist_chat_history(
    notebook: Notebook, current_user: User, result: AgentRunResult[object]
) -> None:
    await append_notebook_chat_history(notebook, result.new_messages())
    usage = result.usage
    if usage.total_tokens:
        await record_usage_event(
            user_id=current_user.id,
            quantity=usage.total_tokens,
            idempotency_key=f"chat:{notebook.id}:{uuid4()}",
            notebook_id=notebook.id,
            event_metadata={"source": "chat"},
        )


async def _run_background_note_ingestion(document_id: UUID) -> None:
    settings = get_settings()
    try:
        await ingest_document_by_id(document_id, settings)
    except Exception:
        logger.exception(
            "Background note ingestion failed for document %s", document_id
        )


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
    return StreamingResponse(
        _notebook_event_generator(current_user),
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


@router.get(
    "/{notebook_id}/documents/{document_id}/preview",
    response_model=NotebookDocumentPreviewRead,
)
async def read_notebook_document_preview(
    notebook_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> NotebookDocumentPreviewRead:
    document = await _get_owned_notebook_document(
        notebook_id,
        document_id,
        current_user,
    )

    if document.content is not None:
        return NotebookDocumentPreviewRead(
            filename=document.filename,
            content_type=document.content_type,
            size=document.size,
            url=None,
            content=document.content,
            preview_type="text",
        )

    if not document.s3_key:
        raise DocumentContentUnavailableError()

    url = generate_presigned_get_url(
        settings,
        key=document.s3_key,
        expires_in=3600,
    )
    return NotebookDocumentPreviewRead(
        filename=document.filename,
        content_type=document.content_type,
        size=document.size,
        url=url,
        content=None,
        preview_type="url",
    )


@router.get("/{notebook_id}/documents/{document_id}/pdf-inline")
async def read_notebook_document_pdf_inline(
    notebook_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    document = await _get_owned_notebook_document(
        notebook_id,
        document_id,
        current_user,
    )
    if not document.s3_key:
        raise DocumentContentUnavailableError()

    try:
        result = await obstore.get_async(get_s3_store(settings), document.s3_key)
    except FileNotFoundError as exc:
        raise DocumentNotFoundError() from exc
    pdf_bytes = bytes(await result.bytes_async())
    safe_filename = _safe_pdf_filename(document.filename)

    async def stream_pdf() -> AsyncIterator[bytes]:
        yield pdf_bytes

    return StreamingResponse(
        stream_pdf(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="{safe_filename}"; '
                f"filename*=UTF-8''{quote(safe_filename)}"
            ),
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.get("/{notebook_id}/documents/{document_id}/download")
async def download_notebook_document(
    notebook_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    document = await _get_owned_notebook_document(
        notebook_id,
        document_id,
        current_user,
    )
    safe_filename = _safe_download_filename(document.filename)

    if document.content is not None:
        body = document.content.encode("utf-8")
    else:
        if not document.s3_key:
            raise DocumentContentUnavailableError()
        try:
            result = await obstore.get_async(get_s3_store(settings), document.s3_key)
        except FileNotFoundError as exc:
            raise DocumentNotFoundError() from exc
        body = bytes(await result.bytes_async())

    async def stream_document() -> AsyncIterator[bytes]:
        yield body

    return StreamingResponse(
        stream_document(),
        media_type=document.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{safe_filename}"; '
                f"filename*=UTF-8''{quote(safe_filename)}"
            ),
            "Cache-Control": "private, max-age=3600",
        },
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
    document = await create_note(notebook_id, payload, current_user)
    background_tasks.add_task(_run_background_note_ingestion, document.id)
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

    await check_quota_and_raise(current_user.id, 0, settings)

    try:
        request_payload = json.loads(await request.body() or b"{}")
    except ValueError, TypeError:
        request_payload = None

    # Validate the optional document scope before persisting the user turn, so a
    # rejected scope (deleted/foreign/malformed id) doesn't leave an orphaned
    # user message in the history with no assistant reply.
    scoped_document_ids = await resolve_scoped_document_ids(
        notebook, current_user, extract_scoped_document_ids(request_payload)
    )

    new_user_message = build_user_message_from_agui_payload(request_payload)
    if new_user_message is not None:
        await append_notebook_chat_history(notebook, [new_user_message])

    deps = NotebookChatDeps(
        notebook=notebook,
        current_user=current_user,
        settings=settings,
        document_ids=scoped_document_ids,
    )

    return await AGUIAdapter.dispatch_request(
        request,
        agent=notebook_chat_agent,
        model=resolve_chat_provider(),
        deps=deps,
        message_history=message_history,
        conversation_id=str(notebook.id),
        on_complete=functools.partial(_persist_chat_history, notebook, current_user),
        capabilities=[ProcessHistory(keep_recent_messages)],
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
    return await get_chunks_by_filename(notebook_id, filename, current_user)


@router.get(
    "/{notebook_id}/documents/{document_id}/chunks",
    response_model=list[dict[str, object]],
)
async def read_document_chunks_by_id(
    notebook_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict[str, object]]:
    return await get_chunks_by_document_id(notebook_id, document_id, current_user)


@router.get("/{notebook_id}/documents/{document_id}/chunks/{chunk_index}")
async def read_single_chunk(
    notebook_id: UUID,
    document_id: UUID,
    chunk_index: int,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
    return await get_single_chunk(notebook_id, document_id, chunk_index, current_user)


@router.get("/{notebook_id}/documents/{document_id}/chunks/{chunk_index}/image-url")
async def get_chunk_image_url(
    notebook_id: UUID,
    document_id: UUID,
    chunk_index: int,
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    return await build_chunk_image_url(
        notebook_id, document_id, chunk_index, current_user, settings
    )


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
    settings: Annotated[Settings, Depends(get_settings)],
) -> object:
    (
        report,
        context,
        instructions,
        detail_level,
        question_count,
    ) = await create_pending_report(notebook_id, payload, current_user, settings)
    background_tasks.add_task(
        run_report_generation,
        report_id=report.id,
        report_type=payload.report_type,
        context=context,
        instructions=instructions,
        detail_level=detail_level,
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
    return await cancel_report(notebook_id, report_id, current_user)


@router.delete(
    "/{notebook_id}/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_notebook_report(
    notebook_id: UUID,
    report_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    await delete_report(notebook_id, report_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{notebook_id}/reports", response_model=list[NotebookReportRead])
async def list_notebook_reports(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> list:
    return await list_reports(notebook_id, current_user)


@router.get("/{notebook_id}/reports/{report_id}", response_model=NotebookReportRead)
async def get_notebook_report(
    notebook_id: UUID,
    report_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> object:
    return await get_report(notebook_id, report_id, current_user)
