from __future__ import annotations

from dataclasses import replace
from functools import lru_cache

from pydantic_ai.models import Model
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openrouter import OpenRouterProvider

from app.core.config import get_settings


@lru_cache(maxsize=1)
def _get_openrouter_model() -> Model:
    settings = get_settings()
    provider = OpenRouterProvider(api_key=settings.chat_api_key)
    model = OpenRouterModel(settings.chat_model, provider=provider)

    # Disable forced tool choice (required) to maximize compatibility with various
    # open-source models hosted on OpenRouter that only support tool_choice='auto'.
    # ``Model.profile`` is a writable cached_property (pydantic-ai assigns to it
    # internally), so we override it through the public attribute.
    if isinstance(model.profile, OpenAIModelProfile):
        model.profile = replace(
            model.profile, openai_supports_tool_choice_required=False
        )

    return model


def resolve_chat_provider() -> Model:
    return _get_openrouter_model()


def chat_provider_is_configured() -> bool:
    """True if an OpenRouter API key is configured.

    Used to surface a friendly 503 before attempting LLM-backed features
    (chat, reports) instead of failing deep inside the provider SDK.
    """
    return bool(get_settings().chat_api_key)
