from __future__ import annotations

import asyncio
import logging
from functools import lru_cache

from pydantic_ai.providers.openrouter import OpenRouterProvider

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Max texts per API call — keeps payloads within provider limits.
_EMBED_BATCH_SIZE = 96
# Concurrent embedding requests per process — enough to overlap network latency
# without hammering the provider into rate limits.
_EMBED_CONCURRENCY = 4
_embed_semaphore = asyncio.Semaphore(_EMBED_CONCURRENCY)


@lru_cache(maxsize=4)
def _get_provider(api_key: str) -> OpenRouterProvider:
    # Cached so the underlying HTTP client (and its connection pool) is reused
    # across calls instead of re-doing a TLS handshake per request.
    return OpenRouterProvider(api_key=api_key)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts via OpenRouter, returning one vector per text."""
    settings = get_settings()
    provider = _get_provider(settings.chat_api_key)

    async def embed_batch(batch: list[str]) -> list[list[float]]:
        async with _embed_semaphore:
            response = await provider.client.embeddings.create(
                model=settings.embedding_model,
                input=batch,
                dimensions=settings.embedding_dimension,
                encoding_format="float",
            )
        response.data.sort(key=lambda item: item.index)
        return [item.embedding for item in response.data]

    batches = [
        texts[i : i + _EMBED_BATCH_SIZE]
        for i in range(0, len(texts), _EMBED_BATCH_SIZE)
    ]
    results = await asyncio.gather(*(embed_batch(batch) for batch in batches))
    return [embedding for batch in results for embedding in batch]


async def embed_text(text: str) -> list[float]:
    """Embed a single text string."""
    return (await embed_texts([text]))[0]


def embedding_provider_is_configured() -> bool:
    return bool(get_settings().chat_api_key)
