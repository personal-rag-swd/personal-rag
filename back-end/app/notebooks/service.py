from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.notebooks.models import Notebook
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found")
    return notebook


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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error") from exc
    return notebook


def delete_notebook(session: Session, notebook_id: UUID, current_user: User) -> None:
    notebook = get_notebook(session, notebook_id, current_user)
    try:
        session.delete(notebook)
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error") from exc
