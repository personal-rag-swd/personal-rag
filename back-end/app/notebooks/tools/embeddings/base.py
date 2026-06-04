from __future__ import annotations

from abc import ABC, abstractmethod
import logging

from pydantic_ai import Embedder
from pydantic_ai.exceptions import ModelHTTPError

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
        # Batch to avoid provider limits (e.g. Gemini limit is 100)
        batch_size = 100
        embeddings = []
        try:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                result = self.embedder.embed_documents_sync(batch)
                embeddings.extend([list(emb) for emb in result.embeddings])
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
            # OpenAI-compatible providers can return non-standard response payloads
            # when base URL/auth is misconfigured; surface an actionable message.
            if "has no attribute 'data'" in str(exc):
                raise RuntimeError(
                    "Embedding provider returned an unexpected response shape. "
                    "Check EMBEDDING_PROVIDER_URL and EMBEDDING_API_KEY. "
                    "For OpenRouter, use EMBEDDING_PROVIDER_URL=https://openrouter.ai/api/v1."
                ) from exc
            raise
        return embeddings
