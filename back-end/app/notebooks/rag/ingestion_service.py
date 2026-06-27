from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pymupdf
from botocore.exceptions import ClientError
from bson import Binary
from langchain_core.documents import Document
from pydantic_ai import Agent
from pydantic_ai.messages import BinaryContent

from app.core.config import Settings
from app.core.event_bus import domain_event_bus
from app.core.llm_provider import chat_provider_is_configured, resolve_chat_provider
from app.core.s3 import get_s3_client
from app.notebooks.domain_events import (
    DocumentFailed,
    DocumentIndexed,
    DocumentIndexing,
    DocumentProcessing,
    DocumentRegistered,
    DocumentUploaded,
)
from app.notebooks.models import Notebook, NotebookDocument, NotebookDocumentChunk
from app.notebooks.rag.document_chunker import (
    IMAGE_EXTENSIONS,
    ChunkingRequest,
    chunk_document,
)
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
    """Check if every chunk of the document has been embedded and is searchable.

    Atlas makes the index ACTIVE and queryable before all documents are
    embedded, so we must verify each chunk individually rather than stopping
    at the first hit.
    """
    chunks = await NotebookDocumentChunk.find(
        {"document_id": document.id},
        sort=[("chunk_index", 1)],
    ).to_list()

    if not chunks:
        return True

    for chunk in chunks:
        try:
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": ATLAS_VECTOR_INDEX_NAME,
                        "path": "content",
                        "query": chunk.content,
                        "numCandidates": 20,
                        "limit": 10,
                        "similarity": "cosine",
                        "filter": {
                            "notebook_id": Binary.from_uuid(document.notebook_id),
                            "user_id": Binary.from_uuid(document.user_id),
                        },
                    }
                }
            ]
            results = await NotebookDocumentChunk.aggregate(pipeline).to_list()
            found = any(r.get("document_id") == document.id for r in results)
            if not found:
                return False
        except Exception as e:
            logger.warning(
                "Vector search query failed during indexing verification for document %s: %s",
                document.id,
                str(e),
            )
            return False

    return True


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
    await domain_event_bus.emit(DocumentIndexing(document))

    start_time = datetime.now(UTC)
    deadline = start_time + timedelta(seconds=wait_seconds)
    while True:
        status, queryable = index_status
        if (
            status == "ACTIVE"
            and queryable
            and await _is_document_vector_indexed(document)
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


# Canonical IANA image MIME types. ``image/jpg`` is NOT valid — vision
# providers reject it — so ``.jpg`` must map to ``image/jpeg``.
_IMAGE_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

image_description_agent = Agent(
    instructions=(
        "Describe this image concisely for a RAG retrieval system. "
        "Include all visible text, objects, charts, diagrams, tables, and visual layout."
    )
)


def _image_media_type(filename: str) -> str:
    """Map a filename to a valid image MIME type, defaulting to image/jpeg."""
    return _IMAGE_MEDIA_TYPES.get(Path(filename).suffix.lower(), "image/jpeg")


async def _describe_image(image_bytes: bytes, label: str, media_type: str) -> str:
    """Call the vision LLM to describe an image; fall back to label on any failure."""
    if not chat_provider_is_configured():
        return f"Image: {label}"
    try:
        result = await image_description_agent.run(
            [BinaryContent(data=image_bytes, media_type=media_type)],
            model=resolve_chat_provider(),
        )
        return result.output.strip() or f"Image: {label}"
    except Exception:
        logger.warning("LLM image description failed for %s", label)
        return f"Image: {label}"


# Embedded images smaller than this (in either dimension, px) are almost always
# logos, icons, bullets, or spacers — not worth a vision call or an index entry.
_MIN_EMBEDDED_IMAGE_DIMENSION = 64

# Native encodings a vision provider and the browser can consume directly. Any
# other format (CMYK JPEG, JPX, JBIG2, …) is normalized to PNG via a Pixmap.
_PDF_IMAGE_MEDIA_TYPES = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
}


def _extract_pdf_image_bytes(
    pdf_doc: pymupdf.Document, xref: int
) -> tuple[bytes, str, str] | None:
    """Return ``(image_bytes, extension, media_type)`` for an embedded image.

    Follows the official PyMuPDF recipe: ``extract_image`` yields the image in
    its native encoding; formats a vision model/browser cannot read are
    re-rendered to RGB PNG via a ``Pixmap`` (handling CMYK/alpha). Returns
    ``None`` for images too small to be meaningful.
    """
    base = pdf_doc.extract_image(xref)
    if (
        base["width"] < _MIN_EMBEDDED_IMAGE_DIMENSION
        or base["height"] < _MIN_EMBEDDED_IMAGE_DIMENSION
    ):
        return None

    ext = base["ext"].lower()
    media_type = _PDF_IMAGE_MEDIA_TYPES.get(ext)
    if media_type is not None:
        return base["image"], ext, media_type

    pix = pymupdf.Pixmap(pdf_doc, xref)
    if pix.n - pix.alpha > 3:  # CMYK / multi-channel → convert to RGB first
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    return pix.tobytes("png"), "png", "image/png"


