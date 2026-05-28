from functools import lru_cache
from typing import Callable

from pydantic_ai import Agent
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from app.core.config import get_settings
from app.notebooks.prompt import CHAT_SYSTEM_INSTRUCTIONS


@lru_cache
def _get_base_model() -> OpenRouterModel:
    settings = get_settings()
    provider = OpenRouterProvider(api_key=settings.openrouter_api_key)
    return OpenRouterModel(settings.openrouter_model, provider=provider)


def get_notebook_chat_agent(context_retriever: Callable[[str], str] | None = None) -> Agent:
    model = _get_base_model()
    agent = Agent(model, instructions=CHAT_SYSTEM_INSTRUCTIONS)

    if context_retriever is not None:

        @agent.tool_plain
        def search_notebook_context(query: str) -> str:
            """Search indexed notebook sources and return labeled excerpts to cite."""
            return context_retriever(query)

    return agent
