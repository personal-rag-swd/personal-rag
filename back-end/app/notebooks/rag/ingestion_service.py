from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from botocore.exceptions import ClientError
from bson import Binary

from app.core.config import Settings
from app.core.s3 import get_s3_client
from app.notebooks.events import publish_document_event
from app.notebooks.models import Notebook, NotebookDocument, NotebookDocumentChunk
from app.notebooks.rag.document_chunker import ChunkingRequest, chunk_document
from app.users.models import User

logger = logging.getLogger(__name__)

INGESTIBLE_STATUSES = {"pending", "uploaded"}
CLAIMABLE_DOCUMENT_STATUSES = {"pending", "uploaded"}
INGESTION_FAILED_MESSAGE = (
    "Ingestion timed out while processing. Please retry the upload."
)
UPLOAD_FAILED_MESSAGE = (
    "Upload timed out. The file was not received by storage. Please retry the upload."
)

ATLAS_VECTOR_INDEX_NAME = "notebook_chunks_vector_index"


async def _check_atlas_index_status() -> tuple[str, bool] | None:
    """Check Atlas search index status using ``list_search_indexes``.

    Returns ``(status, queryable)`` if the index is found, or ``None``
    when the API is not available (non-Atlas deployments, old driver, …).
    """
    try:
        collection = NotebookDocumentChunk.get_pymongo_collection()
        cursor = collection.list_search_indexes()
        indexes = await cursor.to_list(length=100)
    except Exception:
        return None

    for index in indexes:
        if index.get("name") == ATLAS_VECTOR_INDEX_NAME:
            return index.get("status", ""), index.get("queryable", False)
    return None


async def _is_document_vector_indexed(
    document: NotebookDocument,
) -> bool:
    """Check if the first chunk of the document has been embedded and is searchable via vector search."""
    first_chunk = await NotebookDocumentChunk.find_one(
        {"document_id": document.id},
        sort=[("chunk_index", 1)],
    )
    if first_chunk is None:
        # No chunks to index
        return True

    try:
        pipeline = [
            {
                "$vectorSearch": {
                    "index": ATLAS_VECTOR_INDEX_NAME,
                    "path": "content",
                    "query": first_chunk.content,
                    "numCandidates": 10,
                    "limit": 5,
                    "similarity": "cosine",
                    "filter": {
                        "notebook_id": Binary.from_uuid(document.notebook_id),
                        "user_id": Binary.from_uuid(document.user_id),
                    },
                }
            }
        ]
        results = await NotebookDocumentChunk.aggregate(pipeline).to_list()
        for r in results:
            if r.get("document_id") == document.id:
                return True
    except Exception as e:
        logger.warning(
            "Vector search query failed during indexing verification for document %s: %s",
            document.id,
            str(e),
        )
        # Treat query failures as "not indexed yet" so we do not promote the
        # document to indexed while Atlas/server-side embedding is still catching up.
        return False

    return False


async def wait_for_atlas_vector_index(
    document: NotebookDocument,
    wait_seconds: float = 120.0,
) -> None:
    """Wait for the Atlas ``{ATLAS_VECTOR_INDEX_NAME}`` to become ACTIVE
    and queryable, and for the document chunks to be embedded by the autoEmbed model.

    During the wait the document status is set to ``"indexing"`` so the
    existing SSE stream (``GET /notebooks/events``) pushes real-time
    updates to the client.

    If the check is not available (non-Atlas, missing index, etc.) the
    function returns immediately.  On timeout the document proceeds
    anyway with a warning.
    """
    index_status = await _check_atlas_index_status()
    if index_status is None:
        return

    # In Atlas environments, we set the status to "indexing" while we check/wait
    document.status = "indexing"
    document.updated_at = datetime.now(UTC)
    await document.save()
    await publish_document_event(document)

    start_time = datetime.now(UTC)
    deadline = start_time + timedelta(seconds=wait_seconds)
    while True:
        status, queryable = index_status
        if status == "ACTIVE" and queryable and await _is_document_vector_indexed(
            document
        ):
            logger.info(
                "Atlas vector index %s is ACTIVE and document %s chunks are embedded/searchable (waited %.1fs)",
                ATLAS_VECTOR_INDEX_NAME,
                document.filename,
                (datetime.now(UTC) - start_time).total_seconds(),
            )
            return

        if datetime.now(UTC) >= deadline:
            break

        await asyncio.sleep(5.0)

        # Refresh index status
        index_status = await _check_atlas_index_status()
        if index_status is None:
            logger.info("$listSearchIndexes became unavailable - proceeding")
            return

    logger.warning(
        "Timed out waiting for Atlas vector index %s or document %s embedding after %.0fs - "
        "proceeding anyway; vector search may return incomplete results.",
        ATLAS_VECTOR_INDEX_NAME,
        document.filename,
        wait_seconds,
    )


