from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import pymupdf4llm
from docx import Document as DocxDocument
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import Settings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
# Extensions handled by chunk_document() (text-extraction engines below).
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
# Canonical IANA image MIME types keyed by bare extension (no leading dot).
# "image/jpg" is NOT valid — vision providers reject it — so "jpg" maps to
# "image/jpeg". This is the single source of truth for both the upload gate
# (IMAGE_EXTENSIONS) and ingestion_service's media-type lookups.
IMAGE_MEDIA_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
}
# Image extensions are accepted for upload but routed to the async vision
# pipeline in ingestion_service, not to chunk_document().
IMAGE_EXTENSIONS = {f".{ext}" for ext in IMAGE_MEDIA_TYPES}


@dataclass(frozen=True)
class ChunkingRequest:
    content: bytes
    filename: str
    source: str
    document_id: str


def split_text(
    text: str,
    *,
    source: str,
    document_id: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
    )
    docs = splitter.create_documents(
        [text],
        metadatas=[{"source": source, "document_id": document_id}],
    )
    logger.info("Split %s into %d chunk(s)", source, len(docs))
    return docs


def chunk_pdf(
    request: ChunkingRequest,
    *,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[Document]:
    logger.info(
        "Extracting text from PDF: filename=%s, source=%s, size=%d bytes",
        request.filename,
        request.source,
        len(request.content),
    )
    doc = pymupdf.open(stream=request.content, filetype="pdf")
    extracted_text = pymupdf4llm.to_markdown(doc)
    if not isinstance(extracted_text, str):
        raise TypeError(
            f"pymupdf4llm.to_markdown returned unexpected type: {type(extracted_text)}"
        )
    return split_text(
        extracted_text,
        source=request.source,
        document_id=request.document_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def chunk_docx(
    request: ChunkingRequest,
    *,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[Document]:
    logger.info(
        "Extracting text from DOCX: filename=%s, source=%s, size=%d bytes",
        request.filename,
        request.source,
        len(request.content),
    )
    doc = DocxDocument(io.BytesIO(request.content))
    paragraphs = [
        paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()
    ]
    table_rows: list[str] = []
    for table in doc.tables:
        for row in table.rows:
            # Deduplicate adjacent merged cells that repeat the same text
            seen: set[str] = set()
            cells: list[str] = []
            for cell in row.cells:
                text = cell.text.strip()
                if text and text not in seen:
                    seen.add(text)
                    cells.append(text)
            if cells:
                table_rows.append(" | ".join(cells))
    extracted_parts = paragraphs + table_rows
    extracted_text = "\n".join(extracted_parts)
    return split_text(
        extracted_text,
        source=request.source,
        document_id=request.document_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def chunk_text(
    request: ChunkingRequest,
    *,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[Document]:
    logger.info(
        "Extracting text from plain/markdown text: filename=%s, source=%s, size=%d bytes",
        request.filename,
        request.source,
        len(request.content),
    )
    extracted_text = request.content.decode("utf-8", errors="ignore")
    return split_text(
        extracted_text,
        source=request.source,
        document_id=request.document_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


ENGINE_BY_EXTENSION = {
    ".pdf": chunk_pdf,
    ".docx": chunk_docx,
    ".txt": chunk_text,
    ".md": chunk_text,
}


def chunk_document(
    request: ChunkingRequest, settings: Settings | None = None
) -> list[Document]:
    suffix = Path(request.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")

    engine = ENGINE_BY_EXTENSION[suffix]
    chunk_size = settings.notebook_chunk_size if settings is not None else CHUNK_SIZE
    chunk_overlap = (
        settings.notebook_chunk_overlap if settings is not None else CHUNK_OVERLAP
    )
    logger.info(
        "Starting chunk_document processing: filename=%s, size=%d bytes, format=%s, chunk_size=%d",
        request.filename,
        len(request.content),
        suffix,
        chunk_size,
    )
    return engine(
        request,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
