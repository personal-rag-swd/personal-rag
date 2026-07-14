"""Shared helper for attaching retrieved image chunks' bytes to an LLM prompt.

Both the chat agent (``search_notebook_context``) and report generation
(``build_report_context``) need the same thing: describe an image chunk via
its ``SOURCE``/label text *and* show the model the actual bytes, so citations
of a chart are grounded in what it depicts, not just its stored description.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from pydantic_ai.messages import BinaryContent

from app.core.s3 import get_object_bytes
from app.notebooks.prompt.context_prompts import image_part_label
from app.notebooks.rag.search_service import RetrievedChunk

if TYPE_CHECKING:
    from obstore.store import S3Store

logger = logging.getLogger(__name__)


async def _fetch_image_content(
    store: S3Store, chunk: RetrievedChunk
) -> BinaryContent | None:
    """Download an image chunk's bytes from S3 as BinaryContent (None on failure)."""
    s3_key = str(chunk.metadata.get("s3_key", ""))
    media_type = str(chunk.metadata.get("media_type", "image/jpeg"))
    if not s3_key:
        return None

    try:
        data = await get_object_bytes(store, s3_key)
        return BinaryContent(data=data, media_type=media_type)
    except Exception:
        logger.warning(
            "Failed to fetch image bytes for chunk %s; skipping", chunk.chunk_index
        )
        return None


async def build_image_parts(
    image_chunks: list[RetrievedChunk],
    numbers: dict[int, int] | None,
    store: S3Store,
) -> list[str | BinaryContent]:
    """Fetch image chunk bytes and return ``[label, content, label, content, ...]``.

    ``numbers``, when given, maps ``id(chunk)`` to the chunk's citation number,
    embedded in each label so the model can bind the picture it sees to a
    citable source (chat). Pass ``None`` where chunks have no S-label (reports).
    Chunks whose bytes fail to download are skipped.
    """
    fetched = await asyncio.gather(
        *(_fetch_image_content(store, chunk) for chunk in image_chunks)
    )
    parts: list[str | BinaryContent] = []
    for chunk, content in zip(image_chunks, fetched, strict=True):
        if content is None:
            continue
        number = numbers.get(id(chunk)) if numbers is not None else None
        parts.append(image_part_label(chunk, number=number))
        parts.append(content)
    return parts
