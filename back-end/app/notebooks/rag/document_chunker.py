from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path

# import numpy as np
# from chonkie import AutoTokenizer, BaseEmbeddings, SemanticChunker
import pymupdf
import pymupdf4llm
from docx import Document as DocxDocument
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import Settings

# from app.notebooks.rag.embeddings_adapter import embed_texts

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


@dataclass(frozen=True)
class ChunkingRequest:
    content: bytes
    filename: str
    source: str
    document_id: str


# ---------------------------------------------------------------------------
# Semantic chunking via Chonkie (commented out – falling back to recursive)
# ---------------------------------------------------------------------------
# class ChonkieEmbeddingAdapter(BaseEmbeddings):
#     def __init__(self, settings: Settings) -> None:
#         super().__init__()
#         self.settings = settings
#
#         model_name = (settings.embedding_model or "").lower()
#         if "gemini" in model_name or "google" in model_name or "gemma" in model_name:
#             try:
#                 self._tokenizer = AutoTokenizer("Xenova/gemma-tokenizer")
#                 logger.info(
#                     "Chonkie adapter using Xenova/gemma-tokenizer for model: %s",
#                     settings.embedding_model,
#                 )
#             except Exception:
#                 self._tokenizer = AutoTokenizer("cl100k_base")
#                 logger.warning(
#                     "Failed to load Xenova/gemma-tokenizer, falling back to cl100k_base"
#                 )
#         else:
#             self._tokenizer = AutoTokenizer("cl100k_base")
#             logger.info("Chonkie adapter using cl100k_base tokenizer")
#
#     def embed(self, text: str) -> np.ndarray:
#         embeddings = embed_texts([text], self.settings)
#         return np.array(embeddings[0])
#
#     def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
#         if not texts:
#             return []
#         logger.info("Chonkie adapter batch embedding %d text(s)", len(texts))
#         embeddings = embed_texts(texts, self.settings)
#         return [np.array(emb) for emb in embeddings]
#
#     @property
#     def dimension(self) -> int:
#         return self.settings.embedding_dimension
#
#     def get_tokenizer(self) -> Any:
#         return self._tokenizer


def split_text(
    text: str,
    *,
    source: str,
    document_id: str,
    settings: Settings | None = None,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[Document]:
    logger.info(
        "Splitting text using RecursiveCharacterTextSplitter for source=%s (chunk_size=%d, chunk_overlap=%d)",
        source,
        chunk_size,
        chunk_overlap,
    )
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
    )
    docs = splitter.create_documents(
        [text],
        metadatas=[{"source": source, "document_id": document_id}],
    )
    logger.info(
        "Split text into %d chunk(s) using RecursiveCharacterTextSplitter",
        len(docs),
    )
    return docs

    # -----------------------------------------------------------------------
    # Semantic chunking via Chonkie (commented out)
    # -----------------------------------------------------------------------
    # logger.info(
    #     "Splitting text using Chonkie SemanticChunker for source=%s (chunk_size=%d)",
    #     source,
    #     chunk_size,
    # )
    # embeddings = ChonkieEmbeddingAdapter(settings)
    # splitter = SemanticChunker(
    #     embedding_model=embeddings,
    #     threshold=0.8,
    #     chunk_size=chunk_size,
    # )
    # chunks = splitter.chunk(text)
    # docs = [
    #     Document(
    #         page_content=c.text,
    #         metadata={
    #             "source": source,
    #             "document_id": document_id,
    #             "start_index": c.start_index,
    #         },
    #     )
    #     for c in chunks
    # ]
    # logger.info("Split text into %d chunk(s) using Chonkie SemanticChunker", len(docs))
    # return docs


def chunk_pdf(
    request: ChunkingRequest,
    *,
    settings: Settings | None = None,
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
    page_chunks = pymupdf4llm.to_markdown(doc, page_chunks=True)
    num_pages = len(page_chunks)
    page_texts = [chunk["text"] for chunk in page_chunks if chunk["text"].strip()]
    extracted_text = "\n".join(page_texts)
    logger.info(
        "PDF text extraction complete (pymupdf4llm). Pages: %d, Total character count: %d",
        num_pages,
        len(extracted_text),
    )
    return split_text(
        extracted_text,
        source=request.source,
        document_id=request.document_id,
        settings=settings,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def chunk_docx(
    request: ChunkingRequest,
    *,
    settings: Settings | None = None,
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
    logger.info(
        "DOCX text extraction complete. Paragraphs count: %d, Tables count: %d, Total character count: %d",
        len(paragraphs),
        len(doc.tables),
        len(extracted_text),
    )
    return split_text(
        extracted_text,
        source=request.source,
        document_id=request.document_id,
        settings=settings,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def chunk_text(
    request: ChunkingRequest,
    *,
    settings: Settings | None = None,
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
    logger.info(
        "Plain text decoding complete. Total character count: %d", len(extracted_text)
    )
    return split_text(
        extracted_text,
        source=request.source,
        document_id=request.document_id,
        settings=settings,
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
    chunk_size = settings.notebook_chunk_size if settings is not None else 1000
    chunk_overlap = settings.notebook_chunk_overlap if settings is not None else 200
    logger.info(
        "Starting chunk_document processing: filename=%s, size=%d bytes, format=%s, chunk_size=%d",
        request.filename,
        len(request.content),
        suffix,
        chunk_size,
    )
    return engine(
        request,
        settings=settings,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
