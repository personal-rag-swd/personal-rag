from __future__ import annotations

from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


@dataclass(frozen=True)
class ChunkingRequest:
    content: bytes
    filename: str
    source: str
    document_id: str


def split_text(text: str, *, source: str, document_id: str) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,
    )
    return splitter.create_documents(
        [text],
        metadatas=[{"source": source, "document_id": document_id}],
    )
