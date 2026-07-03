"""Persistence + state-machine operations for ``NotebookDocument`` rows.

This module owns every status transition (``pending → uploaded → processing →
indexed/failed``) and the domain event each transition emits. It has no
dependency on the ingestion pipeline, so callers that only need to register,
claim, or reap documents don't pull in PyMuPDF/embedding machinery.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

import obstore
from beanie.odm.queries.update import UpdateResponse

from app.core.config import Settings
from app.core.event_bus import domain_event_bus
from app.core.s3 import get_s3_store
from app.notebooks.domain_events import (
    DocumentEvent,
    DocumentFailed,
    DocumentProcessing,
    DocumentRegistered,
    DocumentUploaded,
)
from app.notebooks.models import NotebookDocument

if TYPE_CHECKING:
    from obstore.store import S3Store

logger = logging.getLogger(__name__)

CLAIMABLE_DOCUMENT_STATUSES = {"pending", "uploaded"}
INGESTION_FAILED_MESSAGE = (
    "Ingestion timed out while processing. Please retry the upload."
)
UPLOAD_FAILED_MESSAGE = (
    "Upload timed out. The file was not received by storage. Please retry the upload."
)


async def transition_document(
    document: NotebookDocument,
    status: str,
    *,
    error_message: str | None = None,
    event_cls: type[DocumentEvent],
) -> None:
    """Persist a status transition and emit its domain event."""
    document.status = status
    document.error_message = error_message
    document.updated_at = datetime.now(UTC)
    await document.save()
    await domain_event_bus.emit(event_cls(document))


async def register_pending_notebook_document(
    *,
    notebook_id: UUID,
    user_id: UUID,
    bucket: str,
    key: str,
    filename: str,
    content_type: str | None,
) -> NotebookDocument:
    document = NotebookDocument(
        notebook_id=notebook_id,
        user_id=user_id,
        s3_bucket=bucket,
        s3_key=key,
        filename=filename,
        content_type=content_type,
        status="pending",
    )
    await document.insert()
    await domain_event_bus.emit(DocumentRegistered(document))
    return document


async def mark_pending_document_uploaded_if_object_exists(
    document: NotebookDocument,
    settings: Settings,
    *,
    store: S3Store | None,
) -> bool:
    if document.status != "pending":
        return document.status == "uploaded"

    resolved_store = store or get_s3_store(settings)
    if not document.s3_bucket or not document.s3_key:
        raise ValueError(
            "Cannot check S3 object existence for a pending document without bucket/key"
        )
    try:
        metadata = await obstore.head_async(resolved_store, document.s3_key)
    except FileNotFoundError:
        logger.debug("Notebook document upload is not visible yet: %s", document.id)
        return False

    document.size = metadata["size"]
    await transition_document(document, "uploaded", event_cls=DocumentUploaded)
    return True


async def claim_document_for_ingestion(
    document_id: UUID,
    *,
    size: int | None = None,
) -> NotebookDocument | None:
    set_fields: dict[str, Any] = {
        "status": "processing",
        "error_message": None,
        "updated_at": datetime.now(UTC),
    }
    if size is not None:
        set_fields["size"] = size
    document = cast(
        NotebookDocument | None,
        await NotebookDocument.find_one(
            {"_id": document_id, "status": {"$in": list(CLAIMABLE_DOCUMENT_STATUSES)}},
        ).update_one({"$set": set_fields}, response_type=UpdateResponse.NEW_DOCUMENT),
    )
    if document is None:
        return None
    await domain_event_bus.emit(DocumentProcessing(document))
    return document


async def mark_document_upload_failed(
    *,
    key: str,
    user_id: UUID,
    error_message: str | None = None,
) -> bool:
    document = await NotebookDocument.find_one(
        {"s3_key": key, "user_id": user_id},
    )
    if document is None:
        return False
    if document.status in {"indexed", "processing", "uploaded"}:
        return True
    await transition_document(
        document,
        "failed",
        error_message=(
            error_message or "Upload failed before object storage accepted the file."
        )[:4000],
        event_cls=DocumentFailed,
    )
    return True


async def record_ingestion_outcome(
    document_id: UUID,
    *,
    status: str,
    error_message: str | None,
    event: type[DocumentUploaded] | type[DocumentFailed],
    only_if_processing: bool = False,
) -> None:
    """Re-fetch the document and persist a terminal/transient ingestion outcome.

    The ``ingest_document_by_id`` exception handlers run after the in-hand
    ``document`` may be stale, so the row is re-read before updating. When
    ``only_if_processing`` is set, a document no longer in ``"processing"`` is
    left untouched (a concurrent handler already finalized it).
    """
    document = await NotebookDocument.find_one({"_id": document_id})
    if document is None or (only_if_processing and document.status != "processing"):
        return
    await transition_document(
        document, status, error_message=error_message, event_cls=event
    )


async def _fail_stale_documents(
    query: dict[str, Any],
    error_message: str,
    warning_log_template: str,
) -> int:
    stale_docs = await NotebookDocument.find(query).to_list()
    if not stale_docs:
        return 0
    now = datetime.now(UTC)
    await NotebookDocument.find(query).update_many(
        {
            "$set": {
                "status": "failed",
                "error_message": error_message,
                "updated_at": now,
            }
        }
    )
    for doc in stale_docs:
        doc.status = "failed"
        doc.error_message = error_message
        doc.updated_at = now
        await domain_event_bus.emit(DocumentFailed(doc))
    logger.warning(warning_log_template, len(stale_docs))
    return len(stale_docs)


def _stale_timeout_threshold(settings: Settings) -> datetime:
    return datetime.now(UTC) - timedelta(
        minutes=settings.file_ingestion_processing_timeout_minutes,
    )


async def fail_stale_processing_documents(settings: Settings) -> int:
    return await _fail_stale_documents(
        query={
            "status": "processing",
            "updated_at": {"$lte": _stale_timeout_threshold(settings)},
        },
        error_message=INGESTION_FAILED_MESSAGE,
        warning_log_template="Marked %s stale processing documents as failed",
    )


async def fail_stale_pending_documents(settings: Settings) -> int:
    return await _fail_stale_documents(
        query={
            "status": "pending",
            "created_at": {"$lte": _stale_timeout_threshold(settings)},
        },
        error_message=UPLOAD_FAILED_MESSAGE,
        warning_log_template="Marked %s stale pending documents as failed",
    )
