from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from pydantic_ai.messages import ModelRequest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, delete, select, func

from app.notebooks.models import Notebook, NotebookDocument, NotebookDocumentChunk
from app.notebooks.schemas import NotebookCreate, NotebookUpdate
from app.notebooks.memory import load_notebook_chat_history
from app.users.models import User


def list_notebooks(session: Session, current_user: User) -> list[Notebook]:
    statement = (
        select(Notebook)
        .where(Notebook.user_id == current_user.id)
        .order_by(Notebook.last_active_at.desc(), Notebook.created_at.desc())
    )
    notebooks = list(session.exec(statement).all())
    for notebook in notebooks:
        populate_notebook_counts(session, notebook)
    return notebooks


def get_notebook(session: Session, notebook_id: UUID, current_user: User) -> Notebook:
    notebook = session.exec(
        select(Notebook).where(
            Notebook.id == notebook_id,
            Notebook.user_id == current_user.id,
        )
    ).first()
    if notebook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")
    return populate_notebook_counts(session, notebook)


def list_notebook_documents(
    session: Session,
    notebook_id: UUID,
    current_user: User,
) -> list[NotebookDocument]:
    notebook = get_notebook(session, notebook_id, current_user)
    statement = (
        select(NotebookDocument)
        .where(NotebookDocument.notebook_id == notebook.id)
        .where(NotebookDocument.user_id == current_user.id)
        .order_by(NotebookDocument.created_at.desc())
    )
    return list(session.exec(statement).all())


def delete_notebook_document(
    session: Session,
    notebook_id: UUID,
    document_id: UUID,
    current_user: User,
) -> None:
    notebook = get_notebook(session, notebook_id, current_user)
    document = session.exec(
        select(NotebookDocument).where(
            NotebookDocument.id == document_id,
            NotebookDocument.notebook_id == notebook.id,
            NotebookDocument.user_id == current_user.id,
        )
    ).first()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    try:
        session.exec(delete(NotebookDocumentChunk).where(NotebookDocumentChunk.document_id == document.id))
        session.delete(document)
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error") from exc


def create_notebook(session: Session, payload: NotebookCreate, current_user: User) -> Notebook:
    notebook = Notebook(
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        tags=payload.tags,
    )
    try:
        session.add(notebook)
        session.commit()
        session.refresh(notebook)
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error") from exc
    notebook.__dict__["document_count"] = 0
    notebook.__dict__["query_count"] = 0
    return notebook


def update_notebook(
    session: Session,
    notebook_id: UUID,
    payload: NotebookUpdate,
    current_user: User,
) -> Notebook:
    notebook = get_notebook(session, notebook_id, current_user)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(notebook, key, value)
    notebook.updated_at = datetime.now(UTC)
    try:
        session.add(notebook)
        session.commit()
        session.refresh(notebook)
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error") from exc
    return populate_notebook_counts(session, notebook)


def touch_notebook(session: Session, notebook_id: UUID, current_user: User) -> Notebook:
    notebook = get_notebook(session, notebook_id, current_user)
    now = datetime.now(UTC)
    notebook.last_active_at = now
    notebook.updated_at = now
    try:
        session.add(notebook)
        session.commit()
        session.refresh(notebook)
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error") from exc
    return populate_notebook_counts(session, notebook)


def populate_notebook_counts(session: Session, notebook: Notebook) -> Notebook:
    # Count documents in the notebook
    doc_count = session.exec(
        select(func.count(NotebookDocument.id))
        .where(NotebookDocument.notebook_id == notebook.id)
    ).one() or 0

    # Count user queries in the notebook chat history
    messages = load_notebook_chat_history(session, notebook)
    query_count = sum(1 for m in messages if isinstance(m, ModelRequest))

    # Attach as dynamic properties directly to __dict__ to bypass Pydantic's __setattr__ validation
    notebook.__dict__["document_count"] = doc_count
    notebook.__dict__["query_count"] = query_count
    return notebook


def delete_notebook(session: Session, notebook_id: UUID, current_user: User) -> None:
    notebook = get_notebook(session, notebook_id, current_user)
    try:
        session.delete(notebook)
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error") from exc

