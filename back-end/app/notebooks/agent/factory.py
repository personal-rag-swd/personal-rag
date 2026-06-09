from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.notebooks.config import NotebookChatSettings, get_notebook_chat_settings
from app.notebooks.models import Notebook
from app.notebooks.prompt import CHAT_SYSTEM_INSTRUCTIONS, build_context_block
from app.notebooks.tools import search_notebook_chunks
from app.users.models import User


@lru_cache(maxsize=1)
def _get_gemini_model() -> Model:
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    settings = get_notebook_chat_settings(get_settings())
    provider = GoogleProvider(api_key=settings.chat_api_key)
    return GoogleModel(settings.chat_model, provider=provider)


@lru_cache(maxsize=1)
def _get_openai_compatible_model() -> Model:
    from dataclasses import replace

    from pydantic_ai.models.openai import OpenAIModel
    from pydantic_ai.profiles.openai import OpenAIModelProfile
    from pydantic_ai.providers.openai import OpenAIProvider

    settings = get_notebook_chat_settings(get_settings())
    provider = OpenAIProvider(
        api_key=settings.chat_api_key,
        base_url=settings.chat_provider_url,
    )
    model = OpenAIModel(settings.chat_model, provider=provider)

    # Disable forced tool choice (required) to maximize compatibility with various
    # open-source models hosted on custom backends that only support tool_choice='auto'
    if hasattr(model, "profile") and isinstance(model.profile, OpenAIModelProfile):
        new_profile = replace(model.profile, openai_supports_tool_choice_required=False)
        model.__dict__["profile"] = new_profile
        if hasattr(model, "_profile"):
            model._profile = new_profile

    return model


@lru_cache(maxsize=1)
def _get_openrouter_model() -> Model:
    from dataclasses import replace

    from pydantic_ai.models.openrouter import OpenRouterModel
    from pydantic_ai.profiles.openai import OpenAIModelProfile
    from pydantic_ai.providers.openrouter import OpenRouterProvider

    settings = get_notebook_chat_settings(get_settings())
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


class GeminiChatProvider:
    def build_model(self) -> Model:
        return _get_gemini_model()


class OpenAICompatibleChatProvider:
    def build_model(self) -> Model:
        return _get_openai_compatible_model()


class OpenRouterChatProvider:
    def build_model(self) -> Model:
        return _get_openrouter_model()


_CHAT_PROVIDER_REGISTRY: dict[str, object] = {
    "openrouter": OpenRouterChatProvider(),
    "openai_compatible": OpenAICompatibleChatProvider(),
    "gemini": GeminiChatProvider(),
}


def _current_chat_settings() -> NotebookChatSettings:
    return get_notebook_chat_settings(get_settings())


def resolve_chat_provider() -> any:
    settings = _current_chat_settings()
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
    settings = _current_chat_settings()
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
            top_k=ctx.deps.settings.notebook_retrieval_top_k,
        )
        return build_context_block(chunks)

    return agent
