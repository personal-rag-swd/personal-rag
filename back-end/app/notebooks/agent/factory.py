from __future__ import annotations

from typing import Callable
from pydantic_ai import Agent

from app.core.config import get_settings
from app.notebooks.prompt import CHAT_SYSTEM_INSTRUCTIONS
from app.notebooks.agent.base import ChatModelProvider
from app.notebooks.agent.providers import GeminiChatProvider, OpenAICompatibleChatProvider, OpenRouterChatProvider

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
    if selected_provider == "gemini":
        return bool(settings.gemini_api_key)
    if selected_provider == "openrouter":
        return bool(settings.openrouter_api_key)
    return False


def get_notebook_chat_agent(
    context_retriever: Callable[[str], str] | None = None,
) -> Agent:
    model = resolve_chat_provider().build_model()
    agent = Agent(model, instructions=CHAT_SYSTEM_INSTRUCTIONS)

    if context_retriever is not None:

        @agent.tool_plain
        def search_notebook_context(query: str) -> str:
            """Search indexed notebook sources and return labeled excerpts to cite."""
            return context_retriever(query)

    return agent
