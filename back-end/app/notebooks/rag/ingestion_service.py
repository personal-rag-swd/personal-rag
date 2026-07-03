"""Document ingestion pipeline: load source bytes → chunk (+ describe images) →
embed → index, plus the top-level orchestration and the poll-based fallback.

Persistence/state transitions live in :mod:`document_repository` and image
handling in :mod:`image_ingestion`; this module composes them. The repository
functions used by other packages (``register_pending_notebook_document``,
``mark_document_upload_failed``, ``claim_document_for_ingestion``,
``fail_stale_*``) are re-exported here so the historical
``app.notebooks.rag.ingestion_service`` import surface is preserved.
"""

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

import obstore.exceptions
from beanie import SortDirection
from langchain_core.documents import Document

from app.core.config import Settings
from app.core.embedding_provider import embed_texts
from app.core.exceptions import TransientProviderError
from app.core.s3 import get_object_bytes, get_s3_store
from app.notebooks.domain_events import (
    DocumentFailed,
    DocumentIndexed,
    DocumentUploaded,
)
from app.notebooks.exceptions import TransientIngestionError
from app.notebooks.models import NotebookDocument, NotebookDocumentChunk
from app.notebooks.rag.document_chunker import (
    IMAGE_EXTENSIONS,
    IMAGE_MEDIA_TYPES,
    ChunkingRequest,
    chunk_document,
)
from app.notebooks.rag.document_repository import (
    claim_document_for_ingestion,
    fail_stale_pending_documents,
    fail_stale_processing_documents,
    mark_document_upload_failed,
    mark_pending_document_uploaded_if_object_exists,
    record_ingestion_outcome,
    register_pending_notebook_document,
    transition_document,
)
from app.notebooks.rag.image_ingestion import (
    build_image_chunk_document,
    describe_image,
    extract_pdf_images,
)

if TYPE_CHECKING:
    from obstore.store import S3Store

logger = logging.getLogger(__name__)

__all__ = [
    "claim_document_for_ingestion",
    "fail_stale_pending_documents",
    "fail_stale_processing_documents",
    "ingest_document_by_id",
    "mark_document_upload_failed",
    "mark_pending_document_uploaded_if_object_exists",
    "process_unprocessed_notebook_documents",
    "register_pending_notebook_document",
]


async def _load_source_bytes(
    document: NotebookDocument,
    settings: Settings,
    store: S3Store | None,
) -> tuple[bytes, str]:
    """Resolve the raw bytes for a document (DB note vs S3 object) and its
    ``source`` key, enforcing the max-document-size limit.
    """
    if document.content is not None:
        body = document.content.encode("utf-8")
        source_key = f"db-notes/{document.id}"
        logger.info(
            "Reading document content from database (note type) for "
            "document_id=%s, key=%s",
            document.id,
            source_key,
        )
    else:
        logger.info(
            "Fetching document content from S3: bucket=%s, key=%s",
            document.s3_bucket,
            document.s3_key,
        )
        if not store:
            raise ValueError("S3 store must be provided for S3-based ingestion")
        if not document.s3_bucket or not document.s3_key:
            raise ValueError(
                "Cannot fetch document from S3 without bucket/key for ingestion"
            )
        body = await get_object_bytes(store, document.s3_key)
        source_key = document.s3_key

    if len(body) > settings.notebook_max_document_bytes:
        raise ValueError(
            f"Document is {len(body)} bytes, above the "
            f"{settings.notebook_max_document_bytes}-byte ingestion limit"
        )
    return body, source_key


async def _build_split_documents(
    document: NotebookDocument,
    body: bytes,
    source_key: str,
    settings: Settings,
    store: S3Store | None,
) -> list[Document]:
    """Turn raw bytes into non-empty chunk Documents (text chunks plus, for
    PDFs, described embedded images), enforcing the per-document chunk limit.
    """
    logger.info(
        "Ingesting document %s (%s bytes): starting chunking...",
        document.filename,
        len(body),
    )
    suffix = Path(document.filename).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        media_type = IMAGE_MEDIA_TYPES.get(suffix.lstrip("."), "image/jpeg")
        description = await describe_image(body, document.filename, media_type)
        split_docs: list[Document] = [
            build_image_chunk_document(
                description=description,
                document=document,
                source=source_key,
                s3_key=document.s3_key,
                media_type=media_type,
            )
        ]
    else:
        # chunk_document is pure CPU (pymupdf/docx parsing) — keep it off the
        # event loop so ingestion doesn't stall the API server.
        chunking = asyncio.to_thread(
            chunk_document,
            ChunkingRequest(
                content=body,
                filename=document.filename,
                source=source_key,
                document_id=str(document.id),
            ),
            settings,
        )
        if suffix == ".pdf" and document.s3_bucket and document.s3_key and store:
            # Text chunking and embedded-image extraction are independent
            # passes over the same bytes — run them concurrently.
            split_docs, image_docs = await asyncio.gather(
                chunking, extract_pdf_images(document, body, store)
            )
            split_docs = split_docs + image_docs
        else:
            split_docs = await chunking

    split_docs = [doc for doc in split_docs if doc.page_content.strip()]
    if not split_docs:
        raise ValueError("No extractable text content in document")
    if len(split_docs) > settings.notebook_max_chunks_per_document:
        raise ValueError(
            f"Document produced {len(split_docs)} chunks, above the "
            f"{settings.notebook_max_chunks_per_document}-chunk ingestion limit"
        )
    return split_docs


