from __future__ import annotations

import logging
from datetime import UTC, datetime
from datetime import timedelta
from typing import Any
from uuid import UUID

from botocore.exceptions import ClientError
from sqlalchemy import case
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, delete, select, update

from app.core.config import Settings, validate_rag_embedding_dimension
from app.core.s3 import get_s3_client
from app.notebooks.models import Notebook, NotebookDocument, NotebookDocumentChunk
from app.notebooks.tools.chunking import ChunkingRequest, chunk_document
from app.notebooks.tools.embeddings import embed_texts
from app.users.models import User

logger = logging.getLogger(__name__)

INGESTIBLE_STATUSES = {"pending", "uploaded"}
CLAIMABLE_DOCUMENT_STATUSES = {"pending", "uploaded"}
INGESTION_FAILED_MESSAGE = "Ingestion timed out while processing. Please retry the upload."
UPLOAD_FAILED_MESSAGE = "Upload timed out. The file was not received by storage. Please retry the upload."


class TransientIngestionError(RuntimeError):
    """A retryable ingestion error that should trigger message requeue."""


def fail_stale_processing_documents(
    session: Session,
    settings: Settings,
) -> int:
    timeout_threshold = datetime.now(UTC) - timedelta(
        minutes=settings.file_ingestion_processing_timeout_minutes,
    )
    stale_docs = list(
        session.exec(
            select(NotebookDocument)
            .where(NotebookDocument.status == "processing")
            .where(NotebookDocument.updated_at <= timeout_threshold)
        )
    )
    if not stale_docs:
        return 0
    now = datetime.now(UTC)
    for doc in stale_docs:
        doc.status = "failed"
        doc.error_message = INGESTION_FAILED_MESSAGE
        doc.updated_at = now
        session.add(doc)
    session.commit()
    logger.warning("Marked %s stale processing documents as failed", len(stale_docs))
    return len(stale_docs)


def fail_stale_pending_documents(
    session: Session,
    settings: Settings,
) -> int:
    timeout_threshold = datetime.now(UTC) - timedelta(
        minutes=settings.file_ingestion_processing_timeout_minutes,
    )
    stale_docs = list(
        session.exec(
            select(NotebookDocument)
            .where(NotebookDocument.status == "pending")
            .where(NotebookDocument.created_at <= timeout_threshold)
        )
    )
    if not stale_docs:
        return 0
    now = datetime.now(UTC)
    for doc in stale_docs:
        doc.status = "failed"
        doc.error_message = UPLOAD_FAILED_MESSAGE
        doc.updated_at = now
        session.add(doc)
    session.commit()
    logger.warning("Marked %s stale pending documents as failed", len(stale_docs))
    return len(stale_docs)


def register_pending_notebook_document(
    session: Session,
    *,
    notebook: Notebook,
    current_user: User,
    bucket: str,
    key: str,
    filename: str,
    content_type: str | None,
) -> NotebookDocument:
    document = NotebookDocument(
        notebook_id=notebook.id,
        user_id=current_user.id,
        s3_bucket=bucket,
        s3_key=key,
        filename=filename,
        content_type=content_type,
        status="pending",
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def _is_missing_object_error(exc: ClientError) -> bool:
    code = str(exc.response.get("Error", {}).get("Code", "")).lower()
    status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return status_code == 404 or code in {"404", "nosuchkey", "notfound"}


def mark_pending_document_uploaded_if_object_exists(
    session: Session,
    document: NotebookDocument,
    settings: Settings,
    *,
    s3_client: Any | None = None,
) -> bool:
    """Promote a pending upload only after object storage confirms the key exists."""
    if document.status != "pending":
        return document.status == "uploaded"

    s3_client = s3_client or get_s3_client(settings)
    try:
        metadata = s3_client.head_object(Bucket=document.s3_bucket, Key=document.s3_key)
    except ClientError as exc:
        if _is_missing_object_error(exc):
            logger.debug("Notebook document upload is not visible yet: %s", document.id)
            return False
        raise

    document.status = "uploaded"
    document.size = metadata.get("ContentLength")
    document.error_message = None
    document.updated_at = datetime.now(UTC)
    session.add(document)
    session.commit()
    return True


def process_unprocessed_notebook_documents(
    session: Session,
    settings: Settings,
    *,
    limit: int = 20,
) -> dict[str, int]:
    """Poll pending/uploaded documents and ingest every object that is available."""
    validate_rag_embedding_dimension(settings)
    stats = {"checked": 0, "uploaded": 0, "ingested": 0, "skipped": 0, "recovered": 0}
    stats["recovered"] = (
        fail_stale_processing_documents(session, settings)
        + fail_stale_pending_documents(session, settings)
    )
    statement = (
        select(NotebookDocument)
        .where(NotebookDocument.status.in_(INGESTIBLE_STATUSES))
        .order_by(
            case(
                (NotebookDocument.status == "uploaded", 0),
                (NotebookDocument.status == "pending", 1),
                else_=2,
            ),
            NotebookDocument.created_at,
        )
        .limit(limit)
    )
    documents = list(session.exec(statement))
    s3_client = get_s3_client(settings) if documents else None

    for document in documents:
        stats["checked"] += 1
        if document.status == "pending":
            if not mark_pending_document_uploaded_if_object_exists(
                session,
                document,
                settings,
                s3_client=s3_client,
            ):
                stats["skipped"] += 1
                continue
            stats["uploaded"] += 1

        ingest_document_by_id(session, document.id, settings, s3_client=s3_client)
        stats["ingested"] += 1

    return stats


def claim_document_for_ingestion(
    session: Session,
    document_id: UUID,
    *,
    size: int | None = None,
) -> NotebookDocument | None:
    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "status": "processing",
        "error_message": None,
        "updated_at": now,
    }
    if size is not None:
        values["size"] = size

    result = session.exec(
        update(NotebookDocument)
        .where(NotebookDocument.id == document_id)
        .where(NotebookDocument.status.in_(CLAIMABLE_DOCUMENT_STATUSES))
        .values(**values)
    )
    if result.rowcount == 0:
        session.rollback()
        return None

    session.commit()
    return session.get(NotebookDocument, document_id)


