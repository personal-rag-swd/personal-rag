import pytest
from pydantic_ai.exceptions import ModelHTTPError

from app.core.config import Settings, validate_rag_embedding_dimension
from app.notebooks.tools import embeddings
from app.notebooks.tools.embeddings import (
    GeminiEmbeddingAdapter,
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


def test_openai_compatible_embedding_uses_provider_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str | None] = {}

    class DummyAdapter:
        def __init__(
            self,
            *,
            api_key: str,
            model: str,
            base_url: str | None = None,
            output_dimensionality: int | None = None,
        ) -> None:
            captured["api_key"] = api_key
            captured["model"] = model
            captured["base_url"] = base_url
            captured["output_dimensionality"] = output_dimensionality

    monkeypatch.setattr(embeddings, "OpenAICompatibleEmbeddingAdapter", DummyAdapter)
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

    monkeypatch.setattr(
        embeddings, "get_embedding_adapter", lambda _settings: WrongShapeAdapter()
    )
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

    monkeypatch.setattr(
        embeddings, "get_embedding_adapter", lambda _settings: MissingOneAdapter()
    )
    with pytest.raises(RuntimeError, match="Embedding response count mismatch"):
        embed_texts(["one", "two"], settings)


def test_pydantic_ai_embedding_adapter_embeds_texts_correctly() -> None:
    from pydantic_ai import Embedder
    from pydantic_ai.embeddings.test import TestEmbeddingModel

    from app.notebooks.tools.embeddings import PydanticAIEmbeddingAdapter

    embedder = Embedder(TestEmbeddingModel(dimensions=4))
    adapter = PydanticAIEmbeddingAdapter(embedder)

    result = adapter.embed_texts(["one", "two"])
    assert result == [[1.0, 1.0, 1.0, 1.0], [1.0, 1.0, 1.0, 1.0]]


def test_pydantic_ai_embedding_adapter_logs_model_http_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from app.notebooks.tools.embeddings import PydanticAIEmbeddingAdapter

    class FailingEmbedder:
        def embed_documents_sync(self, texts: list[str]):
            raise ModelHTTPError(
                status_code=401,
                model_name="openai/text-embedding-3-small",
                body={"error": "invalid key"},
            )

    adapter = PydanticAIEmbeddingAdapter(FailingEmbedder())
    with pytest.raises(RuntimeError, match="status_code=401"):
        adapter.embed_texts(["one"])

    assert "openai/text-embedding-3-small" in caplog.text
    assert "invalid key" in caplog.text


def test_openai_compatible_adapter_openrouter_settings() -> None:
    from app.notebooks.tools.embeddings import (
        OpenAICompatibleEmbeddingAdapter,
        OpenRouterEmbeddingModel,
    )

    adapter = OpenAICompatibleEmbeddingAdapter(
        api_key="test-key",
        model="test-model",
        base_url="https://openrouter.ai/api/v1",
        output_dimensionality=256,
    )

    # Assert custom OpenRouter model was instantiated and configured
    assert isinstance(adapter.embedder.model, OpenRouterEmbeddingModel)
    assert adapter.embedder.model.check_embedding_ctx_length is False
    assert adapter.embedder.model.model_kwargs == {"encoding_format": "float"}

    # Check that settings are merged into extra_body
    assert adapter.embedder._settings.get("extra_body") == {"encoding_format": "float"}
    assert adapter.embedder._settings.get("dimensions") == 256


def test_validate_rag_embedding_dimension_rejects_non_1536() -> None:
    settings = Settings(
        embedding_provider="openai_compatible",
        embedding_api_key="key",
        embedding_dimension=1024,
    )
    with pytest.raises(RuntimeError, match="EMBEDDING_DIMENSION"):
        validate_rag_embedding_dimension(settings)
