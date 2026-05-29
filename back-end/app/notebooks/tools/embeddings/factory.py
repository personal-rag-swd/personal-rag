from __future__ import annotations

import logging

from app.core.config import Settings
from app.notebooks.tools.embeddings.base import EmbeddingAdapter
from app.notebooks.tools.embeddings.providers import GeminiEmbeddingAdapter, OpenAICompatibleEmbeddingAdapter

logger = logging.getLogger(__name__)


def get_embedding_adapter(settings: Settings) -> EmbeddingAdapter:
    """Resolve and build the configured embedding provider adapter directly."""
    provider = settings.embedding_provider.strip().lower()
    
    if provider == "auto":
        provider = "gemini" if settings.gemini_api_key else "openai_compatible"

    if provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("Missing GEMINI_API_KEY for gemini provider")
        return GeminiEmbeddingAdapter(
            api_key=settings.gemini_api_key,
            model=settings.gemini_embedding_model,
            output_dimensionality=settings.embedding_dimensions,
        )
        
    if provider == "openai_compatible":
        api_key = settings.embedding_api_key or settings.openrouter_api_key
        if not api_key:
            raise RuntimeError("Missing embedding API key for openai_compatible provider")
        base_url = settings.embedding_base_url or settings.openrouter_base_url
        return OpenAICompatibleEmbeddingAdapter(
            api_key=api_key,
            base_url=base_url,
            model=settings.embedding_model,
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
    logger.info(
        "Generating embeddings for %d texts using %s (model: %s)",
        len(texts),
        type(adapter).__name__,
        getattr(adapter, "model", "unknown"),
    )
    embeddings = adapter.embed_texts(texts)
    
    if len(embeddings) != len(texts):
        raise RuntimeError(
            f"Embedding response count mismatch: expected {len(texts)} vectors, got {len(embeddings)}"
        )
        
    if settings.embedding_dimensions > 0:
        for idx, embedding in enumerate(embeddings):
            if len(embedding) != settings.embedding_dimensions:
                raise RuntimeError(
                    f"Embedding vector size mismatch at index {idx}: "
                    f"expected {settings.embedding_dimensions}, got {len(embedding)}"
                )
                
    return embeddings
