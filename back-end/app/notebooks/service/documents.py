"""Notebook document operations: listing, deletion, ownership lookup, and
validation of the client-supplied document scope used by chat retrieval.
"""

from uuid import UUID

from beanie import SortDirection

from app.core.config import Settings
from app.core.s3 import get_object_bytes, get_s3_store
from app.notebooks.exceptions import (
    DocumentContentUnavailableError,
    DocumentNotFoundError,
)
from app.notebooks.models import (
    Notebook,
    NotebookDocument,
    NotebookDocumentChunk,
    NotebookReport,
)
from app.notebooks.service.notebooks import get_notebook
from app.users.models import User


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


async def get_notebook_document(
    notebook: Notebook, document_id: UUID, current_user: User
) -> NotebookDocument:
    document = await NotebookDocument.find_one(
        {"_id": document_id, "notebook_id": notebook.id, "user_id": current_user.id},
    )
    if document is None:
        raise DocumentNotFoundError()
    return document


async def get_owned_document(
    notebook_id: UUID, document_id: UUID, current_user: User
) -> NotebookDocument:
    """Resolve a document by notebook + document id, verifying ownership.

    Unlike :func:`get_notebook_document`, this takes ids directly (no preloaded
    notebook) for the document byte/preview endpoints.
    """
    document = await NotebookDocument.find_one(
        {"_id": document_id, "notebook_id": notebook_id, "user_id": current_user.id},
    )
    if document is None:
        raise DocumentNotFoundError()
    return document


async def load_document_bytes(document: NotebookDocument, settings: Settings) -> bytes:
    """Return a document's raw bytes from its DB content or S3 object.

    Encapsulates the "where do the bytes live" decision shared by the download
    and PDF-inline endpoints: in-app notes carry their text in ``content``;
    everything else is fetched from object storage.
    """
    if document.content is not None:
        return document.content.encode("utf-8")
    if not document.s3_key:
        raise DocumentContentUnavailableError()
    try:
        return await get_object_bytes(get_s3_store(settings), document.s3_key)
    except FileNotFoundError as exc:
        raise DocumentNotFoundError() from exc


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
