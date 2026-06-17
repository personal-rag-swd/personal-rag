from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from pydantic_ai.messages import ModelRequest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, delete, func, select

from app.notebooks.memory import load_notebook_chat_history
from app.notebooks.models import (
    Notebook,
    NotebookDocument,
    NotebookDocumentChunk,
    NotebookReport,
)
from app.notebooks.schemas import NotebookCreate, NotebookUpdate
from app.users.models import User


def list_notebooks(session: Session, current_user: User) -> list[Notebook]:
    statement = (
        select(Notebook)
        .where(Notebook.user_id == current_user.id)
        .order_by(Notebook.last_active_at.desc(), Notebook.created_at.desc())
    )
    return list(session.exec(statement).all())


def get_notebook(session: Session, notebook_id: UUID, current_user: User) -> Notebook:
    notebook = session.exec(
        select(Notebook).where(
            Notebook.id == notebook_id,
            Notebook.user_id == current_user.id,
        )
    ).first()
    if notebook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found"
        )
    return notebook


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    try:
        session.exec(
            delete(NotebookDocumentChunk).where(
                NotebookDocumentChunk.document_id == document.id
            )
        )

        # Delete any note reports referencing this document ID
        note_reports = session.exec(
            select(NotebookReport)
            .where(NotebookReport.notebook_id == notebook.id)
            .where(NotebookReport.user_id == current_user.id)
            .where(NotebookReport.report_type == "note")
        ).all()
        for r in note_reports:
            if isinstance(r.content, dict) and r.content.get("document_id") == str(
                document.id
            ):
                session.delete(r)

        session.delete(document)
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error"
        ) from exc


def create_notebook(
    session: Session, payload: NotebookCreate, current_user: User
) -> Notebook:
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error"
        ) from exc
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error"
        ) from exc
    return notebook


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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error"
        ) from exc
    return notebook


def populate_notebook_metrics(
    session: Session, notebook_id: UUID, current_user: User
) -> Notebook:
    notebook = get_notebook(session, notebook_id, current_user)
    doc_count = (
        session.exec(
            select(func.count(NotebookDocument.id))
            .where(NotebookDocument.notebook_id == notebook.id)
            .where(NotebookDocument.user_id == current_user.id)
        ).one()
        or 0
    )
    messages = load_notebook_chat_history(session, notebook)
    query_count = sum(1 for message in messages if isinstance(message, ModelRequest))
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error"
        ) from exc
