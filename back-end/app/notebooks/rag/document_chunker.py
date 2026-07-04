from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pymupdf
import pymupdf4llm
from docx import Document as DocxDocument
from docx.table import Table as DocxTable
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)

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
    chunk_size: int,
    chunk_overlap: int,
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


# pymupdf4llm drops every image from its markdown output (we describe images
# separately via the vision pipeline) and leaves a placeholder in the text,
# e.g. "**==> picture [246 x 81] intentionally omitted <==**". Left in, it gets
# embedded as a text chunk and read back to the user as "the picture was
# omitted", so strip it out. Covers both emitted variants (with and without the
# "intentionally omitted" wording), with or without the surrounding bold markers.
_IMAGE_PLACEHOLDER_RE = re.compile(
    r"[ \t]*\*{0,2}==>\s*picture\s*\[[\d.]+\s*x\s*[\d.]+\]"
    r"(?:\s*intentionally omitted)?\s*<==\*{0,2}[ \t]*\n?",
    re.IGNORECASE,
)
# Collapse the runs of blank lines left behind after removing the placeholders.
_EXCESS_BLANK_LINES_RE = re.compile(r"\n{3,}")


def _extract_pdf_text(request: ChunkingRequest) -> str:
    doc = pymupdf.open(stream=request.content, filetype="pdf")
    extracted_text = pymupdf4llm.to_markdown(doc)
    if not isinstance(extracted_text, str):
        raise TypeError(
            f"pymupdf4llm.to_markdown returned unexpected type: {type(extracted_text)}"
        )
    extracted_text = _IMAGE_PLACEHOLDER_RE.sub("", extracted_text)
    return _EXCESS_BLANK_LINES_RE.sub("\n\n", extracted_text)


def _docx_table_rows(table: DocxTable) -> list[str]:
    rows: list[str] = []
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
            rows.append(" | ".join(cells))
    return rows


def _extract_docx_text(request: ChunkingRequest) -> str:
    doc = DocxDocument(io.BytesIO(request.content))
    parts: list[str] = []
    # iter_inner_content yields paragraphs and tables in document order,
    # unlike doc.paragraphs + doc.tables which regroups them by kind.
    for item in doc.iter_inner_content():
        if isinstance(item, DocxTable):
            parts.extend(_docx_table_rows(item))
        elif item.text.strip():
            parts.append(item.text.strip())
    return "\n".join(parts)


def _extract_plain_text(request: ChunkingRequest) -> str:
    return request.content.decode("utf-8", errors="ignore")


EXTRACTOR_BY_EXTENSION = {
    ".pdf": _extract_pdf_text,
    ".docx": _extract_docx_text,
    ".txt": _extract_plain_text,
    ".md": _extract_plain_text,
}


def chunk_document(request: ChunkingRequest, settings: Settings) -> list[Document]:
    suffix = Path(request.filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")

    logger.info(
        "Extracting text: filename=%s, source=%s, size=%d bytes, format=%s, chunk_size=%d",
        request.filename,
        request.source,
        len(request.content),
        suffix,
        settings.notebook_chunk_size,
    )
    extracted_text = EXTRACTOR_BY_EXTENSION[suffix](request)
    return split_text(
        extracted_text,
        source=request.source,
        document_id=request.document_id,
        chunk_size=settings.notebook_chunk_size,
        chunk_overlap=settings.notebook_chunk_overlap,
    )
