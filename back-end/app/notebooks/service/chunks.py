"""Read access to a document's indexed chunks and presigned image URLs."""

from uuid import UUID

from beanie import SortDirection

from app.core.config import Settings
from app.core.s3 import generate_presigned_get_url
from app.notebooks.exceptions import (
    ChunkNotAnImageError,
    ChunkNotFoundError,
    DocumentNotFoundError,
    ImageNotFoundError,
)
from app.notebooks.models import NotebookDocument, NotebookDocumentChunk
from app.notebooks.service.documents import get_notebook_document
from app.notebooks.service.notebooks import get_notebook
from app.users.models import User


def _serialize_chunk(c: NotebookDocumentChunk) -> dict[str, object]:
    return {
        "id": str(c.id),
        "document_id": str(c.document_id),
        "chunk_index": c.chunk_index,
        "content": c.content,
        "metadata": c.chunk_metadata,
    }


async def _fetch_and_serialize_chunks(
    document: NotebookDocument,
) -> list[dict[str, object]]:
    chunks = (
        await NotebookDocumentChunk.find({"document_id": document.id})
        .sort(("chunk_index", SortDirection.ASCENDING))
        .to_list()
    )
    return [_serialize_chunk(c) for c in chunks]


async def get_chunks_by_filename(
    notebook_id: UUID, filename: str, current_user: User
) -> list[dict[str, object]]:
    notebook = await get_notebook(notebook_id, current_user)
    document = await NotebookDocument.find_one(
        {"notebook_id": notebook.id, "filename": filename, "user_id": current_user.id},
    )
    if document is None:
        raise DocumentNotFoundError()
    return await _fetch_and_serialize_chunks(document)


async def get_chunks_by_document_id(
    notebook_id: UUID, document_id: UUID, current_user: User
) -> list[dict[str, object]]:
    notebook = await get_notebook(notebook_id, current_user)
    document = await get_notebook_document(notebook, document_id, current_user)
    return await _fetch_and_serialize_chunks(document)


async def _get_owned_chunk(
    notebook_id: UUID, document_id: UUID, chunk_index: int, current_user: User
) -> tuple[NotebookDocument, NotebookDocumentChunk]:
    """Resolve a chunk after verifying notebook + document ownership."""
    notebook = await get_notebook(notebook_id, current_user)
    document = await get_notebook_document(notebook, document_id, current_user)
    chunk = await NotebookDocumentChunk.find_one(
        {"document_id": document.id, "chunk_index": chunk_index},
    )
    if chunk is None:
        raise ChunkNotFoundError()
    return document, chunk


async def get_single_chunk(
    notebook_id: UUID, document_id: UUID, chunk_index: int, current_user: User
) -> dict[str, object]:
    document, chunk = await _get_owned_chunk(
        notebook_id, document_id, chunk_index, current_user
    )
    return {
        "id": str(chunk.id),
        "document_id": str(chunk.document_id),
        "filename": document.filename,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "metadata": chunk.chunk_metadata,
    }


async def build_chunk_image_url(
    notebook_id: UUID,
    document_id: UUID,
    chunk_index: int,
    current_user: User,
    settings: Settings,
) -> dict[str, str]:
    _document, chunk = await _get_owned_chunk(
        notebook_id, document_id, chunk_index, current_user
    )
    if chunk.chunk_metadata.get("chunk_type") != "image":
        raise ChunkNotAnImageError()
    s3_key = chunk.chunk_metadata.get("s3_key")
    if not s3_key:
        raise ImageNotFoundError()
    url = generate_presigned_get_url(settings, key=str(s3_key))
    return {"url": url}
