from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.notebooks.models import NotebookDocument
from app.notebooks.rag import document_repository, ingestion_service

pytestmark = pytest.mark.anyio


async def test_run_document_ingestion_embeds_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """embed_texts is called with the chunk texts and vectors land on the chunks."""
    fake_vector = [0.1, 0.2, 0.3]

    inserted: list[Any] = []

    async def fake_embed_texts(texts: list[str]) -> list[list[float]]:
        return [fake_vector for _ in texts]

    async def fake_insert_many(chunks: list[Any]) -> None:
        inserted.extend(chunks)

    async def fake_delete() -> None:
        pass

    document = SimpleNamespace(
        id=uuid4(),
        notebook_id=uuid4(),
        user_id=uuid4(),
        filename="test.txt",
        content="hello world chunk",
        s3_bucket=None,
        s3_key=None,
        status="processing",
        error_message=None,
        updated_at=None,
        save=AsyncMock(),
    )

    monkeypatch.setattr(ingestion_service, "embed_texts", fake_embed_texts)

    with (
        patch.object(
            ingestion_service.NotebookDocumentChunk,
            "find",
            return_value=SimpleNamespace(delete=fake_delete),
        ),
        patch.object(
            ingestion_service.NotebookDocumentChunk,
            "insert_many",
            new=AsyncMock(side_effect=fake_insert_many),
        ),
        patch.object(
            document_repository,
            "domain_event_bus",
            SimpleNamespace(emit=AsyncMock()),
        ),
    ):
        from app.core.config import Settings

        settings = Settings(
            embedding_model="openai/text-embedding-3-small",
            embedding_dimension=3,
        )
        await ingestion_service._run_document_ingestion(
            cast(NotebookDocument, document), settings, None
        )

    assert len(inserted) >= 1
    for chunk in inserted:
        assert chunk.embedding == fake_vector
