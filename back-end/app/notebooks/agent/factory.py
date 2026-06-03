from __future__ import annotations

from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.notebooks.agent.base import ChatModelProvider
from app.notebooks.agent.providers import GeminiChatProvider, OpenAICompatibleChatProvider, OpenRouterChatProvider
from app.notebooks.models import Notebook
from app.notebooks.prompt import CHAT_SYSTEM_INSTRUCTIONS, build_context_block
from app.notebooks.tools import search_notebook_chunks
from app.users.models import User

_CHAT_PROVIDER_REGISTRY: dict[str, ChatModelProvider] = {
    "openrouter": OpenRouterChatProvider(),
    "openai_compatible": OpenAICompatibleChatProvider(),
    "gemini": GeminiChatProvider(),
}


def resolve_chat_provider() -> ChatModelProvider:
    settings = get_settings()
    selected_provider = settings.chat_provider.strip().lower()
    resolved = _CHAT_PROVIDER_REGISTRY.get(selected_provider)
    if resolved is None:
        raise ValueError(
            f"Unsupported chat provider '{selected_provider}'. "
            "Use openrouter, openai_compatible, or gemini."
        )
    return resolved


def chat_provider_is_configured() -> bool:
    """True if the currently selected chat provider has an API key available.

    Used to surface a friendly 503 before attempting LLM-backed features
    (chat, reports) instead of failing deep inside the provider SDK.
    """
    settings = get_settings()
    selected_provider = settings.chat_provider.strip().lower()
    if selected_provider in ("gemini", "openrouter", "openai_compatible"):
        return bool(settings.chat_api_key)
    return False


@dataclass
class NotebookChatDeps:
    session: Session
    notebook: Notebook
    current_user: User
    settings: Settings


def get_notebook_chat_agent() -> Agent[NotebookChatDeps, str]:
    model = resolve_chat_provider().build_model()
    agent = Agent(
        model,
        deps_type=NotebookChatDeps,
        instructions=CHAT_SYSTEM_INSTRUCTIONS,
    )

    @agent.tool
    def search_notebook_context(ctx: RunContext[NotebookChatDeps], query: str) -> str:
        """Search indexed notebook sources and return labeled excerpts to cite."""
        chunks = search_notebook_chunks(
            session=ctx.deps.session,
            notebook=ctx.deps.notebook,
            current_user=ctx.deps.current_user,
            query=query,
            settings=ctx.deps.settings,
            top_k=6,
        )
        return build_context_block(chunks)

    return agent
