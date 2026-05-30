from __future__ import annotations

from functools import lru_cache
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.core.config import get_settings
from app.notebooks.agent.base import ChatModelProvider


class OpenAICompatibleChatProvider(ChatModelProvider):
    @lru_cache
    def build_model(self) -> Model:
        settings = get_settings()
        provider = OpenAIProvider(
            api_key=settings.chat_api_key,
            base_url=settings.chat_provider_url,
        )
        return OpenAIModel(settings.chat_model, provider=provider)
