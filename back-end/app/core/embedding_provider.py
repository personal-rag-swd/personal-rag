from __future__ import annotations

import asyncio
import base64
import logging
from functools import lru_cache

import openai
from pydantic_ai.providers.openrouter import OpenRouterProvider

from app.core.config import get_settings
from app.core.exceptions import TransientProviderError

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


async def _create_embeddings(input_payload: object) -> list[list[float]]:
    """Call the embeddings endpoint and return vectors sorted by index.

    Translates retryable provider failures into the shared transient type so
    callers (e.g. ingestion) can re-queue instead of terminally failing a
    perfectly good document on a rate-limit blip.
    """
    settings = get_settings()
    provider = _get_provider(settings.chat_api_key)
    try:
        async with _embed_semaphore:
            response = await provider.client.embeddings.create(
                model=settings.embedding_model,
                input=input_payload,  # type: ignore[arg-type]
                dimensions=settings.embedding_dimension,
                encoding_format="float",
            )
    except (openai.RateLimitError, openai.APIConnectionError) as exc:
        raise TransientProviderError(str(exc)) from exc
    except openai.APIStatusError as exc:
        if exc.status_code >= 500:
            raise TransientProviderError(str(exc)) from exc
        raise
    response.data.sort(key=lambda item: item.index)
    return [item.embedding for item in response.data]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts via OpenRouter, returning one vector per text."""
    batches = [
        texts[i : i + _EMBED_BATCH_SIZE]
        for i in range(0, len(texts), _EMBED_BATCH_SIZE)
    ]
    results = await asyncio.gather(*(_create_embeddings(batch) for batch in batches))
    return [embedding for batch in results for embedding in batch]


async def embed_text(text: str) -> list[float]:
    """Embed a single text string."""
    return (await embed_texts([text]))[0]


async def embed_image(data: bytes, media_type: str) -> list[float]:
    """Embed a single image via OpenRouter's multimodal embeddings input.

    One image per request: images are token-heavy, and per-request isolation
    lets a single bad image fall back to text embedding without failing the
    whole document's other images.
    """
    encoded = base64.b64encode(data).decode("ascii")
    data_uri = f"data:{media_type};base64,{encoded}"
    payload = [{"content": [{"type": "image_url", "image_url": {"url": data_uri}}]}]
    return (await _create_embeddings(payload))[0]
