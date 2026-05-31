from __future__ import annotations

import logging
from typing import Any

from pydantic_ai import Embedder
from pydantic_ai.embeddings import EmbeddingSettings
from pydantic_ai.embeddings.google import GoogleEmbeddingModel, GoogleEmbeddingSettings
from pydantic_ai.embeddings.openai import OpenAIEmbeddingModel
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider

from app.core.config import Settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OpenRouter quirk: needs a custom model subclass to skip token-count checks
# and force float encoding. Kept as a small local class rather than a full
# module since it is only used inside _build_embedder().
# ---------------------------------------------------------------------------

class _OpenRouterEmbeddingModel(OpenAIEmbeddingModel):
    """OpenAIEmbeddingModel variant with OpenRouter-specific defaults."""

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


def _build_embedder(settings: Settings) -> Embedder:
    """Resolve the configured embedding provider and return a ready-to-use Embedder."""
    provider = settings.embedding_provider.strip().lower()
    if provider == "auto":
        provider = "gemini" if settings.embedding_api_key else "openai_compatible"

    if provider == "gemini":
        if not settings.embedding_api_key:
            raise RuntimeError("Missing EMBEDDING_API_KEY for gemini provider")
        emb_settings = (
            GoogleEmbeddingSettings(dimensions=settings.embedding_dimension)
            if settings.embedding_dimension and settings.embedding_dimension > 0
            else None
        )
        return Embedder(
            GoogleEmbeddingModel(
                settings.embedding_model,
                provider=GoogleProvider(api_key=settings.embedding_api_key),
            ),
            settings=emb_settings,
        )

    if provider == "openai_compatible":
        if not settings.embedding_api_key:
            raise RuntimeError("Missing EMBEDDING_API_KEY for openai_compatible provider")
        base_url: str | None = settings.embedding_provider_url or None
        is_openrouter = base_url is not None and "openrouter.ai" in base_url.lower()

        extra_body: dict[str, Any] = {}
        if is_openrouter:
            extra_body["encoding_format"] = "float"

        emb_settings: EmbeddingSettings | None = None
        if settings.embedding_dimension and settings.embedding_dimension > 0:
            emb_settings = EmbeddingSettings(
                dimensions=settings.embedding_dimension,
                extra_body=extra_body if extra_body else None,
            )
        elif extra_body:
            emb_settings = EmbeddingSettings(extra_body=extra_body)

        openai_provider = OpenAIProvider(api_key=settings.embedding_api_key, base_url=base_url)
        if is_openrouter:
            model = _OpenRouterEmbeddingModel(
                settings.embedding_model,
                provider=openai_provider,
                check_embedding_ctx_length=False,
                model_kwargs={"encoding_format": "float"},
            )
        else:
            model = OpenAIEmbeddingModel(settings.embedding_model, provider=openai_provider)

        return Embedder(model, settings=emb_settings)

    raise RuntimeError(
        f"Unsupported embedding provider '{settings.embedding_provider}'. "
        "Use one of: auto, gemini, openai_compatible."
    )


def embed_texts(texts: list[str], settings: Settings) -> list[list[float]]:
    """Embed a list of text strings using the configured provider."""
    if not texts:
        return []

    embedder = _build_embedder(settings)

    provider_url = settings.embedding_provider_url or (
        "https://generativelanguage.googleapis.com"
        if settings.embedding_provider.strip().lower() == "gemini"
        else "https://api.openai.com/v1"
    )
    logger.info(
        "Embedding model running: provider_url=%s, model=%s, dimension=%s",
        provider_url,
        settings.embedding_model or "unknown",
        settings.embedding_dimension or "unknown",
    )

    try:
        result = embedder.embed_documents_sync(texts)
    except ModelHTTPError as exc:
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
    except Exception as exc:  # pragma: no cover - provider-specific error handling
        if "has no attribute 'data'" in str(exc):
            raise RuntimeError(
                "Embedding provider returned an unexpected response shape. "
                "Check EMBEDDING_PROVIDER_URL and EMBEDDING_API_KEY. "
                "For OpenRouter, use EMBEDDING_PROVIDER_URL=https://openrouter.ai/api/v1."
            ) from exc
        raise

    embeddings = [list(emb) for emb in result.embeddings]

    if len(embeddings) != len(texts):
        raise RuntimeError(
            f"Embedding response count mismatch: expected {len(texts)} vectors, got {len(embeddings)}"
        )

    if settings.embedding_dimension and settings.embedding_dimension > 0:
        for idx, embedding in enumerate(embeddings):
            if len(embedding) != settings.embedding_dimension:
                raise RuntimeError(
                    f"Embedding vector size mismatch at index {idx}: "
                    f"expected {settings.embedding_dimension}, got {len(embedding)}"
                )

    return embeddings
