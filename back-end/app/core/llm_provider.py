from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from functools import lru_cache
from typing import TYPE_CHECKING

from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models import Model
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openrouter import OpenRouterProvider

from app.core.config import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic_ai import Agent
    from pydantic_ai.messages import UserContent
    from pydantic_ai.run import AgentRunResult

logger = logging.getLogger(__name__)

# HTTP statuses worth retrying: rate limits and transient upstream failures.
TRANSIENT_HTTP_STATUSES = frozenset({429, 500, 502, 503})


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


async def run_agent_with_retry[OutputT](
    agent: Agent[None, OutputT],
    user_prompt: str | Sequence[UserContent],
    *,
    model: Model,
    max_retries: int = 4,
    initial_delay: float = 2.0,
) -> AgentRunResult[OutputT]:
    """Run an agent, retrying transient provider errors with exponential backoff.

    Shared by every one-shot agent invocation (reports, query rewrite, image
    description) so a rate-limit blip doesn't fail the operation outright.
    Non-transient errors and exhausted retries propagate to the caller.
    """
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return await agent.run(user_prompt, model=model)
        except ModelHTTPError as exc:
            if (
                exc.status_code not in TRANSIENT_HTTP_STATUSES
                or attempt >= max_retries - 1
            ):
                raise
            logger.warning(
                "Model HTTP error %s on attempt %d; retrying in %.1fs",
                exc.status_code,
                attempt + 1,
                delay,
            )
            await asyncio.sleep(delay)
            delay *= 2
    raise RuntimeError("Model retry loop exited without a result")