class TransientIngestionError(RuntimeError):
    """A retryable ingestion error that should trigger message requeue."""


async def _fail_stale_documents(
    query: dict[str, Any],
    error_message: str,
    warning_log_template: str,
) -> int:
    stale_docs = await NotebookDocument.find(query).to_list()
    if not stale_docs:
        return 0
    now = datetime.now(UTC)
    for doc in stale_docs:
        doc.status = "failed"
        doc.error_message = error_message
        doc.updated_at = now
        await doc.save()
        await publish_document_event(doc)
    logger.warning(warning_log_template, len(stale_docs))
    return len(stale_docs)


async def fail_stale_processing_documents(
    settings: Settings,
) -> int:
    timeout_threshold = datetime.now(UTC) - timedelta(
        minutes=settings.file_ingestion_processing_timeout_minutes,
    )
    return await _fail_stale_documents(
        query={"status": {"$in": ["processing", "indexing"]}, "updated_at": {"$lte": timeout_threshold}},
        error_message=INGESTION_FAILED_MESSAGE,
        warning_log_template="Marked %s stale processing/indexing documents as failed",
    )


async def fail_stale_pending_documents(
    settings: Settings,
) -> int:
    timeout_threshold = datetime.now(UTC) - timedelta(
        minutes=settings.file_ingestion_processing_timeout_minutes,
    )
    return await _fail_stale_documents(
        query={"status": "pending", "created_at": {"$lte": timeout_threshold}},
        error_message=UPLOAD_FAILED_MESSAGE,
        warning_log_template="Marked %s stale pending documents as failed",
    )


