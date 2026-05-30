import pytest

from app.core.config import Settings
from app.notebooks.tools.embeddings import factory
from app.notebooks.tools.embeddings import (
    GeminiEmbeddingAdapter,
    OpenAICompatibleEmbeddingAdapter,
    embed_texts,
    get_embedding_adapter,
)


def test_auto_provider_prefers_gemini_when_key_present() -> None:
    settings = Settings(
        embedding_provider="auto",
        gemini_api_key="gemini-key",
        gemini_embedding_model="gemini-embedding-2",
    )
    adapter = get_embedding_adapter(settings)
    assert isinstance(adapter, GeminiEmbeddingAdapter)


def test_auto_provider_uses_openai_compatible_without_gemini_key() -> None:
    settings = Settings(
        embedding_provider="auto",
        embedding_api_key="embed-key",
        embedding_model="text-embedding-3-small",
        gemini_api_key="",
    )
    adapter = get_embedding_adapter(settings)
    assert isinstance(adapter, OpenAICompatibleEmbeddingAdapter)


def test_missing_api_key_raises_for_openai_compatible() -> None:
    settings = Settings(embedding_provider="openai_compatible", embedding_api_key="", openrouter_api_key="")
    with pytest.raises(RuntimeError, match="Missing embedding API key"):
        get_embedding_adapter(settings)


def test_embed_texts_dimension_mismatch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(embedding_provider="openai_compatible", embedding_api_key="key", embedding_dimensions=8)

    class WrongShapeAdapter:
        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            return [[0.0, 1.0] for _ in texts]

    monkeypatch.setattr(factory, "get_embedding_adapter", lambda _settings: WrongShapeAdapter())
    with pytest.raises(RuntimeError, match="Embedding vector size mismatch"):
        embed_texts(["one"], settings)


def test_embed_texts_count_mismatch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(embedding_provider="openai_compatible", embedding_api_key="key")

    class MissingOneAdapter:
        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            return [[0.0, 1.0]]

    monkeypatch.setattr(factory, "get_embedding_adapter", lambda _settings: MissingOneAdapter())
    with pytest.raises(RuntimeError, match="Embedding response count mismatch"):
        embed_texts(["one", "two"], settings)


def test_pydantic_ai_embedding_adapter_embeds_texts_correctly() -> None:
    from pydantic_ai import Embedder
    from pydantic_ai.embeddings.test import TestEmbeddingModel
    from app.notebooks.tools.embeddings.base import PydanticAIEmbeddingAdapter

    embedder = Embedder(TestEmbeddingModel(dimensions=4))
    adapter = PydanticAIEmbeddingAdapter(embedder)

    result = adapter.embed_texts(["one", "two"])
    assert result == [[1.0, 1.0, 1.0, 1.0], [1.0, 1.0, 1.0, 1.0]]


