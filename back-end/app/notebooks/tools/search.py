from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from app.core.config import Settings, validate_rag_embedding_dimension
from app.notebooks.models import Notebook
from app.notebooks.tools.embeddings import embed_texts
from app.users.models import User


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
    validate_rag_embedding_dimension(settings)
    query_vector = embed_texts([query], settings)[0]
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
        WHERE d.notebook_id = :notebook_id
          AND d.user_id = :user_id
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