async def register_pending_notebook_document(
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
    await document.insert()
    await publish_document_event(document)
    return document


def _is_missing_object_error(exc: ClientError) -> bool:
    code = str(exc.response.get("Error", {}).get("Code", "")).lower()
    status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return status_code == 404 or code in {"404", "nosuchkey", "notfound"}


async def mark_pending_document_uploaded_if_object_exists(
    document: NotebookDocument,
    settings: Settings,
    *,
    s3_client: Any | None = None,
) -> bool:
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
    await document.save()
    await publish_document_event(document)
    return True


async def process_unprocessed_notebook_documents(
    settings: Settings,
    *,
    limit: int = 20,
) -> dict[str, int]:
    """Poll-based ingestion fallback when the RabbitMQ consumer is disabled.

    Queries MongoDB for documents in ``pending`` or ``uploaded`` status,
    verifies the S3 object exists, and triggers ingestion.  Call this
    periodically (e.g. via a background task or cron) when
    ``settings.rabbitmq_consumer_enabled`` is ``False``.
    """
    stats = {"checked": 0, "uploaded": 0, "ingested": 0, "skipped": 0, "recovered": 0}
    stats["recovered"] = await fail_stale_processing_documents(
        settings
    ) + await fail_stale_pending_documents(settings)

    uploaded_docs = await NotebookDocument.find(
        {"status": "uploaded"},
    ).sort(("created_at", 1)).limit(limit).to_list()

    pending_docs = await NotebookDocument.find(
        {"status": "pending"},
    ).sort(("created_at", 1)).limit(limit - len(uploaded_docs)).to_list()

    documents = uploaded_docs + pending_docs
    s3_client = get_s3_client(settings) if documents else None

    for document in documents:
        stats["checked"] += 1
        if document.status == "pending":
            if not await mark_pending_document_uploaded_if_object_exists(
                document,
                settings,
                s3_client=s3_client,
            ):
                stats["skipped"] += 1
                continue
            stats["uploaded"] += 1

        await ingest_document_by_id(document.id, settings, s3_client=s3_client)
        stats["ingested"] += 1

    return stats


async def claim_document_for_ingestion(
    document_id: UUID,
    *,
    size: int | None = None,
) -> NotebookDocument | None:
    document = await NotebookDocument.find_one(
        {"_id": document_id, "status": {"$in": list(CLAIMABLE_DOCUMENT_STATUSES)}},
    )
    if document is None:
        return None
    document.status = "processing"
    document.error_message = None
    document.updated_at = datetime.now(UTC)
    if size is not None:
        document.size = size
    await document.save()
    await publish_document_event(document, "document_update")
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
    document.status = "failed"
    document.error_message = (
        error_message or "Upload failed before object storage accepted the file."
    )[:4000]
    document.updated_at = datetime.now(UTC)
    await document.save()
    await publish_document_event(document)
    return True


async def _run_document_ingestion(
    document: NotebookDocument,
    settings: Settings,
    s3_client: Any,
) -> None:
    if document.content is not None:
        body = document.content.encode("utf-8")
        source_key = f"db-notes/{document.id}"
        logger.info(
            "Reading document content from database (note type) for document_id=%s, key=%s",
            document.id,
            source_key,
        )
    else:
        logger.info(
            "Fetching document content from S3: bucket=%s, key=%s",
            document.s3_bucket,
            document.s3_key,
        )
        obj = s3_client.get_object(Bucket=document.s3_bucket, Key=document.s3_key)
        body = obj["Body"].read()
        source_key = document.s3_key

    logger.info(
        "Ingesting document %s (%s bytes): starting chunking...",
        document.filename,
        len(body),
    )
    split_docs = chunk_document(
        ChunkingRequest(
            content=body,
            filename=document.filename,
            source=source_key,
            document_id=str(document.id),
        ),
        settings,
    )
    chunk_texts = [doc.page_content for doc in split_docs]
    if not chunk_texts:
        raise ValueError("No extractable text content in document")

    logger.info(
        "Document %s split into %d chunk(s).", document.filename, len(chunk_texts)
    )
    if len("".join(chunk_texts).strip()) < 20:
        logger.warning(
            "Extracted unusually small text content from %s", document.filename
        )

    logger.info(
        "Indexing %d chunks in database for %s...", len(split_docs), document.filename
    )
    await NotebookDocumentChunk.find(
        {"document_id": document.id}
    ).delete()
    now = datetime.now(UTC)
    for idx, split_doc in enumerate(split_docs):
        await NotebookDocumentChunk(
            document_id=document.id,
            notebook_id=document.notebook_id,
            user_id=document.user_id,
            chunk_index=idx,
            content=split_doc.page_content,
            chunk_metadata=split_doc.metadata,
            created_at=now,
            updated_at=now,
        ).insert()

    await wait_for_atlas_vector_index(document)

    document.status = "indexed"
    document.error_message = None
    document.updated_at = now
    await document.save()
    await publish_document_event(document)
    logger.info(
        "Successfully ingested and indexed document %s (%d chunks).",
        document.filename,
        len(split_docs),
    )


async def ingest_document_by_id(
    document_id: UUID,
    settings: Settings,
    *,
    s3_client: Any | None = None,
    require_processing_status: bool = False,
) -> None:
    document = await NotebookDocument.find_one({"_id": document_id})
    if document is None:
        logger.error("Failed to start ingestion: document_id=%s not found", document_id)
        return
    logger.info(
        "Start ingestion request received for document_id=%s, filename=%s",
        document_id,
        document.filename,
    )
    if require_processing_status and document.status != "processing":
        logger.info(
            "Skipping document ingestion for %s because status is %s",
            document_id,
            document.status,
        )
        return
    if document.status in CLAIMABLE_DOCUMENT_STATUSES:
        logger.info(
            "Claiming document %s for processing (current status: %s)",
            document_id,
            document.status,
        )
        document.status = "processing"
        document.error_message = None
        document.updated_at = datetime.now(UTC)
        await document.save()
        await publish_document_event(document)

    try:
        client = s3_client or get_s3_client(settings)
        await _run_document_ingestion(document, settings, client)
    except Exception as exc:
        if isinstance(exc, ClientError):
            logger.exception(
                "Notebook document ingestion hit a transient error for %s", document_id
            )
            document = await NotebookDocument.find_one({"_id": document_id})
            if document is not None:
                document.status = "uploaded"
                document.error_message = None
                document.updated_at = datetime.now(UTC)
                await document.save()
                await publish_document_event(document)
            raise TransientIngestionError(str(exc)) from exc
        logger.exception("Notebook document ingestion failed for %s", document_id)
        document = await NotebookDocument.find_one({"_id": document_id})
        if document is not None:
            document.status = "failed"
            document.error_message = str(exc)[:4000]
            document.updated_at = datetime.now(UTC)
            await document.save()
            await publish_document_event(document)
