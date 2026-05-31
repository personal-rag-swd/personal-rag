from __future__ import annotations

from functools import lru_cache
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from app.core.config import get_settings
from app.notebooks.agent.base import ChatModelProvider


class GeminiChatProvider(ChatModelProvider):
    @lru_cache
    def build_model(self) -> Model:
        settings = get_settings()
        provider = GoogleProvider(api_key=settings.chat_api_key)
        return GoogleModel(settings.chat_model, provider=provider)
