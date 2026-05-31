from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.notebooks.models import Notebook
from app.notebooks.prompt import CHAT_SYSTEM_INSTRUCTIONS, build_context_block
from app.notebooks.tools import search_notebook_chunks
from app.users.models import User


def _build_chat_model(settings: Settings) -> Model:
    """Resolve the configured chat provider and return a ready-to-use model."""
    provider = settings.chat_provider.strip().lower()
    if provider == "gemini":
        return GoogleModel(
            settings.chat_model,
            provider=GoogleProvider(api_key=settings.chat_api_key),
        )
    if provider in ("openrouter", "openai_compatible"):
        return OpenAIChatModel(
            settings.chat_model,
            provider=OpenAIProvider(
                api_key=settings.chat_api_key,
                base_url=settings.chat_provider_url or None,
            ),
        )
    raise ValueError(
        f"Unsupported chat provider '{provider}'. "
        "Use openrouter, openai_compatible, or gemini."
    )


def resolve_chat_provider() -> Model:
    """Return the configured chat model (kept for backwards compatibility)."""
    return _build_chat_model(get_settings())


def chat_provider_is_configured() -> bool:
    """True if the currently selected chat provider has an API key available.

    Used to surface a friendly 503 before attempting LLM-backed features
    (chat, reports) instead of failing deep inside the provider SDK.
    """
    settings = get_settings()
    provider = settings.chat_provider.strip().lower()
    if provider in ("gemini", "openrouter", "openai_compatible"):
        return bool(settings.chat_api_key)
    return False


@dataclass
class NotebookChatDeps:
    session: Session
    notebook: Notebook
    current_user: User
    settings: Settings


def get_notebook_chat_agent() -> Agent[NotebookChatDeps, str]:
    model = _build_chat_model(get_settings())
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
