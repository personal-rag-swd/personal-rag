import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from beanie import SortDirection
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelRequest

from app.billing.service import check_quota_and_raise, record_usage_event
from app.core.config import Settings, get_settings
from app.core.event_bus import domain_event_bus
from app.core.llm_provider import chat_provider_is_configured
from app.core.s3 import generate_presigned_get_url
from app.notebooks.agent.report_agents import (
    generate_blog_post,
    generate_briefing_doc,
    generate_custom_report,
    generate_flashcards,
    generate_mindmap,
    generate_quiz,
    generate_study_guide,
    get_last_report_usage,
)
from app.notebooks.domain_events import (
    ReportCancelled,
    ReportCompleted,
    ReportFailed,
    ReportGenerating,
)
from app.notebooks.exceptions import (
    CannotCancelReportError,
    ChunkNotAnImageError,
    ChunkNotFoundError,
    CustomReportMissingInstructionsError,
    DocumentNotFoundError,
    ImageNotFoundError,
    LLMNotConfiguredError,
    NoIndexedDocumentsError,
    NotebookNotFoundError,
    ReportNotFoundError,
)
from app.notebooks.memory import load_notebook_chat_history
from app.notebooks.models import (
    Notebook,
    NotebookDocument,
    NotebookDocumentChunk,
    NotebookMessage,
    NotebookReport,
)
from app.notebooks.prompt.context_prompts import source_block
from app.notebooks.rag.search_service import RetrievedChunk
from app.notebooks.schemas import (
    BlogPostReport,
    BriefingDocReport,
    CustomReport,
    FlashcardReport,
    MindMapReport,
    NotebookCreate,
    NotebookPopulateRead,
    NotebookUpdate,
    NoteCreate,
    QuizReport,
    ReportGenerateRequest,
    StudyGuideReport,
)
from app.users.models import User

_logger = logging.getLogger(__name__)


async def list_notebooks(current_user: User) -> list[Notebook]:
    return (
        await Notebook.find({"user_id": current_user.id})
        .sort(
            ("last_active_at", SortDirection.DESCENDING),
            ("created_at", SortDirection.DESCENDING),
        )
        .to_list()
    )


async def get_notebook(notebook_id: UUID, current_user: User) -> Notebook:
    notebook = await Notebook.find_one(
        {"_id": notebook_id, "user_id": current_user.id},
    )
    if notebook is None:
        raise NotebookNotFoundError()
    return notebook


async def list_notebook_documents(
    notebook_id: UUID,
    current_user: User,
) -> list[NotebookDocument]:
    notebook = await get_notebook(notebook_id, current_user)
    return (
        await NotebookDocument.find(
            {"notebook_id": notebook.id, "user_id": current_user.id},
        )
        .sort(("created_at", SortDirection.DESCENDING))
        .to_list()
    )


async def delete_notebook_document(
    notebook_id: UUID,
    document_id: UUID,
    current_user: User,
) -> None:
    notebook = await get_notebook(notebook_id, current_user)
    document = await NotebookDocument.find_one(
        {"_id": document_id, "notebook_id": notebook.id, "user_id": current_user.id},
    )
    if document is None:
        raise DocumentNotFoundError()

    await NotebookDocumentChunk.find({"document_id": document.id}).delete()

    note_reports = await NotebookReport.find(
        {"notebook_id": notebook.id, "user_id": current_user.id, "report_type": "note"},
    ).to_list()
    for r in note_reports:
        if isinstance(r.content, dict) and r.content.get("document_id") == str(
            document.id
        ):
            await r.delete()

    await document.delete()


async def create_notebook(payload: NotebookCreate, current_user: User) -> Notebook:
    notebook = Notebook(
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        tags=payload.tags,
    )
    await notebook.insert()
    return notebook


async def update_notebook(
    notebook_id: UUID,
    payload: NotebookUpdate,
    current_user: User,
) -> Notebook:
    notebook = await get_notebook(notebook_id, current_user)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(notebook, key, value)
    notebook.updated_at = datetime.now(UTC)
    await notebook.save()
    return notebook


async def touch_notebook(notebook_id: UUID, current_user: User) -> Notebook:
    notebook = await get_notebook(notebook_id, current_user)
    now = datetime.now(UTC)
    notebook.last_active_at = now
    notebook.updated_at = now
    await notebook.save()
    return notebook


