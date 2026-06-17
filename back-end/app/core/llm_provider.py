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
    # open-source models hosted on OpenRouter that only support tool_choice='auto'
    if hasattr(model, "profile") and isinstance(model.profile, OpenAIModelProfile):
        new_profile = replace(model.profile, openai_supports_tool_choice_required=False)
        model.__dict__["profile"] = new_profile
        if hasattr(model, "_profile"):
            model._profile = new_profile

    return model


def resolve_chat_provider() -> Model:
    settings = get_settings()
    selected_provider = settings.chat_provider.strip().lower()
    if selected_provider == "openrouter":
        return _get_openrouter_model()
    raise ValueError(
        f"Unsupported chat provider '{selected_provider}'. Use openrouter."
    )


def chat_provider_is_configured() -> bool:
    """True if the currently selected chat provider has an API key available.

    Used to surface a friendly 503 before attempting LLM-backed features
    (chat, reports) instead of failing deep inside the provider SDK.
    """
    settings = get_settings()
    selected_provider = settings.chat_provider.strip().lower()
    if selected_provider == "openrouter":
        return bool(settings.chat_api_key)
    return False
