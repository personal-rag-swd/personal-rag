from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from pydantic_ai.exceptions import ModelHTTPError
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.core.config import get_settings
from app.notebooks.agent import (
    chat_provider_is_configured,
    generate_blog_post,
    generate_briefing_doc,
    generate_custom_report,
    generate_mindmap,
    generate_study_guide,
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
    MindMapReport,
    ReportGenerateRequest,
    StudyGuideReport,
)
from app.users.models import User

logger = logging.getLogger(__name__)

# ~120 k chars ~= 30 k tokens, comfortably within current model limits.
REPORT_CONTEXT_CHAR_LIMIT = 120_000


def ensure_report_generation_available() -> None:
    if chat_provider_is_configured():
        return

    provider = get_settings().chat_provider.strip().lower()
    raise RuntimeError(
        f"LLM service is not configured. Set the API key for the '{provider}' chat provider."
    )


def build_report_context(
    session: Session, notebook: Notebook, current_user: User
) -> str:
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
        if total + len(block) > REPORT_CONTEXT_CHAR_LIMIT:
            break
        parts.append(block)
        total += len(block)

    return "\n\n".join(parts)


def validate_report_request(payload: ReportGenerateRequest) -> str | None:
    instructions = (payload.additional_instructions or "").strip() or None
    if payload.report_type == "custom" and not instructions:
        raise ValueError(
            "additional_instructions is required for report_type 'custom'."
        )
    return instructions


def create_pending_report(
    session: Session,
    notebook: Notebook,
    current_user: User,
    payload: ReportGenerateRequest,
    instructions: str | None,
) -> NotebookReport:
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
        raise RuntimeError("Database error") from exc
    return report


async def run_report_generation(
    report_id: UUID,
    report_type: str,
    context: str,
    instructions: str | None,
    detail_level: str | None,
    _engine: object | None = None,
) -> None:
    from app.core.database import engine as default_engine

    db_engine = _engine or default_engine
    with Session(db_engine) as session:
        report = session.get(NotebookReport, report_id)
        if report is None or report.status == "cancelled":
            return

        report.status = "generating"
        report.updated_at = datetime.now(UTC)
        session.add(report)
        session.commit()

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
                    report.error_message = (
                        "The AI provider rate limit was exceeded. Please wait a moment and try again."
                    )
                else:
                    report.error_message = (
                        "The AI provider failed to generate the report. Please try again."
                    )
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

        session.expire_all()
        report = session.get(NotebookReport, report_id)
        if report is None or report.status == "cancelled":
            return

        report.status = "completed"
        report.content = report_content.model_dump()
        report.updated_at = datetime.now(UTC)
        session.add(report)
        session.commit()


def list_reports(
    session: Session, notebook: Notebook, current_user: User
) -> list[NotebookReport]:
    return list(
        session.exec(
            select(NotebookReport)
            .where(NotebookReport.notebook_id == notebook.id)
            .where(NotebookReport.user_id == current_user.id)
            .order_by(NotebookReport.created_at.desc())
        ).all()
    )


def get_report(
    session: Session, notebook: Notebook, current_user: User, report_id: UUID
) -> NotebookReport:
    report = session.exec(
        select(NotebookReport).where(
            NotebookReport.id == report_id,
            NotebookReport.notebook_id == notebook.id,
            NotebookReport.user_id == current_user.id,
        )
    ).first()
    if report is None:
        raise LookupError("Report not found")
    return report


def cancel_report(
    session: Session, notebook: Notebook, current_user: User, report_id: UUID
) -> NotebookReport:
    report = get_report(session, notebook, current_user, report_id)
    if report.status not in ("pending", "generating"):
        raise ValueError(f"Cannot cancel report with status '{report.status}'.")

    report.status = "cancelled"
    report.updated_at = datetime.now(UTC)
    try:
        session.add(report)
        session.commit()
        session.refresh(report)
    except SQLAlchemyError as exc:
        session.rollback()
        raise RuntimeError("Database error") from exc
    return report


def delete_report(
    session: Session, notebook: Notebook, current_user: User, report_id: UUID
) -> None:
    report = get_report(session, notebook, current_user, report_id)
    try:
        session.delete(report)
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise RuntimeError("Database error") from exc


async def recover_pending_reports() -> None:
    from app.core.database import engine

    logger = logging.getLogger("app.startup")

    try:
        with Session(engine) as session:
            stuck_reports = list(
                session.exec(
                    select(NotebookReport).where(
                        NotebookReport.status.in_(["pending", "generating"])
                    )
                ).all()
            )

            if not stuck_reports:
                return

            logger.info(
                "Recovering %d pending/generating report(s) after restart",
                len(stuck_reports),
            )

            recovered_tasks: set[asyncio.Task[None]] = set()
            for report in stuck_reports:
                if report.status == "generating":
                    report.status = "pending"
                    session.add(report)
                    session.commit()

                notebook = session.get(Notebook, report.notebook_id)
                user = session.get(User, report.user_id)
                if notebook is None or user is None:
                    logger.warning(
                        "Skipping report %s: notebook or user not found",
                        report.id,
                    )
                    report.status = "failed"
                    report.error_message = (
                        "Recovery failed: associated notebook or user no longer exists."
                    )
                    session.add(report)
                    session.commit()
                    continue

                context = build_report_context(session, notebook, user)
                if not context:
                    logger.warning(
                        "Skipping report %s: no indexed documents available for context",
                        report.id,
                    )
                    report.status = "failed"
                    report.error_message = (
                        "Recovery failed: no indexed documents found."
                    )
                    session.add(report)
                    session.commit()
                    continue

                task = asyncio.create_task(
                    run_report_generation(
                        report_id=report.id,
                        report_type=report.report_type,
                        context=context,
                        instructions=report.additional_instructions,
                        detail_level=report.detail_level,
                        _engine=engine,
                    )
                )
                recovered_tasks.add(task)
                task.add_done_callback(recovered_tasks.discard)
                logger.info(
                    "Re-queued report %s (type=%s)", report.id, report.report_type
                )
    except Exception:
        logger.exception("Failed to recover pending reports")
