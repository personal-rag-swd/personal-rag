from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ToolReturn

from app.core.config import Settings
from app.core.s3 import get_s3_store
from app.notebooks.models import Notebook
from app.notebooks.prompt import CHAT_SYSTEM_INSTRUCTIONS, build_context_block
from app.notebooks.prompt.context_prompts import chunk_to_source
from app.notebooks.rag.image_context import build_image_parts
from app.notebooks.rag.search_service import search_notebook_chunks
from app.users.models import User

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
    image_parts = await build_image_parts(image_chunks, numbers, store)
    # Image bytes ride on `content` (a separate UserPromptPart for the model),
    # not in `return_value`: a non-string return_value is JSON-serialized into
    # the AG-UI tool-result event, which escapes the newlines the frontend's
    # SOURCE-block parser depends on during live streaming.
    return ToolReturn(
        return_value=context_block,
        content=image_parts or None,
        metadata=metadata,
    )
