from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import uuid4

from app.notebooks.models import NotebookDocument
from app.notebooks.rag.image_ingestion import (
    EMBED_IMAGE_BYTES_KEY,
    build_image_chunk_document,
)


def test_build_image_chunk_document_carries_bytes_under_transient_key() -> None:
    document = SimpleNamespace(id=uuid4(), s3_bucket="bucket")

    chunk = build_image_chunk_document(
        description="a caption",
        document=cast(NotebookDocument, document),
        source="notebooks/doc/photo.png",
        s3_key="notebooks/doc/photo.png",
        media_type="image/png",
        image_bytes=b"abc",
    )

    assert chunk.metadata[EMBED_IMAGE_BYTES_KEY] == b"abc"
    assert chunk.page_content == "a caption"
    assert chunk.metadata["chunk_type"] == "image"
