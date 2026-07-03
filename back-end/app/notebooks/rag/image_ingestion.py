"""Image handling for ingestion: vision-model description of standalone images
and extraction/description of images embedded in PDFs.

Kept separate from the ingestion pipeline because it is the only part that
touches PyMuPDF image internals and the vision LLM — a distinct reason to
change from the chunk/embed/index flow.
"""

import asyncio
import logging
from typing import TYPE_CHECKING

import obstore
import pymupdf
from langchain_core.documents import Document
from pydantic_ai import Agent
from pydantic_ai.messages import BinaryContent

from app.core.llm_provider import (
    chat_provider_is_configured,
    resolve_chat_provider,
    run_agent_with_retry,
)
from app.notebooks.models import NotebookDocument
from app.notebooks.rag.document_chunker import IMAGE_MEDIA_TYPES

if TYPE_CHECKING:
    from obstore.store import S3Store

logger = logging.getLogger(__name__)

# Embedded images smaller than this (in either dimension, px) are almost always
# logos, icons, bullets, or spacers — not worth a vision call or an index entry.
_MIN_EMBEDDED_IMAGE_DIMENSION = 64

# Cap concurrent vision-LLM calls so an image-heavy PDF doesn't fan out hundreds
# of simultaneous requests (provider rate limits / 429s / ingestion timeout).
# Module-level semaphore so the cap applies across all concurrent ingestion tasks.
_PDF_IMAGE_VISION_CONCURRENCY = 5
_pdf_image_vision_semaphore = asyncio.Semaphore(_PDF_IMAGE_VISION_CONCURRENCY)

image_description_agent = Agent(
    instructions=(
        "Describe this image concisely for a RAG retrieval system. "
        "Include all visible text, objects, charts, diagrams, tables, and visual layout."
    )
)


def build_image_chunk_document(
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


async def describe_image(image_bytes: bytes, label: str, media_type: str) -> str:
    """Call the vision LLM to describe an image; fall back to label on any failure.

    Retries transient provider errors first (via the shared helper) — a fallback
    placeholder is baked into the index permanently, degrading every future
    retrieval for the document, so it should be a last resort.
    """
    if not chat_provider_is_configured():
        return f"Image: {label}"
    try:
        result = await run_agent_with_retry(
            image_description_agent,
            [BinaryContent(data=image_bytes, media_type=media_type)],
            model=resolve_chat_provider(),
        )
        return result.output.strip() or f"Image: {label}"
    except Exception:
        logger.warning("LLM image description failed for %s", label)
        return f"Image: {label}"


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


def _collect_pdf_images(
    pdf_bytes: bytes,
    key_prefix: str,
    filename: str,
) -> list[tuple[str, bytes, str, str]]:
    """Extract embedded PDF images, returning (s3_key, bytes, media_type, label).

    Uses the official ``page.get_images`` + ``Document.extract_image`` recipe so
    only images actually embedded in the document are processed — each xref once
    — rather than rendering every page. Pure CPU work; run via asyncio.to_thread.
    """
    seen_xrefs: set[int] = set()
    images: list[tuple[str, bytes, str, str]] = []
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
                label = f"image on page {page_index + 1} of {filename}"
                images.append((image_key, image_bytes, media_type, label))
    finally:
        pdf_doc.close()
    return images


async def extract_pdf_images(
    document: NotebookDocument,
    pdf_bytes: bytes,
    store: S3Store,
) -> list[Document]:
    """Extract embedded images from a PDF, upload them to S3, and describe them."""
    if not document.s3_key or not document.s3_bucket:
        raise ValueError(
            "Cannot extract embedded images from a PDF without S3 bucket/key"
        )

    key_prefix = document.s3_key.rsplit("/", 1)[0]
    images = await asyncio.to_thread(
        _collect_pdf_images, pdf_bytes, key_prefix, document.filename
    )
    if not images:
        logger.info("No embedded images found in PDF %s", document.filename)
        return []

    await asyncio.gather(
        *(
            obstore.put_async(
                store,
                image_key,
                image_bytes,
                attributes={"Content-Type": media_type},
            )
            for image_key, image_bytes, media_type, _ in images
        )
    )

    # Describe images concurrently but bounded — sequential vision calls on an
    # image-heavy PDF can exceed the ingestion timeout, while an unbounded
    # gather can hammer the provider into rate limits. The module-level semaphore
    # caps concurrency across all concurrent ingestion tasks, not just within one PDF.
    async def _bounded(data: bytes, label: str, media_type: str) -> str:
        async with _pdf_image_vision_semaphore:
            return await describe_image(data, label, media_type)

    descriptions = await asyncio.gather(
        *(_bounded(data, label, media_type) for _, data, media_type, label in images)
    )
    image_docs = [
        build_image_chunk_document(
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
