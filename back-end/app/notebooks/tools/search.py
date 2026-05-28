from __future__ import annotations

import logging
from hashlib import sha256
from math import sqrt
from uuid import UUID

from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import Settings
from app.notebooks.models import Notebook, NotebookDocument, NotebookDocumentChunk
from app.users.models import User

logger = logging.getLogger(__name__)


class RetrievedChunk(BaseModel):
    document_id: UUID
    filename: str
    chunk_index: int
    content: str
    metadata: dict[str, object]


def _deterministic_embedding(text_value: str, dimensions: int) -> list[float]:
    values: list[float] = []
    i = 0
    while len(values) < dimensions:
        digest = sha256(f"{i}:{text_value}".encode("utf-8")).digest()
        for offset in range(0, len(digest), 4):
            chunk = digest[offset : offset + 4]
            if len(chunk) < 4:
                continue
            val = int.from_bytes(chunk, "big") / 2**32
            values.append((val * 2.0) - 1.0)
            if len(values) == dimensions:
                break
        i += 1
    norm = sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def embed_texts(texts: list[str], settings: Settings) -> list[list[float]]:
    if not texts:
        return []
    if settings.openrouter_api_key:
        client = OpenAI(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url)
        response = client.embeddings.create(model=settings.embedding_model, input=texts)
        return [list(item.embedding) for item in response.data]
    return [_deterministic_embedding(item, settings.embedding_dimensions) for item in texts]


def search_notebook_chunks(
    session: Session,
    *,
    notebook: Notebook,
    current_user: User,
    query: str,
    settings: Settings,
    top_k: int = 6,
) -> list[RetrievedChunk]:
    query_vector = embed_texts([query], settings)[0]
    dialect = session.bind.dialect.name if session.bind is not None else ""

    if dialect == "postgresql":
        stmt = text(
            """
            SELECT
              c.document_id,
              d.filename,
              c.chunk_index,
              c.content,
              c.metadata
            FROM notebook_document_chunk c
            JOIN notebook_document d ON d.id = c.document_id
            WHERE c.notebook_id = :notebook_id
              AND c.user_id = :user_id
              AND d.status = 'indexed'
            ORDER BY c.embedding <=> CAST(:query_vector AS vector)
            LIMIT :top_k
            """
        )
        rows = session.execute(
            stmt,
            {
                "notebook_id": str(notebook.id),
                "user_id": str(current_user.id),
                "query_vector": str(query_vector),
                "top_k": top_k,
            },
        ).all()
        return [
            RetrievedChunk(
                document_id=row[0],
                filename=row[1],
                chunk_index=row[2],
                content=row[3],
                metadata=row[4] or {},
            )
            for row in rows
        ]

    candidates = list(
        session.exec(
            select(NotebookDocumentChunk, NotebookDocument.filename, NotebookDocument.status)
            .join(NotebookDocument, NotebookDocument.id == NotebookDocumentChunk.document_id)
            .where(NotebookDocumentChunk.notebook_id == notebook.id)
            .where(NotebookDocumentChunk.user_id == current_user.id)
            .where(NotebookDocument.status == "indexed")
        ).all()
    )

    def cosine(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=False))

    ranked = sorted(candidates, key=lambda row: cosine(query_vector, row[0].embedding), reverse=True)[:top_k]
    return [
        RetrievedChunk(
            document_id=row[0].document_id,
            filename=row[1],
            chunk_index=row[0].chunk_index,
            content=row[0].content,
            metadata=row[0].chunk_metadata,
        )
        for row in ranked
    ]
