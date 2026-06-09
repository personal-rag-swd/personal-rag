from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic_ai import Embedder
from pydantic_ai.embeddings import EmbeddingSettings
from pydantic_ai.embeddings.google import GoogleEmbeddingModel, GoogleEmbeddingSettings
from pydantic_ai.embeddings.openai import OpenAIEmbeddingModel
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)


class EmbeddingAdapter(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class PydanticAIEmbeddingAdapter(EmbeddingAdapter):
    def __init__(self, embedder: Embedder) -> None:
        self.embedder = embedder

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        batch_size = 100
        embeddings = []
        for idx, i in enumerate(range(0, len(texts), batch_size)):
            if idx > 0:
                time.sleep(1.5)  # Proactive delay to avoid rate limit (RPM)

            batch = texts[i : i + batch_size]

            retries = 3
            backoff = 3
            result = None

            for attempt in range(retries):
                try:
                    result = self.embedder.embed_documents_sync(batch)
                    break
                except ModelHTTPError as exc:
                    if exc.status_code == 429 and attempt < retries - 1:
                        sleep_time = backoff * (attempt + 1)
                        logger.warning(
                            "Rate limit hit (429) on attempt %d/%d. Retrying in %d seconds...",
                            attempt + 1,
                            retries,
                            sleep_time,
                        )
                        time.sleep(sleep_time)
                        continue

                    logger.exception(
                        "Embedding provider HTTP error: status_code=%s model=%s body=%r",
                        exc.status_code,
                        exc.model_name,
                        exc.body,
                    )
                    raise RuntimeError(
                        "Embedding provider HTTP error: "
                        f"status_code={exc.status_code}, model={exc.model_name}, body={exc.body!r}"
                    ) from exc
                except (
                    Exception
                ) as exc:  # pragma: no cover - provider-specific error handling
                    # OpenAI-compatible providers can return non-standard response payloads
                    # when base URL/auth is misconfigured; surface an actionable message.
                    if "has no attribute 'data'" in str(exc):
                        raise RuntimeError(
                            "Embedding provider returned an unexpected response shape. "
                            "Check EMBEDDING_PROVIDER_URL and EMBEDDING_API_KEY. "
                            "For OpenRouter, use EMBEDDING_PROVIDER_URL=https://openrouter.ai/api/v1."
                        ) from exc
                    raise

            if result:
                embeddings.extend([list(emb) for emb in result.embeddings])
        return embeddings


class OpenRouterEmbeddingModel(OpenAIEmbeddingModel):
    def __init__(
        self,
        model_name: str,
        *,
        provider: Any = "openai",
        settings: EmbeddingSettings | None = None,
        check_embedding_ctx_length: bool = True,
        model_kwargs: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(model_name, provider=provider, settings=settings)
        self.check_embedding_ctx_length = check_embedding_ctx_length
        self.model_kwargs = model_kwargs or {}


class GeminiEmbeddingAdapter(PydanticAIEmbeddingAdapter):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        output_dimensionality: int | None = None,
    ) -> None:
        self.model = model
        self.output_dimensionality = output_dimensionality
        self.provider_url = "https://generativelanguage.googleapis.com"

        provider = GoogleProvider(api_key=api_key)
        embedding_model = GoogleEmbeddingModel(
            model_name=model,
            provider=provider,
        )
        settings = None
        if output_dimensionality and output_dimensionality > 0:
            settings = GoogleEmbeddingSettings(dimensions=output_dimensionality)

        embedder = Embedder(embedding_model, settings=settings)
        super().__init__(embedder)


class OpenAICompatibleEmbeddingAdapter(PydanticAIEmbeddingAdapter):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        output_dimensionality: int | None = None,
    ) -> None:
        self.model = model
        self.provider_url = base_url or "https://api.openai.com/v1"
        self.output_dimensionality = output_dimensionality

        provider = OpenAIProvider(api_key=api_key, base_url=base_url)

        is_openrouter = base_url is not None and "openrouter.ai" in base_url.lower()

        if is_openrouter:
            embedding_model = OpenRouterEmbeddingModel(
                model_name=model,
                provider=provider,
                check_embedding_ctx_length=False,
                model_kwargs={"encoding_format": "float"},
            )
        else:
            embedding_model = OpenAIEmbeddingModel(
                model_name=model,
                provider=provider,
            )

        settings = None
        extra_body = {}
        if is_openrouter:
            extra_body["encoding_format"] = "float"

        if output_dimensionality and output_dimensionality > 0:
            if extra_body:
                settings = EmbeddingSettings(
                    dimensions=output_dimensionality, extra_body=extra_body
                )
            else:
                settings = EmbeddingSettings(dimensions=output_dimensionality)
        elif extra_body:
            settings = EmbeddingSettings(extra_body=extra_body)

        embedder = Embedder(embedding_model, settings=settings)
        super().__init__(embedder)


def get_embedding_adapter(settings: Settings) -> EmbeddingAdapter:
    """Resolve and build the configured embedding provider adapter directly."""
    provider = settings.embedding_provider.strip().lower()

    if provider == "auto":
        provider = "gemini" if settings.embedding_api_key else "openai_compatible"

    if provider == "gemini":
        if not settings.embedding_api_key:
            raise RuntimeError("Missing EMBEDDING_API_KEY for gemini provider")
        return GeminiEmbeddingAdapter(
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            output_dimensionality=settings.embedding_dimension,
        )

    if provider == "openai_compatible":
        if not settings.embedding_api_key:
            raise RuntimeError(
                "Missing EMBEDDING_API_KEY for openai_compatible provider"
            )
        return OpenAICompatibleEmbeddingAdapter(
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_provider_url,
            model=settings.embedding_model,
            output_dimensionality=settings.embedding_dimension,
        )

    raise RuntimeError(
        f"Unsupported embedding provider '{settings.embedding_provider}'. "
        f"Use one of: auto, gemini, openai_compatible."
    )


def embed_texts(texts: list[str], settings: Settings) -> list[list[float]]:
    """Embed a list of text strings using the configured adapter."""
    if not texts:
        return []

    adapter = get_embedding_adapter(settings)

    provider_url = getattr(adapter, "provider_url", None)
    if provider_url is None:
        provider_url = settings.embedding_provider_url or (
            "https://generativelanguage.googleapis.com"
            if settings.embedding_provider == "gemini"
            else "https://api.openai.com/v1"
        )
    model = getattr(adapter, "model", settings.embedding_model or "unknown")
    dimension = (
        getattr(adapter, "output_dimensionality", None)
        or settings.embedding_dimension
        or "unknown"
    )

    logger.info(
        "Embedding model running: provider_url=%s, model=%s, dimension=%s",
        provider_url,
        model,
        dimension,
    )
    embeddings = adapter.embed_texts(texts)

    if len(embeddings) != len(texts):
        raise RuntimeError(
            f"Embedding response count mismatch: expected {len(texts)} vectors, got {len(embeddings)}"
        )

    dimensions = settings.embedding_dimension
    if dimensions > 0:
        for idx, embedding in enumerate(embeddings):
            if len(embedding) != dimensions:
                raise RuntimeError(
                    f"Embedding vector size mismatch at index {idx}: "
                    f"expected {dimensions}, got {len(embedding)}"
                )

    return embeddings
