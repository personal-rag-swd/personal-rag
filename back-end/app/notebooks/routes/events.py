from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.core.database import get_session
from app.notebooks.models import NotebookDocument, NotebookReport
from app.notebooks.schemas import NotebookDocumentRead, NotebookReportRead
from app.users.dependencies import get_current_user
from app.users.models import User

router = APIRouter()


@router.get("/events", summary="Stream notebook document and report updates")
async def read_notebook_events(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    once: bool = False,
) -> StreamingResponse:
    async def event_generator() -> AsyncIterator[str]:
        last_doc_state: dict[UUID, tuple[str, datetime, UUID]] = {}
        last_report_state: dict[UUID, tuple[str, datetime, str, UUID]] = {}
        first_tick = True

        try:
            while True:
                docs = session.exec(
                    select(NotebookDocument).where(
                        NotebookDocument.user_id == current_user.id
                    )
                ).all()
                reports = session.exec(
                    select(NotebookReport).where(
                        NotebookReport.user_id == current_user.id
                    )
                ).all()

                if first_tick:
                    by_notebook: dict[UUID, list[NotebookDocument]] = {}
                    for doc in docs:
                        by_notebook.setdefault(doc.notebook_id, []).append(doc)

                    for notebook_id, notebook_docs in by_notebook.items():
                        serialized_docs = [
                            NotebookDocumentRead.model_validate(doc).model_dump(
                                mode="json"
                            )
                            for doc in notebook_docs
                        ]
                        yield (
                            "data: "
                            + json.dumps(
                                {
                                    "type": "snapshot",
                                    "notebook_id": str(notebook_id),
                                    "documents": serialized_docs,
                                    "timestamp": datetime.now(UTC).isoformat(),
                                }
                            )
                            + "\n\n"
                        )

                    last_doc_state = {
                        doc.id: (doc.status, doc.updated_at, doc.notebook_id)
                        for doc in docs
                    }

                    reports_by_notebook: dict[UUID, list[NotebookReport]] = {}
                    for report in reports:
                        reports_by_notebook.setdefault(report.notebook_id, []).append(
                            report
                        )

                    for notebook_id, notebook_reports in reports_by_notebook.items():
                        serialized_reports = [
                            NotebookReportRead.model_validate(report).model_dump(
                                mode="json"
                            )
                            for report in notebook_reports
                        ]
                        yield (
                            "data: "
                            + json.dumps(
                                {
                                    "type": "report_snapshot",
                                    "notebook_id": str(notebook_id),
                                    "reports": serialized_reports,
                                    "timestamp": datetime.now(UTC).isoformat(),
                                }
                            )
                            + "\n\n"
                        )

                    last_report_state = {
                        report.id: (
                            report.status,
                            report.updated_at,
                            report.report_type,
                            report.notebook_id,
                        )
                        for report in reports
                    }
                    if not by_notebook and not reports_by_notebook:
                        yield ": keep-alive\n\n"
                    first_tick = False
                    if once:
                        return
                else:
                    current_doc_ids: set[UUID] = set()
                    for doc in docs:
                        current_doc_ids.add(doc.id)
                        previous_state = last_doc_state.get(doc.id)
                        if previous_state is None or previous_state[:2] != (
                            doc.status,
                            doc.updated_at,
                        ):
                            serialized_doc = NotebookDocumentRead.model_validate(
                                doc
                            ).model_dump(mode="json")
                            yield (
                                "data: "
                                + json.dumps(
                                    {
                                        "type": "document_update",
                                        "notebook_id": str(doc.notebook_id),
                                        "document": serialized_doc,
                                        "timestamp": datetime.now(UTC).isoformat(),
                                    }
                                )
                                + "\n\n"
                            )
                            last_doc_state[doc.id] = (
                                doc.status,
                                doc.updated_at,
                                doc.notebook_id,
                            )

                    removed_doc_ids = set(last_doc_state) - current_doc_ids
                    for removed_doc_id in removed_doc_ids:
                        del last_doc_state[removed_doc_id]

                    current_report_ids: set[UUID] = set()
                    for report in reports:
                        current_report_ids.add(report.id)
                        previous_state = last_report_state.get(report.id)
                        if previous_state is None or previous_state[:2] != (
                            report.status,
                            report.updated_at,
                        ):
                            serialized_report = NotebookReportRead.model_validate(
                                report
                            ).model_dump(mode="json")
                            yield (
                                "data: "
                                + json.dumps(
                                    {
                                        "type": "report_update",
                                        "notebook_id": str(report.notebook_id),
                                        "report": serialized_report,
                                        "timestamp": datetime.now(UTC).isoformat(),
                                    }
                                )
                                + "\n\n"
                            )
                            last_report_state[report.id] = (
                                report.status,
                                report.updated_at,
                                report.report_type,
                                report.notebook_id,
                            )

                    removed_report_ids = set(last_report_state) - current_report_ids
                    for removed_report_id in removed_report_ids:
                        del last_report_state[removed_report_id]

                session.expire_all()
                if once:
                    return
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
