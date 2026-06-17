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
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelRequest
from pydantic_ai.run import AgentRunResult
from pydantic_ai.ui.ag_ui import AGUIAdapter
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, delete, select

from app.core.config import get_settings
from app.core.database import get_session
from app.notebooks.agent import (
    NotebookChatDeps,
    chat_provider_is_configured,
    generate_blog_post,
    generate_briefing_doc,
    generate_custom_report,
    generate_flashcards,
    generate_mindmap,
    generate_quiz,
    generate_study_guide,
    get_notebook_chat_agent,
)
from app.notebooks.memory import (
    append_notebook_chat_history,
    extract_notebook_chat_transcript,
    load_notebook_chat_history,
)
from app.notebooks.models import (
    Notebook,
    NotebookDocument,
    NotebookDocumentChunk,
    NotebookReport,
)
from app.notebooks.schemas import (
    BlogPostReport,
    BriefingDocReport,
    CustomReport,
    FlashcardReport,
    MindMapReport,
    NotebookChatHistoryMessage,
    NotebookCreate,
    NotebookDocumentRead,
    NotebookPopulateRead,
    NotebookRead,
    NotebookReportRead,
    NotebookUpdate,
    NoteCreate,
    QuizReport,
    ReportGenerateRequest,
    StudyGuideReport,
)
from app.notebooks.service import (
    create_notebook,
    delete_notebook,
    delete_notebook_document,
    get_notebook,
    list_notebook_documents,
    list_notebooks,
    populate_notebook_metrics,
    touch_notebook,
    update_notebook,
)
from app.users.dependencies import get_current_user
from app.users.models import User

logger = logging.getLogger(__name__)

# Maximum characters of source text fed to the LLM for report generation.
# ~120 k chars ≈ 30 k tokens, safely within most context windows.
_REPORT_CONTEXT_CHAR_LIMIT = 120_000

# Maps the "Fewer / Standard / More" preset (quiz questions or flashcards) to a count.
_COUNT_BY_SIZE = {"fewer": 10, "standard": 20, "more": 30}


router = APIRouter(prefix="/notebooks", tags=["Notebooks"])