async def populate_notebook_metrics(
    notebook_id: UUID, current_user: User
) -> NotebookPopulateRead:
    notebook = await get_notebook(notebook_id, current_user)
    doc_count = await NotebookDocument.find(
        {"notebook_id": notebook.id, "user_id": current_user.id},
    ).count()
    messages = await load_notebook_chat_history(notebook)
    query_count = sum(1 for message in messages if isinstance(message, ModelRequest))
    metrics = NotebookPopulateRead.model_validate(notebook, from_attributes=True)
    metrics.document_count = doc_count
    metrics.query_count = query_count
    return metrics


async def _delete_notebook_child_documents(notebook_id: UUID) -> None:
    await NotebookMessage.find({"notebook_id": notebook_id}).delete()
    await NotebookDocument.find({"notebook_id": notebook_id}).delete()
    await NotebookDocumentChunk.find({"notebook_id": notebook_id}).delete()
    await NotebookReport.find({"notebook_id": notebook_id}).delete()


async def delete_notebook(notebook_id: UUID, current_user: User) -> None:
    notebook = await get_notebook(notebook_id, current_user)
    await _delete_notebook_child_documents(notebook.id)
    await notebook.delete()


_REPORT_CONTEXT_CHAR_LIMIT = 120_000


async def build_report_context(notebook: Notebook, current_user: User) -> str:
    documents = (
        await NotebookDocument.find(
            {
                "notebook_id": notebook.id,
                "user_id": current_user.id,
                "status": "indexed",
            },
        )
        .sort(("filename", SortDirection.ASCENDING))
        .to_list()
    )

    if not documents:
        return ""

    doc_map = {str(d.id): d.filename for d in documents}
    doc_ids = [d.id for d in documents]

    chunks = (
        await NotebookDocumentChunk.find({"document_id": {"$in": doc_ids}})
        .sort(("chunk_index", SortDirection.ASCENDING))
        .to_list()
    )

    parts: list[str] = []
    total = 0
    for chunk in chunks:
        metadata = chunk.chunk_metadata or {}
        # Same SOURCE grammar as chat context blocks, so models see one
        # labeling convention and any citations they emit resolve the same way.
        block = source_block(
            RetrievedChunk(
                document_id=chunk.document_id,
                filename=doc_map.get(str(chunk.document_id), "unknown"),
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                metadata=metadata,
                chunk_type="image" if metadata.get("chunk_type") == "image" else "text",
            )
        )
        if total + len(block) > _REPORT_CONTEXT_CHAR_LIMIT:
            break
        parts.append(block)
        total += len(block)

    return "\n\n".join(parts)


async def run_report_generation(
    report_id: UUID,
    report_type: str,
    context: str,
    instructions: str | None,
    detail_level: str | None,
    question_count: int | None = None,
) -> None:
    report = await NotebookReport.find_one({"_id": report_id})
    if report is None or report.status == "cancelled":
        return

    report.status = "generating"
    report.updated_at = datetime.now(UTC)
    await report.save()
    await domain_event_bus.emit(ReportGenerating(report))

    report = await NotebookReport.find_one({"_id": report_id})
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
                _logger.error("Unknown report type: %s", report_type)
                report.status = "failed"
                report.error_message = f"Unknown report type: {report_type}"
                report.updated_at = datetime.now(UTC)
                await report.save()
                await domain_event_bus.emit(ReportFailed(report))
                return
    except ModelHTTPError as exc:
        report = await NotebookReport.find_one({"_id": report_id})
        if report is not None and report.status != "cancelled":
            report.status = "failed"
            if exc.status_code == 429:
                report.error_message = "The AI provider rate limit was exceeded. Please wait a moment and try again."
            else:
                report.error_message = (
                    "The AI provider failed to generate the report. Please try again."
                )
            report.updated_at = datetime.now(UTC)
            await report.save()
            await domain_event_bus.emit(ReportFailed(report))
        return
    except Exception:
        _logger.exception("Unexpected error during report generation")
        report = await NotebookReport.find_one({"_id": report_id})
        if report is not None and report.status != "cancelled":
            report.status = "failed"
            report.error_message = (
                "An unexpected error occurred during report generation."
            )
            report.updated_at = datetime.now(UTC)
            await report.save()
            await domain_event_bus.emit(ReportFailed(report))
        return

    usage = get_last_report_usage()
    if usage is not None and usage.total_tokens:
        await record_usage_event(
            user_id=report.user_id,
            quantity=usage.total_tokens,
            idempotency_key=f"report:{report_id}",
            settings=get_settings(),
            notebook_id=report.notebook_id,
            event_metadata={"source": "report", "report_type": report_type},
        )

    report = await NotebookReport.find_one({"_id": report_id})
    if report is None or report.status == "cancelled":
        return

    report.status = "completed"
    report.content = report_content.model_dump()
    report.updated_at = datetime.now(UTC)
    await report.save()
    await domain_event_bus.emit(ReportCompleted(report))


