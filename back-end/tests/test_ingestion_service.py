from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.notebooks.rag import ingestion_service

pytestmark = pytest.mark.anyio


async def test_vector_index_verification_treats_search_errors_as_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = SimpleNamespace(
        id=uuid4(),
        notebook_id=uuid4(),
        user_id=uuid4(),
    )

    async def fake_find_one(*args: object, **kwargs: object) -> object:
        return SimpleNamespace(content="chunk text")

    class FakeFindResult:
        async def to_list(self) -> list[object]:
            return [SimpleNamespace(id=uuid4(), content="chunk text")]

    def raise_vector_search_error(*args: object, **kwargs: object) -> object:
        raise RuntimeError("vector search unavailable")

    monkeypatch.setattr(
        ingestion_service,
        "NotebookDocumentChunk",
        SimpleNamespace(
            find=lambda *args, **kwargs: FakeFindResult(),
            find_one=fake_find_one,
            aggregate=raise_vector_search_error,
        ),
    )

    assert await ingestion_service._is_document_vector_indexed(document) is False
