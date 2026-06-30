import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pymupdf
from beanie import SortDirection
from beanie.odm.queries.update import UpdateResponse
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from langchain_core.documents import Document
from pydantic_ai import Agent
from pydantic_ai.messages import BinaryContent

from app.core.config import Settings
from app.core.embedding_provider import embed_texts
from app.core.event_bus import domain_event_bus
from app.core.llm_provider import chat_provider_is_configured, resolve_chat_provider
from app.core.s3 import get_s3_client
from app.notebooks.domain_events import (
    DocumentFailed,
    DocumentIndexed,
    DocumentProcessing,
    DocumentRegistered,
    DocumentUploaded,
)
from app.notebooks.exceptions import TransientIngestionError
from app.notebooks.models import Notebook, NotebookDocument, NotebookDocumentChunk
from app.notebooks.rag.document_chunker import (
    IMAGE_EXTENSIONS,
    IMAGE_MEDIA_TYPES,
    ChunkingRequest,
    chunk_document,
)
from app.users.models import User

logger = logging.getLogger(__name__)

CLAIMABLE_DOCUMENT_STATUSES = {"pending", "uploaded"}
INGESTION_FAILED_MESSAGE = (
    "Ingestion timed out while processing. Please retry the upload."
)
UPLOAD_FAILED_MESSAGE = (
    "Upload timed out. The file was not received by storage. Please retry the upload."
)

image_description_agent = Agent(
    instructions=(
        "Describe this image concisely for a RAG retrieval system. "
        "Include all visible text, objects, charts, diagrams, tables, and visual layout."
    )
)


def _image_chunk_document(
    *,
    description: str,
    document: NotebookDocument,
    source: str,
    s3_key: str | None,
    media_type: str,
) -> Document:
    """Build the ``image`` chunk Document shared by the direct-image upload and
    embedded-PDF-image paths (same metadata shape, only ``source``/``s3_key`` vary).
    """
    return Document(
        page_content=description,
        metadata={
            "source": source,
            "document_id": str(document.id),
            "chunk_type": "image",
            "s3_key": s3_key,
            "s3_bucket": document.s3_bucket,
            "media_type": media_type,
        },
    )


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

# Cap concurrent vision-LLM calls so an image-heavy PDF doesn't fan out hundreds
# of simultaneous requests (provider rate limits / 429s / ingestion timeout).
_PDF_IMAGE_VISION_CONCURRENCY = 5


def _extract_pdf_image_bytes(
    pdf_doc: pymupdf.Document, xref: int
) -> tuple[bytes, str, str]:
    """Return ``(image_bytes, extension, media_type)`` for an embedded image.

    Follows the official PyMuPDF recipe: ``extract_image`` yields the image in
    its native encoding; formats a vision model/browser cannot read are
    re-rendered to RGB PNG via a ``Pixmap`` (handling CMYK/alpha).
    """
    base = pdf_doc.extract_image(xref)
    ext = base["ext"].lower()
    media_type = IMAGE_MEDIA_TYPES.get(ext)
    if media_type is not None:
        return base["image"], ext, media_type

    pix = pymupdf.Pixmap(pdf_doc, xref)
    if pix.n - pix.alpha > 3:  # CMYK / multi-channel → convert to RGB first
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    return pix.tobytes("png"), "png", "image/png"


