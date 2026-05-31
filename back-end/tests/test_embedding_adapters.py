import pytest
from pydantic_ai.exceptions import ModelHTTPError

from app.core.config import Settings
from app.notebooks.tools import embeddings as embeddings_module
from app.notebooks.tools.embeddings import _build_embedder, _OpenRouterEmbeddingModel, embed_texts
from pydantic_ai.embeddings.google import GoogleEmbeddingModel
from pydantic_ai.embeddings.openai import OpenAIEmbeddingModel


# ---------------------------------------------------------------------------
# _build_embedder provider selection
# ---------------------------------------------------------------------------

def test_auto_provider_uses_gemini_when_key_present() -> None:
    settings = Settings(
        embedding_provider="auto",
        embedding_api_key="gemini-key",
        embedding_model="gemini-embedding-2",
    )
    embedder = _build_embedder(settings)
    assert isinstance(embedder.model, GoogleEmbeddingModel)


def test_auto_provider_raises_when_no_key() -> None:
    settings = Settings(
        embedding_provider="auto",
        embedding_api_key="",
        embedding_model="text-embedding-3-small",
    )
    # auto falls back to openai_compatible which requires a key
    with pytest.raises(RuntimeError, match="Missing EMBEDDING_API_KEY"):
        _build_embedder(settings)


def test_openai_compatible_embedding_uses_standard_model() -> None:
    settings = Settings(
        embedding_provider="openai_compatible",
        embedding_api_key="embed-key",
        embedding_model="text-embedding-3-small",
        embedding_provider_url="https://api.openai-compatible.example/v1",
    )
    embedder = _build_embedder(settings)
    assert isinstance(embedder.model, OpenAIEmbeddingModel)
    assert not isinstance(embedder.model, _OpenRouterEmbeddingModel)


def test_missing_api_key_raises_for_openai_compatible() -> None:
    settings = Settings(embedding_provider="openai_compatible", embedding_api_key="")
    with pytest.raises(RuntimeError, match="Missing EMBEDDING_API_KEY"):
        _build_embedder(settings)


def test_openrouter_url_uses_custom_model() -> None:
    settings = Settings(
        embedding_provider="openai_compatible",
        embedding_api_key="test-key",
        embedding_model="test-model",
        embedding_provider_url="https://openrouter.ai/api/v1",
        embedding_dimension=256,
    )
    embedder = _build_embedder(settings)
    assert isinstance(embedder.model, _OpenRouterEmbeddingModel)
    assert embedder.model.check_embedding_ctx_length is False
    assert embedder.model.model_kwargs == {"encoding_format": "float"}
    assert embedder._settings.get("extra_body") == {"encoding_format": "float"}
    assert embedder._settings.get("dimensions") == 256


def test_unsupported_provider_raises() -> None:
    settings = Settings(embedding_provider="unknown_provider", embedding_api_key="key")
    with pytest.raises(RuntimeError, match="Unsupported embedding provider"):
        _build_embedder(settings)


# ---------------------------------------------------------------------------
# embed_texts validation
# ---------------------------------------------------------------------------

def test_embed_texts_dimension_mismatch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        embedding_provider="openai_compatible",
        embedding_api_key="key",
        embedding_dimension=8,
    )

    class _FakeResult:
        embeddings = [[0.0, 1.0]]  # wrong size

    class _FakeEmbedder:
        def embed_documents_sync(self, texts):
            return _FakeResult()

    monkeypatch.setattr(embeddings_module, "_build_embedder", lambda _: _FakeEmbedder())
    with pytest.raises(RuntimeError, match="Embedding vector size mismatch"):
        embed_texts(["one"], settings)


def test_embed_texts_count_mismatch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        embedding_provider="openai_compatible",
        embedding_api_key="key",
        embedding_dimension=2,
    )

    class _FakeResult:
        embeddings = [[0.0, 1.0]]  # only 1 vector for 2 texts

    class _FakeEmbedder:
        def embed_documents_sync(self, texts):
            return _FakeResult()

    monkeypatch.setattr(embeddings_module, "_build_embedder", lambda _: _FakeEmbedder())
    with pytest.raises(RuntimeError, match="Embedding response count mismatch"):
        embed_texts(["one", "two"], settings)


def test_embed_texts_model_http_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        embedding_provider="openai_compatible",
        embedding_api_key="key",
        embedding_dimension=0,
    )

    class _FailingEmbedder:
        def embed_documents_sync(self, texts):
            raise ModelHTTPError(
                status_code=401,
                model_name="openai/text-embedding-3-small",
                body={"error": "invalid key"},
            )

    monkeypatch.setattr(embeddings_module, "_build_embedder", lambda _: _FailingEmbedder())
    with pytest.raises(RuntimeError, match="status_code=401"):
        embed_texts(["one"], settings)


def test_embed_texts_returns_empty_for_no_input() -> None:
    settings = Settings(embedding_provider="openai_compatible", embedding_api_key="key")
    assert embed_texts([], settings) == []