async def _extract_pdf_images(
    document: NotebookDocument,
    pdf_bytes: bytes,
    s3_client: Any,
) -> list[Document]:
    """Extract embedded images from a PDF, upload them to S3, and describe them.

    Uses the official ``page.get_images`` + ``Document.extract_image`` recipe so
    only images actually embedded in the document are processed — each xref once
    — rather than rendering every page.
    """
    key_prefix = document.s3_key.rsplit("/", 1)[0]
    pdf_doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

    seen_xrefs: set[int] = set()
    images: list[tuple[str, bytes, str, str]] = []  # (s3_key, bytes, media_type, label)
    for page_index in range(len(pdf_doc)):
        for img in pdf_doc[page_index].get_images():
            xref = img[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            extracted = _extract_pdf_image_bytes(pdf_doc, xref)
            if extracted is None:
                continue
            image_bytes, ext, media_type = extracted

            image_key = f"{key_prefix}/images/img_{xref}.{ext}"
            s3_client.put_object(
                Bucket=document.s3_bucket,
                Key=image_key,
                Body=image_bytes,
                ContentType=media_type,
            )
            label = f"image on page {page_index + 1} of {document.filename}"
            images.append((image_key, image_bytes, media_type, label))

    if not images:
        logger.info("No embedded images found in PDF %s", document.filename)
        return []

    # Describe every image concurrently — sequential vision calls on an
    # image-heavy PDF can exceed the ingestion processing timeout.
    descriptions = await asyncio.gather(
        *(
            _describe_image(data, label, media_type)
            for _, data, media_type, label in images
        )
    )
    image_docs = [
        Document(
            page_content=description,
            metadata={
                "source": document.s3_key,
                "document_id": str(document.id),
                "chunk_type": "image",
                "s3_key": image_key,
                "s3_bucket": document.s3_bucket,
                "media_type": media_type,
            },
        )
        for (image_key, _, media_type, _), description in zip(
            images, descriptions, strict=True
        )
    ]
    logger.info(
        "Extracted %d embedded image(s) from PDF %s",
        len(image_docs),
        document.filename,
    )
    return image_docs


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
        await domain_event_bus.emit(DocumentFailed(doc))
    logger.warning(warning_log_template, len(stale_docs))
    return len(stale_docs)


async def fail_stale_processing_documents(
    settings: Settings,
) -> int:
    timeout_threshold = datetime.now(UTC) - timedelta(
        minutes=settings.file_ingestion_processing_timeout_minutes,
    )
    return await _fail_stale_documents(
        query={
            "status": {"$in": ["processing", "indexing"]},
            "updated_at": {"$lte": timeout_threshold},
        },
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
    await domain_event_bus.emit(DocumentRegistered(document))
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
    await domain_event_bus.emit(DocumentUploaded(document))
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

    uploaded_docs = (
        await NotebookDocument.find(
            {"status": "uploaded"},
        )
        .sort(("created_at", 1))
        .limit(limit)
        .to_list()
    )

    pending_docs = (
        await NotebookDocument.find(
            {"status": "pending"},
        )
        .sort(("created_at", 1))
        .limit(limit - len(uploaded_docs))
        .to_list()
    )

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
    document.status = "failed"
    document.error_message = (
        error_message or "Upload failed before object storage accepted the file."
    )[:4000]
    document.updated_at = datetime.now(UTC)
    await document.save()
    await domain_event_bus.emit(DocumentFailed(document))
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
    suffix = Path(document.filename).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        media_type = _image_media_type(document.filename)
        description = await _describe_image(body, document.filename, media_type)
        split_docs: list[Document] = [
            Document(
                page_content=description,
                metadata={
                    "source": source_key,
                    "document_id": str(document.id),
                    "chunk_type": "image",
                    "s3_key": document.s3_key,
                    "s3_bucket": document.s3_bucket,
                    "media_type": media_type,
                },
            )
        ]
    elif suffix == ".pdf" and document.s3_bucket:
        text_docs = chunk_document(
            ChunkingRequest(
                content=body,
                filename=document.filename,
                source=source_key,
                document_id=str(document.id),
            ),
            settings,
        )
        image_docs = await _extract_pdf_images(document, body, s3_client)
        split_docs = text_docs + image_docs
    else:
        split_docs = chunk_document(
            ChunkingRequest(
                content=body,
                filename=document.filename,
                source=source_key,
                document_id=str(document.id),
            ),
            settings,
        )

    # Drop blank chunks so they are never inserted/embedded — an empty chunk
    # would stall index verification (its vector-search query never matches).
    split_docs = [doc for doc in split_docs if doc.page_content.strip()]
    if not split_docs:
        raise ValueError("No extractable text content in document")
    chunk_texts = [doc.page_content for doc in split_docs]

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
    await NotebookDocumentChunk.find({"document_id": document.id}).delete()
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
    await domain_event_bus.emit(DocumentIndexed(document))
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
        await domain_event_bus.emit(DocumentProcessing(document))

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
                await domain_event_bus.emit(DocumentUploaded(document))
            raise TransientIngestionError(str(exc)) from exc
        logger.exception("Notebook document ingestion failed for %s", document_id)
        document = await NotebookDocument.find_one({"_id": document_id})
        if document is not None:
            document.status = "failed"
            document.error_message = str(exc)[:4000]
            document.updated_at = datetime.now(UTC)
            await document.save()
            await domain_event_bus.emit(DocumentFailed(document))
    except BaseException:
        # CancelledError (and other BaseException subclasses) must not leave the
        # document permanently stuck at "processing". Mark it failed so the stale
        # timeout doesn't need to clean it up, then re-raise so the cancellation
        # propagates normally.
        logger.warning("Ingestion cancelled for document %s", document_id)
        doc = await NotebookDocument.find_one({"_id": document_id})
        if doc is not None and doc.status == "processing":
            doc.status = "failed"
            doc.error_message = "Ingestion was interrupted. Please retry the upload."
            doc.updated_at = datetime.now(UTC)
            await doc.save()
            await domain_event_bus.emit(DocumentFailed(doc))
        raise
