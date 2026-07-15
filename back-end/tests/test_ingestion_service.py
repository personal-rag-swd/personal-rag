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
        assert chunk.chunk_metadata["embedding_source"] == "text"


async def test_standalone_image_upload_embeds_image_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A standalone image upload embeds the raw bytes directly, keeping the
    caption in ``content`` and dropping the transient bytes key before persist.
    """
    from app.notebooks.rag import image_ingestion

    image_bytes = b"fake-png-bytes"
    fake_image_vector = [0.9, 0.8, 0.7]

    inserted: list[Any] = []
    embed_image_calls: list[tuple[bytes, str]] = []

    async def fake_embed_texts(texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]

    async def fake_embed_image(data: bytes, media_type: str) -> list[float]:
        embed_image_calls.append((data, media_type))
        return fake_image_vector

    async def fake_describe_image(data: bytes, label: str, media_type: str) -> str:
        return "a caption describing the image"

    async def fake_insert_many(chunks: list[Any]) -> None:
        inserted.extend(chunks)

    async def fake_delete() -> None:
        pass

    document = SimpleNamespace(
        id=uuid4(),
        notebook_id=uuid4(),
        user_id=uuid4(),
        filename="photo.png",
        content=None,
        s3_bucket="bucket",
        s3_key="notebooks/doc/photo.png",
        status="processing",
        error_message=None,
        updated_at=None,
        save=AsyncMock(),
    )

    monkeypatch.setattr(ingestion_service, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(ingestion_service, "embed_image", fake_embed_image)
    monkeypatch.setattr(image_ingestion, "describe_image", fake_describe_image)
    monkeypatch.setattr(ingestion_service, "describe_image", fake_describe_image)

    async def fake_get_object_bytes(store: Any, key: str) -> bytes:
        return image_bytes

    monkeypatch.setattr(ingestion_service, "get_object_bytes", fake_get_object_bytes)

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
            cast(NotebookDocument, document), settings, cast(Any, SimpleNamespace())
        )

    assert embed_image_calls == [(image_bytes, "image/png")]
    assert len(inserted) == 1
    chunk = inserted[0]
    assert chunk.content == "a caption describing the image"
    assert chunk.embedding == fake_image_vector
    assert chunk.chunk_metadata["embedding_source"] == "image"
    assert image_ingestion.EMBED_IMAGE_BYTES_KEY not in chunk.chunk_metadata


async def test_image_embedding_falls_back_to_text_on_non_transient_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-transient embed_image failure degrades to text embedding of the
    caption rather than failing the document.
    """
    from app.notebooks.rag import image_ingestion

    image_bytes = b"fake-png-bytes"
    fake_text_vector = [0.1, 0.1, 0.1]

    inserted: list[Any] = []
    embed_texts_calls: list[list[str]] = []

    async def fake_embed_texts(texts: list[str]) -> list[list[float]]:
        embed_texts_calls.append(texts)
        return [fake_text_vector for _ in texts]

    async def fake_embed_image(data: bytes, media_type: str) -> list[float]:
        raise ValueError("bad payload")

    async def fake_describe_image(data: bytes, label: str, media_type: str) -> str:
        return "a caption describing the image"

    async def fake_insert_many(chunks: list[Any]) -> None:
        inserted.extend(chunks)

    async def fake_delete() -> None:
        pass

    document = SimpleNamespace(
        id=uuid4(),
        notebook_id=uuid4(),
        user_id=uuid4(),
        filename="photo.png",
        content=None,
        s3_bucket="bucket",
        s3_key="notebooks/doc/photo.png",
        status="processing",
        error_message=None,
        updated_at=None,
        save=AsyncMock(),
    )

    monkeypatch.setattr(ingestion_service, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(ingestion_service, "embed_image", fake_embed_image)
    monkeypatch.setattr(image_ingestion, "describe_image", fake_describe_image)
    monkeypatch.setattr(ingestion_service, "describe_image", fake_describe_image)

    async def fake_get_object_bytes(store: Any, key: str) -> bytes:
        return image_bytes

    monkeypatch.setattr(ingestion_service, "get_object_bytes", fake_get_object_bytes)

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
            cast(NotebookDocument, document), settings, cast(Any, SimpleNamespace())
        )

    assert ["a caption describing the image"] in embed_texts_calls
    assert len(inserted) == 1
    chunk = inserted[0]
    assert chunk.embedding == fake_text_vector
    assert chunk.chunk_metadata["embedding_source"] == "text"


async def test_image_embedding_transient_error_requeues_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A TransientProviderError from embed_image re-queues the document as
    ``uploaded`` (raising ``TransientIngestionError``) rather than terminally
    failing it. Drives the full ``ingest_document_by_id`` path so the re-queue
    outcome — not just error propagation — is asserted.
    """
    from app.core.exceptions import TransientProviderError
    from app.notebooks.exceptions import TransientIngestionError
    from app.notebooks.rag import image_ingestion

    image_bytes = b"fake-png-bytes"

    async def fake_embed_texts(texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]

    async def fake_embed_image(data: bytes, media_type: str) -> list[float]:
        raise TransientProviderError("rate limited")

    async def fake_describe_image(data: bytes, label: str, media_type: str) -> str:
        return "a caption describing the image"

    document = SimpleNamespace(
        id=uuid4(),
        notebook_id=uuid4(),
        user_id=uuid4(),
        filename="photo.png",
        content=None,
        s3_bucket="bucket",
        s3_key="notebooks/doc/photo.png",
        status="processing",
        error_message=None,
        updated_at=None,
        save=AsyncMock(),
    )

    async def fake_claim(document_id: Any, *, size: Any = None) -> Any:
        return document

    outcome_calls: list[dict[str, Any]] = []

    async def fake_record_outcome(document_id: Any, **kwargs: Any) -> None:
        outcome_calls.append({"document_id": document_id, **kwargs})

    async def fake_get_object_bytes(store: Any, key: str) -> bytes:
        return image_bytes

    monkeypatch.setattr(ingestion_service, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(ingestion_service, "embed_image", fake_embed_image)
    monkeypatch.setattr(image_ingestion, "describe_image", fake_describe_image)
    monkeypatch.setattr(ingestion_service, "describe_image", fake_describe_image)
    monkeypatch.setattr(ingestion_service, "get_object_bytes", fake_get_object_bytes)
    monkeypatch.setattr(ingestion_service, "claim_document_for_ingestion", fake_claim)
    monkeypatch.setattr(
        ingestion_service, "record_ingestion_outcome", fake_record_outcome
    )

    settings = cast(
        Any,
        SimpleNamespace(
            embedding_model="openai/text-embedding-3-small",
            embedding_dimension=3,
            notebook_max_document_bytes=10_000_000,
            notebook_max_chunks_per_document=1000,
        ),
    )

    with pytest.raises(TransientIngestionError):
        await ingestion_service.ingest_document_by_id(
            document.id, settings, store=cast(Any, SimpleNamespace())
        )

    assert outcome_calls == [
        {
            "document_id": document.id,
            "status": "uploaded",
            "error_message": None,
            "event": ingestion_service.DocumentUploaded,
        }
    ]
