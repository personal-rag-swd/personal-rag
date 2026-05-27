from functools import lru_cache

from pydantic_ai import Agent
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from app.core.config import get_settings


@lru_cache
def get_notebook_chat_agent() -> Agent:
    settings = get_settings()
    provider = OpenRouterProvider(api_key=settings.openrouter_api_key)
    model = OpenRouterModel(settings.openrouter_model, provider=provider)
    return Agent(
        model,
        instructions="You are a helpful, concise chatbot. Keep responses short and conversational.",
    )
