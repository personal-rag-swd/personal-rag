from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import BinaryContent

from app.core.config import Settings
from app.core.s3 import get_s3_client
from app.notebooks.models import Notebook
from app.notebooks.prompt import CHAT_SYSTEM_INSTRUCTIONS, build_context_block
from app.notebooks.rag.search_service import search_notebook_chunks
from app.users.models import User

logger = logging.getLogger(__name__)


@dataclass
class NotebookChatDeps:
    notebook: Notebook
    current_user: User
    settings: Settings


notebook_chat_agent = Agent(
    deps_type=NotebookChatDeps,
    instructions=CHAT_SYSTEM_INSTRUCTIONS,
)


@notebook_chat_agent.tool
async def search_notebook_context(
    ctx: RunContext[NotebookChatDeps], query: str
) -> list[str | BinaryContent]:
    """Search indexed notebook sources and return labeled excerpts to cite."""
    chunks = await search_notebook_chunks(
        notebook=ctx.deps.notebook,
        current_user=ctx.deps.current_user,
        query=query,
        settings=ctx.deps.settings,
        top_k=ctx.deps.settings.notebook_retrieval_top_k,
    )
    parts: list[str | BinaryContent] = [build_context_block(chunks)]

    s3_client = get_s3_client(ctx.deps.settings)
    for chunk in chunks:
        if chunk.chunk_type != "image":
            continue
        s3_key = str(chunk.metadata.get("s3_key", ""))
        s3_bucket = str(chunk.metadata.get("s3_bucket", ""))
        media_type = str(chunk.metadata.get("media_type", "image/jpeg"))
        if not (s3_key and s3_bucket):
            continue
        try:
            obj = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
            parts.append(BinaryContent(data=obj["Body"].read(), media_type=media_type))
        except Exception:
            logger.warning(
                "Failed to fetch image bytes for chunk %s; skipping", chunk.chunk_index
            )

    return parts
