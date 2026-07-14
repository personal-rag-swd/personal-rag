from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import BinaryContent, ToolReturn

from app.core.config import Settings
from app.core.s3 import get_object_bytes, get_s3_store
from app.notebooks.models import Notebook
from app.notebooks.prompt import CHAT_SYSTEM_INSTRUCTIONS, build_context_block
from app.notebooks.prompt.context_prompts import chunk_to_source, image_part_label
from app.notebooks.rag.search_service import RetrievedChunk, search_notebook_chunks
from app.users.models import User

if TYPE_CHECKING:
    from obstore.store import S3Store

logger = logging.getLogger(__name__)


@dataclass
class NotebookChatDeps:
    notebook: Notebook
    current_user: User
    settings: Settings
    document_ids: list[UUID] | None = None
    # Next S-label to assign; shared across all search calls in one run so a
    # second search continues numbering (S6, S7, …) instead of reusing S1.
    next_source_number: int = 1


notebook_chat_agent = Agent(
    deps_type=NotebookChatDeps,
    instructions=CHAT_SYSTEM_INSTRUCTIONS,
)


@notebook_chat_agent.tool
async def search_notebook_context(
    ctx: RunContext[NotebookChatDeps], query: str
) -> ToolReturn:
    """Search indexed notebook sources and return labeled excerpts to cite."""
    # One error boundary for the whole retrieval path (rewrite, embed, vector
    # search): a transient provider or database failure must degrade the answer,
    # not abort the AG-UI stream mid-turn.
    try:
        chunks = await search_notebook_chunks(
            notebook=ctx.deps.notebook,
            current_user=ctx.deps.current_user,
            query=query,
            settings=ctx.deps.settings,
            top_k=ctx.deps.settings.notebook_retrieval_top_k,
            document_ids=ctx.deps.document_ids,
        )
    except Exception:
        logger.exception(
            "Notebook search failed for notebook %s; degrading without sources",
            ctx.deps.notebook.id,
        )
        return ToolReturn(
            return_value=(
                "Notebook search is temporarily unavailable. Answer from the "
                "conversation so far and tell the user that source retrieval failed."
            )
        )
    start_number = ctx.deps.next_source_number
    ctx.deps.next_source_number += len(chunks)
    numbers = {id(chunk): start_number + i for i, chunk in enumerate(chunks)}

    context_block = build_context_block(chunks, start_number=start_number)
    # Structured sources ride on the tool message's metadata (persisted with
    # history, never sent to the LLM) so transcripts don't have to re-parse
    # the prompt text.
    metadata = {
        "sources": [
            chunk_to_source(chunk, number=numbers[id(chunk)]) for chunk in chunks
        ]
    }

    image_chunks = [chunk for chunk in chunks if chunk.chunk_type == "image"]
    if not image_chunks:
        return ToolReturn(return_value=context_block, metadata=metadata)

    store = get_s3_store(ctx.deps.settings)
    fetched = await asyncio.gather(
        *(_fetch_image_content(store, chunk) for chunk in image_chunks)
    )
    # Prefix each image with a label carrying its SOURCE identifiers so the model
    # can bind the picture it sees to a citable chunk (the bytes alone have no
    # source header). Skip chunks whose bytes failed to download.
    parts: list[str | BinaryContent] = [context_block]
    for chunk, content in zip(image_chunks, fetched, strict=True):
        if content is None:
            continue
        parts.append(image_part_label(chunk, number=numbers[id(chunk)]))
        parts.append(content)
    return ToolReturn(return_value=parts, metadata=metadata)


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
