from __future__ import annotations

import logging

from pydantic_ai.providers.openrouter import OpenRouterProvider

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Max texts per API call — keeps payloads within provider limits.
_EMBED_BATCH_SIZE = 96


def _get_provider() -> OpenRouterProvider:
    settings = get_settings()
    return OpenRouterProvider(api_key=settings.chat_api_key)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts via OpenRouter, returning one vector per text."""
    settings = get_settings()
    provider = _get_provider()
    results: list[list[float]] = []
    for i in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch = texts[i : i + _EMBED_BATCH_SIZE]
        response = await provider.client.embeddings.create(
            model=settings.embedding_model,
            input=batch,
            dimensions=settings.embedding_dimension,
            encoding_format="float",
        )
        response.data.sort(key=lambda item: item.index)
        results.extend(item.embedding for item in response.data)
    return results


async def embed_text(text: str) -> list[float]:
    """Embed a single text string."""
    return (await embed_texts([text]))[0]


def embedding_provider_is_configured() -> bool:
    return bool(get_settings().chat_api_key)
