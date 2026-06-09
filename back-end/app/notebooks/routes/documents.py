from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from app.core.database import get_session
from app.notebooks.models import NotebookDocument, NotebookDocumentChunk
from app.notebooks.schemas import NotebookDocumentRead
from app.notebooks.service import (
    delete_notebook_document,
    get_notebook,
    list_notebook_documents,
)
from app.users.dependencies import get_current_user
from app.users.models import User

router = APIRouter()


@router.get("/{notebook_id}/documents", response_model=list[NotebookDocumentRead])
def read_notebook_documents(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[NotebookDocumentRead]:
    return list_notebook_documents(session, notebook_id, current_user)


@router.delete(
    "/{notebook_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_notebook_document_route(
    notebook_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    delete_notebook_document(session, notebook_id, document_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{notebook_id}/documents/chunks", response_model=list[dict[str, object]])
def read_document_chunks(
    notebook_id: UUID,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[dict[str, object]]:
    notebook = get_notebook(session, notebook_id, current_user)
    document = session.exec(
        select(NotebookDocument).where(
            NotebookDocument.notebook_id == notebook.id,
            NotebookDocument.filename == filename,
            NotebookDocument.user_id == current_user.id,
        )
    ).first()
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    chunks = session.exec(
        select(NotebookDocumentChunk)
        .where(NotebookDocumentChunk.document_id == document.id)
        .order_by(NotebookDocumentChunk.chunk_index.asc())
    ).all()

    return [
        {
            "id": str(chunk.id),
            "document_id": str(chunk.document_id),
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "metadata": chunk.chunk_metadata,
        }
        for chunk in chunks
    ]


@router.get(
    "/{notebook_id}/documents/{document_id}/chunks",
    response_model=list[dict[str, object]],
)
def read_document_chunks_by_id(
    notebook_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[dict[str, object]]:
    notebook = get_notebook(session, notebook_id, current_user)
    document = session.exec(
        select(NotebookDocument).where(
            NotebookDocument.id == document_id,
            NotebookDocument.notebook_id == notebook.id,
            NotebookDocument.user_id == current_user.id,
        )
    ).first()
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    chunks = session.exec(
        select(NotebookDocumentChunk)
        .where(NotebookDocumentChunk.document_id == document.id)
        .order_by(NotebookDocumentChunk.chunk_index.asc())
    ).all()

    return [
        {
            "id": str(chunk.id),
            "document_id": str(chunk.document_id),
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "metadata": chunk.chunk_metadata,
        }
        for chunk in chunks
    ]


@router.get("/{notebook_id}/chunks", response_model=dict[str, object])
def read_notebook_chunk(
    notebook_id: UUID,
    filename: str,
    chunk_index: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    notebook = get_notebook(session, notebook_id, current_user)
    chunk = session.exec(
        select(NotebookDocumentChunk)
        .join(
            NotebookDocument, NotebookDocument.id == NotebookDocumentChunk.document_id
        )
        .where(NotebookDocument.filename == filename)
        .where(NotebookDocumentChunk.chunk_index == chunk_index)
        .where(NotebookDocument.notebook_id == notebook.id)
        .where(NotebookDocument.user_id == current_user.id)
    ).first()
    if chunk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found"
        )

    return {
        "content": chunk.content,
        "filename": filename,
        "chunk_index": chunk_index,
    }


@router.get(
    "/{notebook_id}/documents/{document_id}/chunks/{chunk_index}",
    response_model=dict[str, object],
)
def read_notebook_chunk_by_document_id(
    notebook_id: UUID,
    document_id: UUID,
    chunk_index: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    notebook = get_notebook(session, notebook_id, current_user)
    chunk = session.exec(
        select(NotebookDocumentChunk)
        .join(
            NotebookDocument, NotebookDocument.id == NotebookDocumentChunk.document_id
        )
        .where(NotebookDocumentChunk.document_id == document_id)
        .where(NotebookDocumentChunk.chunk_index == chunk_index)
        .where(NotebookDocument.notebook_id == notebook.id)
        .where(NotebookDocument.user_id == current_user.id)
    ).first()
    if chunk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found"
        )

    document = session.exec(
        select(NotebookDocument).where(
            NotebookDocument.id == document_id,
            NotebookDocument.notebook_id == notebook.id,
            NotebookDocument.user_id == current_user.id,
        )
    ).first()
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    return {
        "id": str(chunk.id),
        "document_id": str(chunk.document_id),
        "filename": document.filename,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "metadata": chunk.chunk_metadata,
    }
