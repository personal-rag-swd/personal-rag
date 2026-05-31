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
            raise RuntimeError("Missing EMBEDDING_API_KEY for openai_compatible provider")
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
        
    dimensions = settings.embedding_dimension
    if dimensions > 0:
        for idx, embedding in enumerate(embeddings):
            if len(embedding) != dimensions:
                raise RuntimeError(
                    f"Embedding vector size mismatch at index {idx}: "
                    f"expected {dimensions}, got {len(embedding)}"
                )
                
    return embeddings
