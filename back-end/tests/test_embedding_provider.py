from __future__ import annotations

import base64
from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest

from app.core import embedding_provider
from app.core.exceptions import TransientProviderError

pytestmark = pytest.mark.anyio


class _FakeEmbeddingItem:
    def __init__(self, index: int, embedding: list[float]) -> None:
        self.index = index
        self.embedding = embedding


class _FakeEmbeddingResponse:
    def __init__(self, data: list[_FakeEmbeddingItem]) -> None:
        self.data = data


def _fake_provider(create: Any) -> SimpleNamespace:
    return SimpleNamespace(
        client=SimpleNamespace(embeddings=SimpleNamespace(create=create))
    )


async def test_embed_image_sends_multimodal_data_uri_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """embed_image builds the documented image_url payload shape with a base64
    data URI and returns the single resulting vector.
    """
    calls: list[dict[str, Any]] = []

    async def fake_create(**kwargs: Any) -> _FakeEmbeddingResponse:
        calls.append(kwargs)
        return _FakeEmbeddingResponse([_FakeEmbeddingItem(0, [0.1, 0.2, 0.3])])

    monkeypatch.setattr(
        embedding_provider, "_get_provider", lambda api_key: _fake_provider(fake_create)
    )

    vector = await embedding_provider.embed_image(b"pngbytes", "image/png")

    assert vector == [0.1, 0.2, 0.3]
    assert len(calls) == 1
    payload = calls[0]
    assert payload["input"] == [
        {
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64,"
                        + base64.b64encode(b"pngbytes").decode("ascii")
                    },
                }
            ]
        }
    ]


async def test_embed_image_translates_rate_limit_to_transient_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 429 from the provider surfaces as TransientProviderError so callers
    can re-queue instead of terminally failing.
    """
    response = httpx.Response(
        status_code=429,
        request=httpx.Request("POST", "https://example.test/embeddings"),
    )

    async def fake_create(**kwargs: Any) -> _FakeEmbeddingResponse:
        raise openai.RateLimitError("rate limited", response=response, body=None)

    monkeypatch.setattr(
        embedding_provider, "_get_provider", lambda api_key: _fake_provider(fake_create)
    )

    with pytest.raises(TransientProviderError):
        await embedding_provider.embed_image(b"pngbytes", "image/png")
