from __future__ import annotations

from functools import lru_cache
from pydantic_ai.models import Model
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from app.core.config import get_settings
from app.notebooks.agent.base import ChatModelProvider


class OpenRouterChatProvider(ChatModelProvider):
    @lru_cache
    def build_model(self) -> Model:
        settings = get_settings()
        provider = OpenRouterProvider(api_key=settings.chat_api_key)
        return OpenRouterModel(settings.chat_model, provider=provider)
