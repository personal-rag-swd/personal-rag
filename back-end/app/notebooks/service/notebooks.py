"""Notebook lifecycle operations: create, read, update, delete, metrics.

``get_notebook`` is the shared ownership guard used across the notebooks
service package — every operation scoped to a notebook resolves it through
here so the ``{"_id": ..., "user_id": ...}`` filter lives in one place.
"""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from beanie import SortDirection
from pydantic_ai.messages import ModelRequest

from app.notebooks.exceptions import NotebookNotFoundError
from app.notebooks.memory import load_notebook_chat_history
from app.notebooks.models import (
    Notebook,
    NotebookDocument,
    NotebookDocumentChunk,
    NotebookMessage,
    NotebookReport,
)
from app.notebooks.schemas import (
    NotebookCreate,
    NotebookPopulateRead,
    NotebookUpdate,
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


async def clear_notebook_chat_history(notebook_id: UUID, current_user: User) -> None:
    """Delete all persisted chat messages for a notebook, leaving it intact."""
    notebook = await get_notebook(notebook_id, current_user)
    await NotebookMessage.find({"notebook_id": notebook.id}).delete()


async def get_user_event_snapshot(
    user_id: UUID,
) -> tuple[list[NotebookDocument], list[NotebookReport]]:
    documents, reports = await asyncio.gather(
        NotebookDocument.find({"user_id": user_id}).to_list(),
        NotebookReport.find({"user_id": user_id}).to_list(),
    )
    return documents, reports