async def _embed_and_persist_chunks(
    document: NotebookDocument,
    split_docs: list[Document],
) -> None:
    """Embed the chunk texts and replace the document's stored chunks."""
    chunk_texts = [doc.page_content for doc in split_docs]

    logger.info(
        "Document %s split into %d chunk(s).", document.filename, len(chunk_texts)
    )
    if sum(len(text) for text in chunk_texts) < 20:
        logger.warning(
            "Extracted unusually small text content from %s", document.filename
        )

    logger.info(
        "Generating embeddings for %d chunks of %s...",
        len(split_docs),
        document.filename,
    )
    embeddings = await embed_texts(chunk_texts)
    if len(embeddings) != len(chunk_texts):
        raise ValueError(
            f"Embedding provider returned {len(embeddings)} embeddings for "
            f"{len(chunk_texts)} chunks in document {document.filename!r}"
        )

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


async def _run_document_ingestion(
    document: NotebookDocument,
    settings: Settings,
    store: S3Store | None,
) -> None:
    body, source_key = await _load_source_bytes(document, settings, store)
    split_docs = await _build_split_documents(
        document, body, source_key, settings, store
    )
    await _embed_and_persist_chunks(document, split_docs)
    await transition_document(document, "indexed", event_cls=DocumentIndexed)
    logger.info(
        "Successfully ingested and indexed document %s (%d chunks).",
        document.filename,
        len(split_docs),
    )


async def ingest_document_by_id(
    document_id: UUID,
    settings: Settings,
    *,
    store: S3Store | None = None,
    size: int | None = None,
) -> None:
    document = await claim_document_for_ingestion(document_id, size=size)
    if document is None:
        logger.info(
            "Skipping ingestion for document %s: missing or not claimable",
            document_id,
        )
        return
    logger.info(
        "Claimed document %s (%s) for ingestion", document_id, document.filename
    )

    try:
        resolved_store = store or get_s3_store(settings)
        await _run_document_ingestion(document, settings, resolved_store)
    except (obstore.exceptions.BaseError, TransientProviderError) as exc:
        logger.exception(
            "Notebook document ingestion hit a transient error for %s", document_id
        )
        await record_ingestion_outcome(
            document_id,
            status="uploaded",
            error_message=None,
            event=DocumentUploaded,
        )
        raise TransientIngestionError(str(exc)) from exc
    except Exception as exc:
        logger.exception("Notebook document ingestion failed for %s", document_id)
        await record_ingestion_outcome(
            document_id,
            status="failed",
            error_message=str(exc)[:4000],
            event=DocumentFailed,
            only_if_processing=True,
        )
    except BaseException:
        # CancelledError (and other BaseException subclasses) must not leave the
        # document permanently stuck at "processing". Mark it failed so the stale
        # timeout doesn't need to clean it up, then re-raise so the cancellation
        # propagates normally.
        logger.warning("Ingestion cancelled for document %s", document_id)
        await record_ingestion_outcome(
            document_id,
            status="failed",
            error_message="Ingestion was interrupted. Please retry the upload.",
            event=DocumentFailed,
            only_if_processing=True,
        )
        raise


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
    store = get_s3_store(settings) if documents else None

    for document in documents:
        stats["checked"] += 1
        if document.status == "pending":
            if not await mark_pending_document_uploaded_if_object_exists(
                document,
                settings,
                store=store,
            ):
                stats["skipped"] += 1
                continue
            stats["uploaded"] += 1

        await ingest_document_by_id(document.id, settings, store=store)
        stats["ingested"] += 1

    return stats
