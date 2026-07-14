"""Report lifecycle: context assembly, pending-report creation, background
generation, and cancel/delete/list operations.

Generation is intentionally decomposed:

- ``_reload_active_report`` centralizes the "re-fetch and bail if the report
  vanished or was cancelled" guard that punctuates the async generation flow.
- ``_mark_report_failed`` centralizes the failure transition + ``ReportFailed``
  emission shared by every error branch.
- ``_REPORT_GENERATORS`` maps a report type to its generator so adding a type
  is a registry entry, not another ``match`` arm.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from beanie import SortDirection
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import BinaryContent

from app.billing.service import check_quota_and_raise, record_usage_event
from app.core.config import Settings, get_settings
from app.core.event_bus import domain_event_bus
from app.core.llm_provider import chat_provider_is_configured
from app.core.s3 import get_s3_store
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
    CustomReportMissingInstructionsError,
    LLMNotConfiguredError,
    NoIndexedDocumentsError,
    ReportNotFoundError,
)
from app.notebooks.models import (
    Notebook,
    NotebookDocument,
    NotebookDocumentChunk,
    NotebookReport,
)
from app.notebooks.prompt.context_prompts import source_block
from app.notebooks.rag.image_context import build_image_parts
from app.notebooks.rag.search_service import RetrievedChunk
from app.notebooks.schemas import (
    BlogPostReport,
    BriefingDocReport,
    CustomReport,
    FlashcardReport,
    MindMapReport,
    QuizReport,
    ReportGenerateRequest,
    StudyGuideReport,
)
from app.notebooks.service.notebooks import get_notebook
from app.users.models import User

_logger = logging.getLogger(__name__)

_REPORT_CONTEXT_CHAR_LIMIT = 120_000
_QUESTION_COUNT_MAP = {"fewer": 10, "standard": 20, "more": 30}

ReportContent = (
    BriefingDocReport
    | StudyGuideReport
    | BlogPostReport
    | CustomReport
    | MindMapReport
    | QuizReport
    | FlashcardReport
)

# A generator receives the normalized (context, instructions, detail_level,
# question_count) tuple; each adapter forwards only what its agent needs.
ReportGenerator = Callable[
    ["ReportContext", str | None, str | None, int | None], Awaitable[ReportContent]
]


@dataclass(frozen=True)
class ReportContext:
    """Report source material: the text source blocks plus, for PDFs with
    embedded figures, a capped set of image chunks' actual bytes so reports
    are grounded in what a chart shows, not just its stored description.
    """

    text: str
    image_parts: list[str | BinaryContent] = field(default_factory=list)


@dataclass(frozen=True)
class PendingReportPlan:
    """Everything the background task needs to generate a freshly-created report."""

    report: NotebookReport
    context: ReportContext
    instructions: str | None
    detail_level: str | None
    question_count: int | None


async def get_notebook_report(
    notebook: Notebook, report_id: UUID, current_user: User
) -> NotebookReport:
    report = await NotebookReport.find_one(
        {"_id": report_id, "notebook_id": notebook.id, "user_id": current_user.id},
    )
    if report is None:
        raise ReportNotFoundError()
    return report


async def build_report_context(
    notebook: Notebook, current_user: User, settings: Settings
) -> ReportContext:
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
        return ReportContext(text="")

    doc_map = {str(d.id): d.filename for d in documents}
    doc_ids = [d.id for d in documents]

    chunks = (
        await NotebookDocumentChunk.find({"document_id": {"$in": doc_ids}})
        .sort(("chunk_index", SortDirection.ASCENDING))
        .to_list()
    )

    parts: list[str] = []
    total = 0
    retrieved_image_chunks: list[RetrievedChunk] = []
    for chunk in chunks:
        metadata = chunk.chunk_metadata or {}
        is_image = metadata.get("chunk_type") == "image"
        retrieved_chunk = RetrievedChunk(
            document_id=chunk.document_id,
            filename=doc_map.get(str(chunk.document_id), "unknown"),
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            metadata=metadata,
            chunk_type="image" if is_image else "text",
        )
        # Same SOURCE grammar as chat context blocks, so models see one
        # labeling convention and any citations they emit resolve the same way.
        block = source_block(retrieved_chunk)
        if total + len(block) > _REPORT_CONTEXT_CHAR_LIMIT:
            break
        parts.append(block)
        total += len(block)
        if (
            is_image
            and len(retrieved_image_chunks) < settings.notebook_report_max_images
        ):
            retrieved_image_chunks.append(retrieved_chunk)

    text = "\n\n".join(parts)
    if not retrieved_image_chunks:
        return ReportContext(text=text)

    store = get_s3_store(settings)
    image_parts = await build_image_parts(retrieved_image_chunks, None, store)
    return ReportContext(text=text, image_parts=image_parts)


async def _generate_briefing(
    context: ReportContext,
    instructions: str | None,
    _detail: str | None,
    _count: int | None,
) -> ReportContent:
    return await generate_briefing_doc(context, instructions)


async def _generate_study_guide(
    context: ReportContext,
    instructions: str | None,
    _detail: str | None,
    _count: int | None,
) -> ReportContent:
    return await generate_study_guide(context, instructions)


async def _generate_blog(
    context: ReportContext,
    instructions: str | None,
    _detail: str | None,
    _count: int | None,
) -> ReportContent:
    return await generate_blog_post(context, instructions)


async def _generate_custom(
    context: ReportContext,
    instructions: str | None,
    _detail: str | None,
    _count: int | None,
) -> ReportContent:
    return await generate_custom_report(context, instructions or "")


async def _generate_mindmap(
    context: ReportContext,
    instructions: str | None,
    detail: str | None,
    _count: int | None,
) -> ReportContent:
    return await generate_mindmap(context, detail, instructions)


async def _generate_quiz(
    context: ReportContext,
    instructions: str | None,
    detail: str | None,
    count: int | None,
) -> ReportContent:
    return await generate_quiz(
        context,
        count=count or 20,
        difficulty=detail,
        additional_instructions=instructions,
    )


async def _generate_flashcards(
    context: ReportContext,
    instructions: str | None,
    detail: str | None,
    count: int | None,
) -> ReportContent:
    return await generate_flashcards(
        context,
        count=count or 20,
        difficulty=detail,
        additional_instructions=instructions,
    )


_REPORT_GENERATORS: dict[str, ReportGenerator] = {
    "briefing": _generate_briefing,
    "study_guide": _generate_study_guide,
    "blog": _generate_blog,
    "custom": _generate_custom,
    "mindmap": _generate_mindmap,
    "quiz": _generate_quiz,
    "flashcards": _generate_flashcards,
}


async def _reload_active_report(report_id: UUID) -> NotebookReport | None:
    """Re-fetch a report, returning None if it vanished or was cancelled mid-run."""
    report = await NotebookReport.find_one({"_id": report_id})
    if report is None or report.status == "cancelled":
        return None
    return report


async def _mark_report_failed(report_id: UUID, message: str) -> None:
    """Transition a still-active report to ``failed`` and emit ``ReportFailed``."""
    report = await _reload_active_report(report_id)
    if report is None:
        return
    report.status = "failed"
    report.error_message = message
    report.updated_at = datetime.now(UTC)
    await report.save()
    await domain_event_bus.emit(ReportFailed(report))


def _model_http_error_message(exc: ModelHTTPError) -> str:
    if exc.status_code == 429:
        return (
            "The AI provider rate limit was exceeded. "
            "Please wait a moment and try again."
        )
    return "The AI provider failed to generate the report. Please try again."


async def run_report_generation(
    report_id: UUID,
    report_type: str,
    context: ReportContext,
    instructions: str | None,
    detail_level: str | None,
    question_count: int | None = None,
) -> None:
    report = await _reload_active_report(report_id)
    if report is None:
        return

    report.status = "generating"
    report.updated_at = datetime.now(UTC)
    await report.save()
    await domain_event_bus.emit(ReportGenerating(report))

    if await _reload_active_report(report_id) is None:
        return

    generator = _REPORT_GENERATORS.get(report_type)
    if generator is None:
        _logger.error("Unknown report type: %s", report_type)
        await _mark_report_failed(report_id, f"Unknown report type: {report_type}")
        return

    try:
        report_content = await generator(
            context, instructions, detail_level, question_count
        )
    except ModelHTTPError as exc:
        await _mark_report_failed(report_id, _model_http_error_message(exc))
        return
    except Exception:
        _logger.exception("Unexpected error during report generation")
        await _mark_report_failed(
            report_id, "An unexpected error occurred during report generation."
        )
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

    report = await _reload_active_report(report_id)
    if report is None:
        return

    report.status = "completed"
    report.content = report_content.model_dump()
    report.updated_at = datetime.now(UTC)
    await report.save()
    await domain_event_bus.emit(ReportCompleted(report))


def _resolve_question_count(payload: ReportGenerateRequest) -> int | None:
    if payload.report_type not in ("quiz", "flashcards"):
        return None
    raw = (
        payload.number_of_questions
        if payload.report_type == "quiz"
        else payload.number_of_cards
    )
    return _QUESTION_COUNT_MAP.get((raw or "standard").strip().lower(), 20)


async def create_pending_report(
    notebook_id: UUID,
    payload: ReportGenerateRequest,
    current_user: User,
    settings: Settings,
) -> PendingReportPlan:
    notebook = await get_notebook(notebook_id, current_user)

    if not chat_provider_is_configured():
        raise LLMNotConfiguredError("openrouter")

    await check_quota_and_raise(current_user.id, 0, settings)

    context = await build_report_context(notebook, current_user, settings)
    if not context.text:
        raise NoIndexedDocumentsError()

    instructions = (payload.additional_instructions or "").strip() or None
    if payload.report_type == "custom" and not instructions:
        raise CustomReportMissingInstructionsError()

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
    return PendingReportPlan(
        report=report,
        context=context,
        instructions=instructions,
        detail_level=payload.detail_level,
        question_count=_resolve_question_count(payload),
    )


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
        await _delete_note_document(
            notebook, report.content.get("document_id"), current_user
        )

    await report.delete()


async def _delete_note_document(
    notebook: Notebook, doc_id_str: object, current_user: User
) -> None:
    """Best-effort deletion of the ``NotebookDocument`` backing a deleted note."""
    if not doc_id_str:
        return
    try:
        doc_id = UUID(str(doc_id_str))
        document = await NotebookDocument.find_one(
            {"_id": doc_id, "notebook_id": notebook.id, "user_id": current_user.id},
        )
        if document:
            await NotebookDocumentChunk.find({"document_id": document.id}).delete()
            await document.delete()
    except Exception:
        _logger.exception("Failed to delete corresponding note document %s", doc_id_str)


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
