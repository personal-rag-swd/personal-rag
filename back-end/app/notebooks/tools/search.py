from __future__ import annotations

import logging
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import Settings
from app.notebooks.models import Notebook, NotebookDocument, NotebookDocumentChunk
from app.notebooks.tools.embeddings import embed_texts
from app.users.models import User

logger = logging.getLogger(__name__)


class RetrievedChunk(BaseModel):
    document_id: UUID
    filename: str
    chunk_index: int
    content: str
    metadata: dict[str, object]


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