_QUESTION_COUNT_MAP = {"fewer": 10, "standard": 20, "more": 30}


def _serialize_chunk(c: NotebookDocumentChunk) -> dict[str, object]:
    return {
        "id": str(c.id),
        "document_id": str(c.document_id),
        "chunk_index": c.chunk_index,
        "content": c.content,
        "metadata": c.chunk_metadata,
    }


async def _fetch_and_serialize_chunks(
    document: NotebookDocument,
) -> list[dict[str, object]]:
    chunks = (
        await NotebookDocumentChunk.find({"document_id": document.id})
        .sort(("chunk_index", SortDirection.ASCENDING))
        .to_list()
    )
    return [_serialize_chunk(c) for c in chunks]


async def get_notebook_document(
    notebook: Notebook, document_id: UUID, current_user: User
) -> NotebookDocument:
    document = await NotebookDocument.find_one(
        {"_id": document_id, "notebook_id": notebook.id, "user_id": current_user.id},
    )
    if document is None:
        raise DocumentNotFoundError()
    return document


async def resolve_scoped_document_ids(
    notebook: Notebook,
    current_user: User,
    raw_document_ids: list[object],
) -> list[UUID] | None:
    """Validate client-supplied document ids that scope chat retrieval.

    Each id must belong to ``notebook`` and ``current_user`` so a chat request
    can't be used to probe document ids from other notebooks. Ownership is
    checked in a single ``$in`` query. Returns None when no scope is supplied
    (retrieval spans all sources); raises ``DocumentNotFoundError`` if any id
    is malformed or not owned.
    """
    if not raw_document_ids:
        return None

    parsed_ids: list[UUID] = []
    for raw_document_id in raw_document_ids:
        try:
            parsed_ids.append(UUID(str(raw_document_id)))
        except ValueError as exc:
            raise DocumentNotFoundError() from exc

    unique_ids = list(dict.fromkeys(parsed_ids))
    owned_count = await NotebookDocument.find(
        {
            "_id": {"$in": unique_ids},
            "notebook_id": notebook.id,
            "user_id": current_user.id,
        }
    ).count()
    if owned_count != len(unique_ids):
        raise DocumentNotFoundError()

    return unique_ids


async def get_notebook_report(
    notebook: Notebook, report_id: UUID, current_user: User
) -> NotebookReport:
    report = await NotebookReport.find_one(
        {"_id": report_id, "notebook_id": notebook.id, "user_id": current_user.id},
    )
    if report is None:
        raise ReportNotFoundError()
    return report


async def get_user_event_snapshot(
    user_id: UUID,
) -> tuple[list[NotebookDocument], list[NotebookReport]]:
    documents, reports = await asyncio.gather(
        NotebookDocument.find({"user_id": user_id}).to_list(),
        NotebookReport.find({"user_id": user_id}).to_list(),
    )
    return documents, reports


async def create_note(
    notebook_id: UUID, payload: NoteCreate, current_user: User
) -> NotebookDocument:
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
    await asyncio.gather(document.insert(), report.insert())
    return document


