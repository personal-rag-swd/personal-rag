"""In-app note creation.

A note is persisted as both a ``NotebookDocument`` (so it flows through the
ingestion/retrieval pipeline via its ``content``) and a completed
``NotebookReport`` of type ``note`` (so it surfaces in the reports list). The
two are linked by ``document_id`` stored in the report content.
"""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.notebooks.models import NotebookDocument, NotebookReport
from app.notebooks.schemas import NoteCreate
from app.notebooks.service.notebooks import get_notebook
from app.users.models import User


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
