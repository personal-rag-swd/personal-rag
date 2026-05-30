from __future__ import annotations

from abc import ABC, abstractmethod
from pydantic_ai import Embedder


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
        result = self.embedder.embed_documents_sync(texts)
        return [list(emb) for emb in result.embeddings]
