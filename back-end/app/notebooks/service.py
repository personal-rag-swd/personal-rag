import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelRequest

from app.notebooks.agent.report_agents import (
    generate_blog_post,
    generate_briefing_doc,
    generate_custom_report,
    generate_flashcards,
    generate_mindmap,
    generate_quiz,
    generate_study_guide,
)
from app.notebooks.events import publish_report_event
from app.notebooks.memory import load_notebook_chat_history
from app.notebooks.models import (
    Notebook,
    NotebookDocument,
    NotebookDocumentChunk,
    NotebookMessage,
    NotebookReport,
)
from app.notebooks.schemas import (
    BlogPostReport,
    BriefingDocReport,
    CustomReport,
    FlashcardReport,
    MindMapReport,
    NotebookCreate,
    NotebookPopulateRead,
    NotebookUpdate,
    QuizReport,
    StudyGuideReport,
)
from app.users.models import User

_logger = logging.getLogger(__name__)


async def list_notebooks(current_user: User) -> list[Notebook]:
    return (
        await Notebook.find({"user_id": current_user.id})
        .sort(("last_active_at", -1), ("created_at", -1))
        .to_list()
    )


async def get_notebook(notebook_id: UUID, current_user: User) -> Notebook:
    notebook = await Notebook.find_one(
        {"_id": notebook_id, "user_id": current_user.id},
    )
    if notebook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found"
        )
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
        .sort(("created_at", -1))
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

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
        .sort(("filename", 1))
        .to_list()
    )

    if not documents:
        return ""

    doc_map = {str(d.id): d.filename for d in documents}
    doc_ids = [d.id for d in documents]

    chunks = (
        await NotebookDocumentChunk.find({"document_id": {"$in": doc_ids}})
        .sort(("chunk_index", 1))
        .to_list()
    )

    parts: list[str] = []
    total = 0
    for chunk in chunks:
        filename = doc_map.get(str(chunk.document_id), "unknown")
        header = f"[file={filename} chunk={chunk.chunk_index}]"
        block = f"{header}\n{chunk.content}"
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
    await publish_report_event(report)

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
                await publish_report_event(report)
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
            await publish_report_event(report)
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
            await publish_report_event(report)
        return

    report = await NotebookReport.find_one({"_id": report_id})
    if report is None or report.status == "cancelled":
        return

    report.status = "completed"
    report.content = report_content.model_dump()
    report.updated_at = datetime.now(UTC)
    await report.save()
    await publish_report_event(report)