async def create_pending_report(
    notebook_id: UUID,
    payload: ReportGenerateRequest,
    current_user: User,
    settings: Settings,
) -> tuple[NotebookReport, str, str | None, str | None, int | None]:
    notebook = await get_notebook(notebook_id, current_user)

    if not chat_provider_is_configured():
        raise LLMNotConfiguredError("openrouter")

    await check_quota_and_raise(current_user.id, 0, settings)

    context = await build_report_context(notebook, current_user)
    if not context:
        raise NoIndexedDocumentsError()

    instructions = (payload.additional_instructions or "").strip() or None
    if payload.report_type == "custom" and not instructions:
        raise CustomReportMissingInstructionsError()

    question_count: int | None = None
    if payload.report_type in ("quiz", "flashcards"):
        raw = (
            payload.number_of_questions
            if payload.report_type == "quiz"
            else payload.number_of_cards
        )
        question_count = _QUESTION_COUNT_MAP.get(
            (raw or "standard").strip().lower(), 20
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
    return report, context, instructions, payload.detail_level, question_count


async def cancel_report(
    notebook_id: UUID, report_id: UUID, current_user: User
) -> NotebookReport:
    notebook = await get_notebook(notebook_id, current_user)
    report = await get_notebook_report(notebook, report_id, current_user)

    if report.status not in ("pending", "generating"):
        raise CannotCancelReportError(report.status)

    report.status = "cancelled"
    report.updated_at = datetime.now(UTC)
    await report.save()
    await domain_event_bus.emit(ReportCancelled(report))
    return report


async def delete_report(notebook_id: UUID, report_id: UUID, current_user: User) -> None:
    notebook = await get_notebook(notebook_id, current_user)
    report = await get_notebook_report(notebook, report_id, current_user)

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
                    await asyncio.gather(
                        NotebookDocumentChunk.find(
                            {"document_id": document.id}
                        ).delete(),
                        document.delete(),
                    )
            except Exception:
                _logger.exception(
                    "Failed to delete corresponding note document %s", doc_id_str
                )

    await report.delete()


async def list_reports(notebook_id: UUID, current_user: User) -> list[NotebookReport]:
    notebook = await get_notebook(notebook_id, current_user)
    return (
        await NotebookReport.find(
            {"notebook_id": notebook.id, "user_id": current_user.id}
        )
        .sort(("created_at", SortDirection.DESCENDING))
        .to_list()
    )


async def get_report(
    notebook_id: UUID, report_id: UUID, current_user: User
) -> NotebookReport:
    notebook = await get_notebook(notebook_id, current_user)
    return await get_notebook_report(notebook, report_id, current_user)


async def get_chunks_by_filename(
    notebook_id: UUID, filename: str, current_user: User
) -> list[dict[str, object]]:
    notebook = await get_notebook(notebook_id, current_user)
    document = await NotebookDocument.find_one(
        {"notebook_id": notebook.id, "filename": filename, "user_id": current_user.id},
    )
    if document is None:
        raise DocumentNotFoundError()
    return await _fetch_and_serialize_chunks(document)


async def get_chunks_by_document_id(
    notebook_id: UUID, document_id: UUID, current_user: User
) -> list[dict[str, object]]:
    notebook = await get_notebook(notebook_id, current_user)
    document = await get_notebook_document(notebook, document_id, current_user)
    return await _fetch_and_serialize_chunks(document)


async def get_single_chunk(
    notebook_id: UUID, document_id: UUID, chunk_index: int, current_user: User
) -> dict[str, object]:
    notebook = await get_notebook(notebook_id, current_user)
    document = await get_notebook_document(notebook, document_id, current_user)
    chunk = await NotebookDocumentChunk.find_one(
        {"document_id": document.id, "chunk_index": chunk_index},
    )
    if chunk is None:
        raise ChunkNotFoundError()
    return {
        "id": str(chunk.id),
        "document_id": str(chunk.document_id),
        "filename": document.filename,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "metadata": chunk.chunk_metadata,
    }


async def build_chunk_image_url(
    notebook_id: UUID,
    document_id: UUID,
    chunk_index: int,
    current_user: User,
    settings: Settings,
) -> dict[str, str]:
    notebook = await get_notebook(notebook_id, current_user)
    document = await get_notebook_document(notebook, document_id, current_user)
    chunk = await NotebookDocumentChunk.find_one(
        {"document_id": document.id, "chunk_index": chunk_index},
    )
    if chunk is None:
        raise ChunkNotFoundError()
    if chunk.chunk_metadata.get("chunk_type") != "image":
        raise ChunkNotAnImageError()
    s3_key = chunk.chunk_metadata.get("s3_key")
    if not s3_key:
        raise ImageNotFoundError()
    url = generate_presigned_get_url(settings, key=str(s3_key))
    return {"url": url}
