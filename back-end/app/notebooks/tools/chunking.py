from __future__ import annotations

import io
from pathlib import Path

from docx import Document as DocxDocument
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def chunk_document(
    content: bytes,
    filename: str,
    source: str,
    document_id: str,
) -> list[Document]:
    """Parse and split a document into chunks ready for embedding.

    Supports .pdf, .docx, .txt, and .md files.
    """
    suffix = Path(filename).suffix.lower()

    if suffix in (".txt", ".md"):
        text = content.decode("utf-8", errors="ignore")
    elif suffix == ".pdf":
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    elif suffix == ".docx":
        doc = DocxDocument(io.BytesIO(content))
        text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    else:
        raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")

    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,
    ).create_documents(
        [text],
        metadatas=[{"source": source, "document_id": document_id}],
    )