async def _extract_pdf_images(
    document: NotebookDocument,
    pdf_bytes: bytes,
    s3_client: BaseClient,
) -> list[Document]:
    """Extract embedded images from a PDF, upload them to S3, and describe them.

    Uses the official ``page.get_images`` + ``Document.extract_image`` recipe so
    only images actually embedded in the document are processed — each xref once
    — rather than rendering every page.
    """
    if not document.s3_key or not document.s3_bucket:
        raise ValueError(
            "Cannot extract embedded images from a PDF without S3 bucket/key"
        )

    key_prefix = document.s3_key.rsplit("/", 1)[0]

    seen_xrefs: set[int] = set()
    images: list[tuple[str, bytes, str, str]] = []  # (s3_key, bytes, media_type, label)
    pdf_doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        for page_index in range(len(pdf_doc)):
            # get_images(full=True) tuple: (xref, smask, width, height, ...).
            for img in pdf_doc[page_index].get_images(full=True):
                xref, width, height = img[0], img[2], img[3]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)

                # Skip logos/icons/spacers before the costlier extract_image call.
                if (
                    width < _MIN_EMBEDDED_IMAGE_DIMENSION
                    or height < _MIN_EMBEDDED_IMAGE_DIMENSION
                ):
                    continue

                image_bytes, ext, media_type = _extract_pdf_image_bytes(pdf_doc, xref)
                image_key = f"{key_prefix}/images/img_{xref}.{ext}"
                # boto3 put_object is blocking; keep it off the event loop.
                await asyncio.to_thread(
                    s3_client.put_object,
                    Bucket=document.s3_bucket,
                    Key=image_key,
                    Body=image_bytes,
                    ContentType=media_type,
                )
                label = f"image on page {page_index + 1} of {document.filename}"
                images.append((image_key, image_bytes, media_type, label))
    finally:
        pdf_doc.close()

    if not images:
        logger.info("No embedded images found in PDF %s", document.filename)
        return []

    # Describe images concurrently but bounded — sequential vision calls on an
    # image-heavy PDF can exceed the ingestion timeout, while an unbounded
    # gather can hammer the provider into rate limits.
    semaphore = asyncio.Semaphore(_PDF_IMAGE_VISION_CONCURRENCY)

    async def _bounded(data: bytes, label: str, media_type: str) -> str:
        async with semaphore:
            return await _describe_image(data, label, media_type)

    descriptions = await asyncio.gather(
        *(_bounded(data, label, media_type) for _, data, media_type, label in images)
    )
    image_docs = [
        _image_chunk_document(
            description=description,
            document=document,
            source=document.s3_key,
            s3_key=image_key,
            media_type=media_type,
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
    s3_client: BaseClient | None,
) -> bool:
    if document.status != "pending":
        return document.status == "uploaded"

    s3_client = s3_client or get_s3_client(settings)
    if not document.s3_bucket or not document.s3_key:
        raise ValueError(
            "Cannot check S3 object existence for a pending document without bucket/key"
        )
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
        .sort(("created_at", SortDirection.ASCENDING))
        .limit(limit)
        .to_list()
    )

    pending_docs = (
        await NotebookDocument.find(
            {"status": "pending"},
        )
        .sort(("created_at", SortDirection.ASCENDING))
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
    s3_client: BaseClient,
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
        if not s3_client:
            raise ValueError("S3 client must be provided for S3-based ingestion")
        if not document.s3_bucket or not document.s3_key:
            raise ValueError(
                "Cannot fetch document from S3 without bucket/key for ingestion"
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
        media_type = IMAGE_MEDIA_TYPES.get(suffix.lstrip("."), "image/jpeg")
        description = await _describe_image(body, document.filename, media_type)
        split_docs: list[Document] = [
            _image_chunk_document(
                description=description,
                document=document,
                source=source_key,
                s3_key=document.s3_key,
                media_type=media_type,
            )
        ]
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
        if suffix == ".pdf" and document.s3_bucket and document.s3_key:
            split_docs = split_docs + await _extract_pdf_images(
                document, body, s3_client
            )

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
        "Generating embeddings for %d chunks of %s...",
        len(split_docs),
        document.filename,
    )
    embeddings = await embed_texts(chunk_texts)

    logger.info(
        "Indexing %d chunks in database for %s...", len(split_docs), document.filename
    )
    await NotebookDocumentChunk.find({"document_id": document.id}).delete()
    now = datetime.now(UTC)
    await NotebookDocumentChunk.insert_many(
        [
            NotebookDocumentChunk(
                document_id=document.id,
                notebook_id=document.notebook_id,
                user_id=document.user_id,
                chunk_index=idx,
                content=split_doc.page_content,
                embedding=embeddings[idx],
                chunk_metadata=split_doc.metadata,
                created_at=now,
                updated_at=now,
            )
            for idx, split_doc in enumerate(split_docs)
        ]
    )

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


async def _record_ingestion_outcome(
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
    document.status = status
    document.error_message = error_message
    document.updated_at = datetime.now(UTC)
    await document.save()
    await domain_event_bus.emit(event(document))


async def ingest_document_by_id(
    document_id: UUID,
    settings: Settings,
    *,
    s3_client: BaseClient | None = None,
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
            await _record_ingestion_outcome(
                document_id,
                status="uploaded",
                error_message=None,
                event=DocumentUploaded,
            )
            raise TransientIngestionError(str(exc)) from exc
        logger.exception("Notebook document ingestion failed for %s", document_id)
        await _record_ingestion_outcome(
            document_id,
            status="failed",
            error_message=str(exc)[:4000],
            event=DocumentFailed,
        )
    except BaseException:
        # CancelledError (and other BaseException subclasses) must not leave the
        # document permanently stuck at "processing". Mark it failed so the stale
        # timeout doesn't need to clean it up, then re-raise so the cancellation
        # propagates normally.
        logger.warning("Ingestion cancelled for document %s", document_id)
        await _record_ingestion_outcome(
            document_id,
            status="failed",
            error_message="Ingestion was interrupted. Please retry the upload.",
            event=DocumentFailed,
            only_if_processing=True,
        )
        raise
