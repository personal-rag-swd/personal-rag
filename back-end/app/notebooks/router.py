from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status, HTTPException
from pydantic_ai.run import AgentRunResult
from pydantic_ai.ui.ag_ui import AGUIAdapter
from sqlmodel import Session, select
from app.notebooks.models import NotebookDocument, NotebookDocumentChunk

from app.core.config import get_settings
from app.core.database import get_session
from app.notebooks.agent import get_notebook_chat_agent
from app.notebooks.schemas import (
    NotebookChatHistoryMessage,
    NotebookCreate,
    NotebookDocumentRead,
    NotebookRead,
    NotebookUpdate,
)
from app.notebooks.prompt import build_context_block
from app.notebooks.tools import search_notebook_chunks
from app.notebooks.memory import (
    extract_notebook_chat_transcript,
    load_notebook_chat_history,
    save_notebook_chat_history,
)
from app.notebooks.service import (
    create_notebook,
    delete_notebook_document,
    delete_notebook,
    get_notebook,
    list_notebook_documents,
    list_notebooks,
    touch_notebook,
    update_notebook,
)
from app.users.dependencies import get_current_user
from app.users.models import User

router = APIRouter(prefix="/notebooks", tags=["Notebooks"])


@router.get("/", response_model=list[NotebookRead])
def read_notebooks(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list:
    return list_notebooks(session, current_user)


@router.post("/", response_model=NotebookRead, status_code=status.HTTP_201_CREATED)
def create_notebook_route(
    payload: NotebookCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    return create_notebook(session, payload, current_user)


@router.get("/{notebook_id}", response_model=NotebookRead)
def read_notebook(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    return get_notebook(session, notebook_id, current_user)


@router.patch("/{notebook_id}", response_model=NotebookRead)
def update_notebook_route(
    notebook_id: UUID,
    payload: NotebookUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    return update_notebook(session, notebook_id, payload, current_user)


@router.post("/{notebook_id}/touch", response_model=NotebookRead)
def touch_notebook_route(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    return touch_notebook(session, notebook_id, current_user)


@router.get("/{notebook_id}/documents", response_model=list[NotebookDocumentRead])
def read_notebook_documents(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list:
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


@router.post("/{notebook_id}/chat")
async def chat_notebook_route(
    notebook_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    notebook = get_notebook(session, notebook_id, current_user)
    message_history = load_notebook_chat_history(session, notebook)

    settings = get_settings()

    def _context_retriever(query: str) -> str:
        chunks = search_notebook_chunks(
            session,
            notebook=notebook,
            current_user=current_user,
            query=query,
            settings=settings,
            top_k=6,
        )
        return build_context_block(chunks)

    async def persist_chat_history(result: AgentRunResult[object]) -> None:
        save_notebook_chat_history(session, notebook, result.all_messages())

    return await AGUIAdapter.dispatch_request(
        request,
        agent=get_notebook_chat_agent(_context_retriever),
        message_history=message_history,
        conversation_id=str(notebook.id),
        on_complete=persist_chat_history,
    )


@router.get("/{notebook_id}/chat/history", response_model=list[NotebookChatHistoryMessage])
def read_notebook_chat_history(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    include_reasoning: bool = False,
) -> list[dict[str, object]]:
    notebook = get_notebook(session, notebook_id, current_user)
    return extract_notebook_chat_transcript(session, notebook, include_reasoning=include_reasoning)


@router.get("/{notebook_id}/documents/chunks", response_model=list[dict[str, object]])
def read_document_chunks(
    notebook_id: UUID,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list:
    notebook = get_notebook(session, notebook_id, current_user)
    document = session.exec(
        select(NotebookDocument).where(
            NotebookDocument.notebook_id == notebook.id,
            NotebookDocument.filename == filename,
            NotebookDocument.user_id == current_user.id,
        )
    ).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    chunks = session.exec(
        select(NotebookDocumentChunk)
        .where(NotebookDocumentChunk.document_id == document.id)
        .order_by(NotebookDocumentChunk.chunk_index.asc())
    ).all()

    return [
        {
            "id": str(c.id),
            "document_id": str(c.document_id),
            "chunk_index": c.chunk_index,
            "content": c.content,
            "metadata": c.chunk_metadata,
        }
        for c in chunks
    ]


@router.get("/{notebook_id}/documents/{document_id}/chunks", response_model=list[dict[str, object]])
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
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    chunks = session.exec(
        select(NotebookDocumentChunk)
        .where(NotebookDocumentChunk.document_id == document.id)
        .where(NotebookDocumentChunk.notebook_id == notebook.id)
        .where(NotebookDocumentChunk.user_id == current_user.id)
        .order_by(NotebookDocumentChunk.chunk_index.asc())
    ).all()

    return [
        {
            "id": str(c.id),
            "document_id": str(c.document_id),
            "chunk_index": c.chunk_index,
            "content": c.content,
            "metadata": c.chunk_metadata,
        }
        for c in chunks
    ]


@router.get("/{notebook_id}/chunks", response_model=dict[str, object])
def read_notebook_chunk(
    notebook_id: UUID,
    filename: str,
    chunk_index: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    notebook = get_notebook(session, notebook_id, current_user)
    chunk = session.exec(
        select(NotebookDocumentChunk)
        .join(NotebookDocument, NotebookDocument.id == NotebookDocumentChunk.document_id)
        .where(NotebookDocument.filename == filename)
        .where(NotebookDocumentChunk.chunk_index == chunk_index)
        .where(NotebookDocumentChunk.notebook_id == notebook.id)
        .where(NotebookDocumentChunk.user_id == current_user.id)
    ).first()
    if not chunk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found")

    return {
        "content": chunk.content,
        "filename": filename,
        "chunk_index": chunk_index,
    }


@router.get("/{notebook_id}/documents/{document_id}/chunks/{chunk_index}", response_model=dict[str, object])
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
        .where(NotebookDocumentChunk.document_id == document_id)
        .where(NotebookDocumentChunk.chunk_index == chunk_index)
        .where(NotebookDocumentChunk.notebook_id == notebook.id)
        .where(NotebookDocumentChunk.user_id == current_user.id)
    ).first()
    if not chunk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found")

    document = session.exec(
        select(NotebookDocument).where(
            NotebookDocument.id == document_id,
            NotebookDocument.notebook_id == notebook.id,
            NotebookDocument.user_id == current_user.id,
        )
    ).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return {
        "id": str(chunk.id),
        "document_id": str(chunk.document_id),
        "filename": document.filename,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "metadata": chunk.chunk_metadata,
    }


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notebook_route(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    delete_notebook(session, notebook_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
