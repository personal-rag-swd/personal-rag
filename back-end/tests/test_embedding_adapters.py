import pytest

from app.core.config import Settings
from app.notebooks.tools.embeddings import factory
from app.notebooks.tools.embeddings import (
    GeminiEmbeddingAdapter,
    OpenAICompatibleEmbeddingAdapter,
    embed_texts,
    get_embedding_adapter,
)


def test_auto_provider_uses_gemini_when_key_present() -> None:
    settings = Settings(
        embedding_provider="auto",
        embedding_api_key="gemini-key",
        embedding_model="gemini-embedding-2",
    )
    adapter = get_embedding_adapter(settings)
    assert isinstance(adapter, GeminiEmbeddingAdapter)


def test_auto_provider_uses_openai_compatible_without_key() -> None:
    settings = Settings(
        embedding_provider="auto",
        embedding_api_key="",
        embedding_model="text-embedding-3-small",
    )
    # Raising missing key since openai_compatible is default but api key is empty
    with pytest.raises(RuntimeError, match="Missing EMBEDDING_API_KEY"):
        get_embedding_adapter(settings)


def test_openai_compatible_embedding_uses_provider_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}

    class DummyAdapter:
        def __init__(self, *, api_key: str, model: str, base_url: str | None = None, output_dimensionality: int | None = None) -> None:
            captured["api_key"] = api_key
            captured["model"] = model
            captured["base_url"] = base_url
            captured["output_dimensionality"] = output_dimensionality

    monkeypatch.setattr(factory, "OpenAICompatibleEmbeddingAdapter", DummyAdapter)
    settings = Settings(
        embedding_provider="openai_compatible",
        embedding_api_key="embed-key",
        embedding_model="text-embedding-3-small",
        embedding_provider_url="https://api.openai-compatible.example/v1",
    )
    get_embedding_adapter(settings)
    assert captured["base_url"] == "https://api.openai-compatible.example/v1"


def test_missing_api_key_raises_for_openai_compatible() -> None:
    settings = Settings(embedding_provider="openai_compatible", embedding_api_key="")
    with pytest.raises(RuntimeError, match="Missing EMBEDDING_API_KEY"):
        get_embedding_adapter(settings)


def test_embed_texts_dimension_mismatch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        embedding_provider="openai_compatible",
        embedding_api_key="key",
        embedding_dimension=8,
    )

    class WrongShapeAdapter:
        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            return [[0.0, 1.0] for _ in texts]

    monkeypatch.setattr(factory, "get_embedding_adapter", lambda _settings: WrongShapeAdapter())
    with pytest.raises(RuntimeError, match="Embedding vector size mismatch"):
        embed_texts(["one"], settings)


def test_embed_texts_count_mismatch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        embedding_provider="openai_compatible",
        embedding_api_key="key",
        embedding_dimension=2,
    )

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
