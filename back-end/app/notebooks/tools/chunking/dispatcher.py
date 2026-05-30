from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

from app.notebooks.tools.chunking.base import ChunkingRequest
from app.notebooks.tools.chunking.engines import (
    chunk_docx,
    chunk_markdown,
    chunk_pdf,
    chunk_text,
)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


ENGINE_BY_EXTENSION = {
    ".pdf": chunk_pdf,
    ".docx": chunk_docx,
    ".txt": chunk_text,
    ".md": chunk_markdown,
}


def chunk_document(request: ChunkingRequest) -> list[Document]:
    suffix = Path(request.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")

    engine = ENGINE_BY_EXTENSION[suffix]
    return engine(request)
