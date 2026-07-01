from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import obstore
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import BinaryContent

from app.core.config import Settings
from app.core.s3 import get_s3_store
from app.notebooks.models import Notebook
from app.notebooks.prompt import CHAT_SYSTEM_INSTRUCTIONS, build_context_block
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


notebook_chat_agent = Agent(
    deps_type=NotebookChatDeps,
    instructions=CHAT_SYSTEM_INSTRUCTIONS,
)


@notebook_chat_agent.tool
async def search_notebook_context(
    ctx: RunContext[NotebookChatDeps], query: str
) -> str | list[str | BinaryContent]:
    """Search indexed notebook sources and return labeled excerpts to cite."""
    chunks = await search_notebook_chunks(
        notebook=ctx.deps.notebook,
        current_user=ctx.deps.current_user,
        query=query,
        settings=ctx.deps.settings,
        top_k=ctx.deps.settings.notebook_retrieval_top_k,
        document_ids=ctx.deps.document_ids,
    )
    context_block = build_context_block(chunks)

    image_chunks = [chunk for chunk in chunks if chunk.chunk_type == "image"]
    if not image_chunks:
        return context_block

    store = get_s3_store(ctx.deps.settings)
    fetched = await asyncio.gather(
        *(_fetch_image_content(store, chunk) for chunk in image_chunks)
    )
    parts: list[str | BinaryContent] = [context_block]
    parts.extend(part for part in fetched if part is not None)
    return parts


async def _fetch_image_content(
    store: S3Store, chunk: RetrievedChunk
) -> BinaryContent | None:
    """Download an image chunk's bytes from S3 as BinaryContent (None on failure)."""
    s3_key = str(chunk.metadata.get("s3_key", ""))
    media_type = str(chunk.metadata.get("media_type", "image/jpeg"))
    if not s3_key:
        return None

    try:
        result = await obstore.get_async(store, s3_key)
        data = bytes(await result.bytes_async())
        return BinaryContent(data=data, media_type=media_type)
    except Exception:
        logger.warning(
            "Failed to fetch image bytes for chunk %s; skipping", chunk.chunk_index
        )
        return None