@router.get("/", response_model=list[NotebookRead])
def read_notebooks(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list:
    return list_notebooks(session, current_user)


@router.post("/", response_model=NotebookRead, status_code=status.HTTP_201_CREATED)
def create_notebook_route(
    payload: NotebookCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    return create_notebook(session, payload, current_user)


@router.get("/events")
async def read_notebook_events(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> StreamingResponse:
    async def event_generator() -> AsyncIterator[str]:
        last_doc_state: dict[UUID, tuple[str, datetime, UUID]] = {}
        last_report_state: dict[UUID, tuple[str, datetime, str, UUID]] = {}
        first_tick = True

        try:
            while True:
                # ── Documents ──────────────────────────────────────────
                docs = session.exec(
                    select(NotebookDocument).where(
                        NotebookDocument.user_id == current_user.id
                    )
                ).all()

                # ── Reports ────────────────────────────────────────────
                reports = session.exec(
                    select(NotebookReport).where(
                        NotebookReport.user_id == current_user.id
                    )
                ).all()

                if first_tick:
                    # Snapshot: documents grouped by notebook
                    by_notebook: dict[UUID, list] = {}
                    for doc in docs:
                        by_notebook.setdefault(doc.notebook_id, []).append(doc)

                    for notebook_id, notebook_docs in by_notebook.items():
                        serialized_docs = [
                            NotebookDocumentRead.model_validate(doc).model_dump(
                                mode="json"
                            )
                            for doc in notebook_docs
                        ]
                        yield f"data: {json.dumps({'type': 'snapshot', 'notebook_id': str(notebook_id), 'documents': serialized_docs, 'timestamp': datetime.now(UTC).isoformat()})}\n\n"

                    last_doc_state = {
                        doc.id: (doc.status, doc.updated_at, doc.notebook_id)
                        for doc in docs
                    }

                    # Snapshot: reports grouped by notebook
                    reports_by_notebook: dict[UUID, list] = {}
                    for report in reports:
                        reports_by_notebook.setdefault(report.notebook_id, []).append(
                            report
                        )

                    for notebook_id, notebook_reports in reports_by_notebook.items():
                        serialized_reports = [
                            NotebookReportRead.model_validate(r).model_dump(mode="json")
                            for r in notebook_reports
                        ]
                        yield f"data: {json.dumps({'type': 'report_snapshot', 'notebook_id': str(notebook_id), 'reports': serialized_reports, 'timestamp': datetime.now(UTC).isoformat()})}\n\n"

                    last_report_state = {
                        report.id: (
                            report.status,
                            report.updated_at,
                            report.report_type,
                            report.notebook_id,
                        )
                        for report in reports
                    }
                    first_tick = False
                else:
                    # Document updates
                    current_doc_ids: set[UUID] = set()
                    for doc in docs:
                        current_doc_ids.add(doc.id)
                        prev = last_doc_state.get(doc.id)
                        if prev is None or prev[:2] != (doc.status, doc.updated_at):
                            serialized_doc = NotebookDocumentRead.model_validate(
                                doc
                            ).model_dump(mode="json")
                            yield f"data: {json.dumps({'type': 'document_update', 'notebook_id': str(doc.notebook_id), 'document': serialized_doc, 'timestamp': datetime.now(UTC).isoformat()})}\n\n"
                            last_doc_state[doc.id] = (
                                doc.status,
                                doc.updated_at,
                                doc.notebook_id,
                            )

                    removed_doc_ids = set(last_doc_state.keys()) - current_doc_ids
                    for rid in removed_doc_ids:
                        del last_doc_state[rid]

                    # Report updates
                    current_report_ids: set[UUID] = set()
                    for report in reports:
                        current_report_ids.add(report.id)
                        prev = last_report_state.get(report.id)
                        if prev is None or prev[:2] != (
                            report.status,
                            report.updated_at,
                        ):
                            serialized_report = NotebookReportRead.model_validate(
                                report
                            ).model_dump(mode="json")
                            yield f"data: {json.dumps({'type': 'report_update', 'notebook_id': str(report.notebook_id), 'report': serialized_report, 'timestamp': datetime.now(UTC).isoformat()})}\n\n"
                            last_report_state[report.id] = (
                                report.status,
                                report.updated_at,
                                report.report_type,
                                report.notebook_id,
                            )

                    removed_report_ids = (
                        set(last_report_state.keys()) - current_report_ids
                    )
                    for rid in removed_report_ids:
                        del last_report_state[rid]

                # Expire the SQLAlchemy session identity map cache to ensure consecutive ticks
                # fetch fresh records directly from the database rather than from memory.
                session.expire_all()

                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/{notebook_id}", response_model=NotebookRead)
def read_notebook(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    return get_notebook(session, notebook_id, current_user)


@router.patch("/{notebook_id}", response_model=NotebookRead)
def update_notebook_route(
    notebook_id: UUID,
    payload: NotebookUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    return update_notebook(session, notebook_id, payload, current_user)


@router.post("/{notebook_id}/touch", response_model=NotebookRead)
def touch_notebook_route(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    return touch_notebook(session, notebook_id, current_user)


@router.get("/{notebook_id}/populate", response_model=NotebookPopulateRead)
def populate_notebook_route(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    return populate_notebook_metrics(session, notebook_id, current_user)


@router.get("/{notebook_id}/documents", response_model=list[NotebookDocumentRead])
def read_notebook_documents(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list:
    return list_notebook_documents(session, notebook_id, current_user)


def _run_background_note_ingestion(
    document_id: UUID,
    _engine: object | None = None,
) -> None:
    """Background task to run vector embedding ingestion on a database-stored note."""
    from app.core.config import get_settings
    from app.core.database import engine as _default_engine
    from app.notebooks.tools.ingestion import ingest_document_by_id

    db_engine = _engine or _default_engine
    settings = get_settings()
    with Session(db_engine) as session:
        try:
            ingest_document_by_id(session, document_id, settings)
        except Exception:
            logger.exception(
                "Background note ingestion failed for document %s", document_id
            )


@router.delete(
    "/{notebook_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_notebook_document_route(
    notebook_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    delete_notebook_document(session, notebook_id, document_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{notebook_id}/notes",
    response_model=NotebookDocumentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_notebook_note(
    notebook_id: UUID,
    payload: NoteCreate,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    notebook = get_notebook(session, notebook_id, current_user)

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
        status="uploaded",  # Mark as uploaded so ingestion claims it properly
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

    try:
        session.add(document)
        session.add(report)
        session.commit()
        session.refresh(document)
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error"
        ) from exc

    # Queue the background ingestion
    session_engine = session.get_bind()
    background_tasks.add_task(
        _run_background_note_ingestion,
        document_id=document.id,
        _engine=session_engine,
    )

    return document


@router.post("/{notebook_id}/chat")
async def chat_notebook_route(
    notebook_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    notebook = get_notebook(session, notebook_id, current_user)
    message_history = load_notebook_chat_history(session, notebook)
    settings = get_settings()

    deps = NotebookChatDeps(
        session=session,
        notebook=notebook,
        current_user=current_user,
        settings=settings,
    )

    async def persist_chat_history(result: AgentRunResult[object]) -> None:
        append_notebook_chat_history(session, notebook, result.new_messages())

    async def keep_recent(messages: list[ModelMessage]) -> list[ModelMessage]:
        system_prompts = []
        other_messages = []
        for msg in messages:
            is_system = False
            if isinstance(msg, ModelRequest):
                part_names = {type(part).__name__ for part in msg.parts}
                if "SystemPromptPart" in part_names or (
                    msg.instructions
                    and not (
                        part_names
                        & {"UserPromptPart", "ToolReturnPart", "RetryPromptPart"}
                    )
                ):
                    is_system = True

            if is_system:
                system_prompts.append(msg)
            else:
                other_messages.append(msg)

        # Keep the last 15 other messages
        recent_limit = 15
        recent_others = (
            other_messages[-recent_limit:]
            if len(other_messages) > recent_limit
            else other_messages
        )

        # Combine system prompts and recent others while maintaining their original relative chronological order
        keep_set = {id(msg) for msg in system_prompts} | {
            id(msg) for msg in recent_others
        }
        return [msg for msg in messages if id(msg) in keep_set]

    return await AGUIAdapter.dispatch_request(
        request,
        agent=get_notebook_chat_agent(),
        deps=deps,
        message_history=message_history,
        conversation_id=str(notebook.id),
        on_complete=persist_chat_history,
        capabilities=[ProcessHistory(keep_recent)],
    )


@router.get(
    "/{notebook_id}/chat/history", response_model=list[NotebookChatHistoryMessage]
)
def read_notebook_chat_history(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    include_reasoning: bool = False,
) -> list[dict[str, object]]:
    notebook = get_notebook(session, notebook_id, current_user)
    return extract_notebook_chat_transcript(
        session, notebook, include_reasoning=include_reasoning
    )


@router.get("/{notebook_id}/documents/chunks", response_model=list[dict[str, object]])
def read_document_chunks(
    notebook_id: UUID,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list:
    notebook = get_notebook(session, notebook_id, current_user)
    document = session.exec(
        select(NotebookDocument).where(
            NotebookDocument.notebook_id == notebook.id,
            NotebookDocument.filename == filename,
            NotebookDocument.user_id == current_user.id,
        )
    ).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    chunks = session.exec(
        select(NotebookDocumentChunk)
        .where(NotebookDocumentChunk.document_id == document.id)
        .order_by(NotebookDocumentChunk.chunk_index.asc())
    ).all()

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
def read_document_chunks_by_id(
    notebook_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[dict[str, object]]:
    notebook = get_notebook(session, notebook_id, current_user)
    document = session.exec(
        select(NotebookDocument).where(
            NotebookDocument.id == document_id,
            NotebookDocument.notebook_id == notebook.id,
            NotebookDocument.user_id == current_user.id,
        )
    ).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    chunks = session.exec(
        select(NotebookDocumentChunk)
        .where(NotebookDocumentChunk.document_id == document.id)
        .order_by(NotebookDocumentChunk.chunk_index.asc())
    ).all()

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


@router.get("/{notebook_id}/chunks", response_model=dict[str, object])
def read_notebook_chunk(
    notebook_id: UUID,
    filename: str,
    chunk_index: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    notebook = get_notebook(session, notebook_id, current_user)
    chunk = session.exec(
        select(NotebookDocumentChunk)
        .join(
            NotebookDocument, NotebookDocument.id == NotebookDocumentChunk.document_id
        )
        .where(NotebookDocument.filename == filename)
        .where(NotebookDocumentChunk.chunk_index == chunk_index)
        .where(NotebookDocument.notebook_id == notebook.id)
        .where(NotebookDocument.user_id == current_user.id)
    ).first()
    if not chunk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found"
        )

    return {
        "content": chunk.content,
        "filename": filename,
        "chunk_index": chunk_index,
    }


@router.get(
    "/{notebook_id}/documents/{document_id}/chunks/{chunk_index}",
    response_model=dict[str, object],
)
def read_notebook_chunk_by_document_id(
    notebook_id: UUID,
    document_id: UUID,
    chunk_index: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    notebook = get_notebook(session, notebook_id, current_user)
    chunk = session.exec(
        select(NotebookDocumentChunk)
        .join(
            NotebookDocument, NotebookDocument.id == NotebookDocumentChunk.document_id
        )
        .where(NotebookDocumentChunk.document_id == document_id)
        .where(NotebookDocumentChunk.chunk_index == chunk_index)
        .where(NotebookDocument.notebook_id == notebook.id)
        .where(NotebookDocument.user_id == current_user.id)
    ).first()
    if not chunk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found"
        )

    document = session.exec(
        select(NotebookDocument).where(
            NotebookDocument.id == document_id,
            NotebookDocument.notebook_id == notebook.id,
            NotebookDocument.user_id == current_user.id,
        )
    ).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
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
def delete_notebook_route(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    delete_notebook(session, notebook_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Report generation (background)
# ---------------------------------------------------------------------------


def _build_report_context(
    session: Session, notebook: Notebook, current_user: User
) -> str:
    """Return all indexed chunk text for a notebook, up to the char limit."""
    chunks = session.exec(
        select(NotebookDocumentChunk, NotebookDocument.filename)
        .join(
            NotebookDocument, NotebookDocument.id == NotebookDocumentChunk.document_id
        )
        .where(NotebookDocument.notebook_id == notebook.id)
        .where(NotebookDocument.user_id == current_user.id)
        .where(NotebookDocument.status == "indexed")
        .order_by(NotebookDocument.filename, NotebookDocumentChunk.chunk_index)
    ).all()

    if not chunks:
        return ""

    parts: list[str] = []
    total = 0
    for chunk, filename in chunks:
        header = f"[file={filename} chunk={chunk.chunk_index}]"
        block = f"{header}\n{chunk.content}"
        if total + len(block) > _REPORT_CONTEXT_CHAR_LIMIT:
            break
        parts.append(block)
        total += len(block)

    return "\n\n".join(parts)


async def _run_report_generation(
    report_id: UUID,
    report_type: str,
    context: str,
    instructions: str | None,
    detail_level: str | None,
    question_count: int | None = None,
    _engine: object | None = None,
) -> None:
    """Background task that runs the LLM call and persists the result."""
    from app.core.database import engine as _default_engine

    db_engine = _engine or _default_engine
    with Session(db_engine) as session:
        report = session.get(NotebookReport, report_id)
        if report is None or report.status == "cancelled":
            return

        # Mark as generating
        report.status = "generating"
        report.updated_at = datetime.now(UTC)
        session.add(report)
        session.commit()

        # Re-check cancellation after status update
        session.expire_all()
        report = session.get(NotebookReport, report_id)
        if report is None or report.status == "cancelled":
            return

        report_content: (
            BriefingDocReport
            | StudyGuideReport
            | BlogPostReport
            | CustomReport
            | MindMapReport
            | QuizReport
            | FlashcardReport
        )
        try:
            match report_type:
                case "briefing":
                    report_content = await generate_briefing_doc(context, instructions)
                case "study_guide":
                    report_content = await generate_study_guide(context, instructions)
                case "blog":
                    report_content = await generate_blog_post(context, instructions)
                case "custom":
                    report_content = await generate_custom_report(
                        context, instructions or ""
                    )
                case "mindmap":
                    report_content = await generate_mindmap(
                        context, detail_level, instructions
                    )
                case "quiz":
                    report_content = await generate_quiz(
                        context,
                        count=question_count or 20,
                        difficulty=detail_level,
                        additional_instructions=instructions,
                    )
                case "flashcards":
                    report_content = await generate_flashcards(
                        context,
                        count=question_count or 20,
                        difficulty=detail_level,
                        additional_instructions=instructions,
                    )
                case _:
                    logger.error("Unknown report type: %s", report_type)
                    report.status = "failed"
                    report.error_message = f"Unknown report type: {report_type}"
                    report.updated_at = datetime.now(UTC)
                    session.add(report)
                    session.commit()
                    return
        except ModelHTTPError as exc:
            session.expire_all()
            report = session.get(NotebookReport, report_id)
            if report is not None and report.status != "cancelled":
                report.status = "failed"
                if exc.status_code == 429:
                    report.error_message = "The AI provider rate limit was exceeded. Please wait a moment and try again."
                else:
                    report.error_message = "The AI provider failed to generate the report. Please try again."
                report.updated_at = datetime.now(UTC)
                session.add(report)
                session.commit()
            return
        except Exception:
            logger.exception("Unexpected error during report generation")
            session.expire_all()
            report = session.get(NotebookReport, report_id)
            if report is not None and report.status != "cancelled":
                report.status = "failed"
                report.error_message = (
                    "An unexpected error occurred during report generation."
                )
                report.updated_at = datetime.now(UTC)
                session.add(report)
                session.commit()
            return

        # Re-check cancellation before writing content
        session.expire_all()
        report = session.get(NotebookReport, report_id)
        if report is None or report.status == "cancelled":
            return

        # Success
        report.status = "completed"
        report.content = report_content.model_dump()
        report.updated_at = datetime.now(UTC)
        session.add(report)
        session.commit()


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
    session: Annotated[Session, Depends(get_session)],
) -> object:
    notebook = get_notebook(session, notebook_id, current_user)

    if not chat_provider_is_configured():
        provider = get_settings().chat_provider.strip().lower()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service is not configured. Set the API key for the '{provider}' chat provider.",
        )

    context = _build_report_context(session, notebook, current_user)
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
        question_count = _COUNT_BY_SIZE.get(
            (payload.number_of_questions or "standard").strip().lower(), 20
        )
    elif payload.report_type == "flashcards":
        question_count = _COUNT_BY_SIZE.get(
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
    try:
        session.add(report)
        session.commit()
        session.refresh(report)
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error"
        ) from exc

    # Capture the engine from the request session so the background task uses
    # the same database (critical for tests where the session engine differs
    # from the module-level engine import).
    session_engine = session.get_bind()

    background_tasks.add_task(
        _run_report_generation,
        report_id=report.id,
        report_type=payload.report_type,
        context=context,
        instructions=instructions,
        detail_level=payload.detail_level,
        question_count=question_count,
        _engine=session_engine,
    )

    return report


@router.post(
    "/{notebook_id}/reports/{report_id}/cancel",
    response_model=NotebookReportRead,
)
def cancel_notebook_report(
    notebook_id: UUID,
    report_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    notebook = get_notebook(session, notebook_id, current_user)
    report = session.exec(
        select(NotebookReport).where(
            NotebookReport.id == report_id,
            NotebookReport.notebook_id == notebook.id,
            NotebookReport.user_id == current_user.id,
        )
    ).first()
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
    try:
        session.add(report)
        session.commit()
        session.refresh(report)
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error"
        ) from exc

    return report


@router.delete(
    "/{notebook_id}/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_notebook_report(
    notebook_id: UUID,
    report_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    notebook = get_notebook(session, notebook_id, current_user)
    report = session.exec(
        select(NotebookReport).where(
            NotebookReport.id == report_id,
            NotebookReport.notebook_id == notebook.id,
            NotebookReport.user_id == current_user.id,
        )
    ).first()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )

    try:
        # If it's a note, also delete the corresponding document
        if report.report_type == "note" and isinstance(report.content, dict):
            doc_id_str = report.content.get("document_id")
            if doc_id_str:
                try:
                    doc_id = UUID(doc_id_str)
                    document = session.exec(
                        select(NotebookDocument).where(
                            NotebookDocument.id == doc_id,
                            NotebookDocument.notebook_id == notebook.id,
                            NotebookDocument.user_id == current_user.id,
                        )
                    ).first()
                    if document:
                        session.exec(
                            delete(NotebookDocumentChunk).where(
                                NotebookDocumentChunk.document_id == document.id
                            )
                        )
                        session.delete(document)
                except Exception:
                    logger.exception(
                        "Failed to delete corresponding note document %s", doc_id_str
                    )
        session.delete(report)
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error"
        ) from exc


@router.get("/{notebook_id}/reports", response_model=list[NotebookReportRead])
def list_notebook_reports(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list:
    notebook = get_notebook(session, notebook_id, current_user)
    return list(
        session.exec(
            select(NotebookReport)
            .where(NotebookReport.notebook_id == notebook.id)
            .where(NotebookReport.user_id == current_user.id)
            .order_by(NotebookReport.created_at.desc())
        ).all()
    )


@router.get("/{notebook_id}/reports/{report_id}", response_model=NotebookReportRead)
def get_notebook_report(
    notebook_id: UUID,
    report_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    notebook = get_notebook(session, notebook_id, current_user)
    report = session.exec(
        select(NotebookReport).where(
            NotebookReport.id == report_id,
            NotebookReport.notebook_id == notebook.id,
            NotebookReport.user_id == current_user.id,
        )
    ).first()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )
    return report
