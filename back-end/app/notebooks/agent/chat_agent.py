from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

from app.core.config import Settings
from app.notebooks.models import Notebook
from app.notebooks.prompt import CHAT_SYSTEM_INSTRUCTIONS, build_context_block
from app.notebooks.rag.search_service import search_notebook_chunks
from app.users.models import User


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
async def search_notebook_context(ctx: RunContext[NotebookChatDeps], query: str) -> str:
    """Search indexed notebook sources and return labeled excerpts to cite."""
    chunks = await search_notebook_chunks(
        notebook=ctx.deps.notebook,
        current_user=ctx.deps.current_user,
        query=query,
        settings=ctx.deps.settings,
        top_k=ctx.deps.settings.notebook_retrieval_top_k,
    )
    return build_context_block(chunks)