def mark_document_upload_failed(
    session: Session,
    *,
    key: str,
    user_id: UUID,
    error_message: str | None = None,
) -> bool:
    statement = select(NotebookDocument).where(
        NotebookDocument.s3_key == key,
        NotebookDocument.user_id == user_id,
    )
    document = session.exec(statement).first()
    if document is None:
        return False
    if document.status in {"indexed", "processing", "uploaded"}:
        return True
    document.status = "failed"
    document.error_message = (error_message or "Upload failed before object storage accepted the file.")[:4000]
    document.updated_at = datetime.now(UTC)
    session.add(document)
    session.commit()
    return True


def ingest_document_by_id(
    session: Session,
    document_id: UUID,
    settings: Settings,
    *,
    s3_client: Any | None = None,
    require_processing_status: bool = False,
) -> None:
    validate_rag_embedding_dimension(settings)
    document = session.get(NotebookDocument, document_id)
    if document is None:
        return
    if require_processing_status and document.status != "processing":
        logger.info(
            "Skipping document ingestion for %s because status is %s",
            document_id,
            document.status,
        )
        return
    if document.status in CLAIMABLE_DOCUMENT_STATUSES:
        document.status = "processing"
        document.error_message = None
        document.updated_at = datetime.now(UTC)
        session.add(document)
        session.commit()

    try:
        s3_client = s3_client or get_s3_client(settings)
        obj = s3_client.get_object(Bucket=document.s3_bucket, Key=document.s3_key)
        body = obj["Body"].read()
        split_docs = chunk_document(
            ChunkingRequest(
                content=body,
                filename=document.filename,
                source=document.s3_key,
                document_id=str(document.id),
            ),
            settings,
        )
        chunk_texts = [doc.page_content for doc in split_docs]
        if not chunk_texts:
            raise ValueError("No extractable text content in document")
        if len("".join(chunk_texts).strip()) < 20:
            logger.warning("Extracted unusually small text content from %s", document.filename)

        embeddings = embed_texts(chunk_texts, settings)

        session.exec(delete(NotebookDocumentChunk).where(NotebookDocumentChunk.document_id == document.id))
        now = datetime.now(UTC)
        for idx, split_doc in enumerate(split_docs):
            session.add(
                NotebookDocumentChunk(
                    document_id=document.id,
                    chunk_index=idx,
                    content=split_doc.page_content,
                    chunk_metadata=split_doc.metadata,
                    embedding=embeddings[idx],
                    created_at=now,
                    updated_at=now,
                )
            )

        document.status = "indexed"
        document.error_message = None
        document.updated_at = now
        session.add(document)
        session.commit()
    except Exception as exc:  # pragma: no cover - error path exercised by tests via status check
        session.rollback()
        if isinstance(exc, (ClientError, SQLAlchemyError)):
            logger.exception("Notebook document ingestion hit a transient error for %s", document_id)
            document = session.get(NotebookDocument, document_id)
            if document is not None:
                document.status = "uploaded"
                document.error_message = None
                document.updated_at = datetime.now(UTC)
                session.add(document)
                session.commit()
            raise TransientIngestionError(str(exc)) from exc
        logger.exception("Notebook document ingestion failed for %s", document_id)
        document = session.get(NotebookDocument, document_id)
        if document is not None:
            document.status = "failed"
            document.error_message = str(exc)[:4000]
            document.updated_at = datetime.now(UTC)
            session.add(document)
            session.commit()
