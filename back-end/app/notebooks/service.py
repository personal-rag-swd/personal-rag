from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from pydantic_ai import ModelMessage, ModelMessagesTypeAdapter
from pydantic_ai.messages import ModelRequest, ModelResponse
from pydantic_core import to_jsonable_python
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, delete, select

from app.notebooks.models import Notebook, NotebookMessage
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


def load_notebook_chat_history(session: Session, notebook: Notebook) -> list[ModelMessage]:
    statement = (
        select(NotebookMessage.message)
        .where(NotebookMessage.notebook_id == notebook.id)
        .order_by(NotebookMessage.seq.asc())
    )
    rows = list(session.exec(statement).all())
    return list(ModelMessagesTypeAdapter.validate_python(rows))


def save_notebook_chat_history(
    session: Session,
    notebook: Notebook,
    messages: list[ModelMessage],
) -> Notebook:
    now = datetime.now(UTC)
    jsonable_messages = to_jsonable_python(messages)
    existing_rows = list(
        session.exec(
            select(NotebookMessage)
            .where(NotebookMessage.notebook_id == notebook.id)
            .order_by(NotebookMessage.seq.asc())
        ).all()
    )
    replace_all = len(existing_rows) > len(jsonable_messages) or any(
        row.message != jsonable_messages[idx] for idx, row in enumerate(existing_rows)
    )

    if replace_all:
        session.exec(delete(NotebookMessage).where(NotebookMessage.notebook_id == notebook.id))
        start_seq = 1
    else:
        start_seq = len(existing_rows) + 1

    for idx, message in enumerate(jsonable_messages[start_seq - 1 :], start=start_seq):
        session.add(NotebookMessage(notebook_id=notebook.id, seq=idx, message=message))

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


def extract_notebook_chat_transcript(
    session: Session,
    notebook: Notebook,
    *,
    include_reasoning: bool = False,
) -> list[dict[str, object]]:
    messages = load_notebook_chat_history(session, notebook)
    transcript: list[dict[str, object]] = []

    for message in messages:
        if isinstance(message, ModelRequest):
            user_chunks = [
                part.content
                for part in message.parts
                if getattr(part, "part_kind", "") == "user-prompt" and isinstance(getattr(part, "content", None), str)
            ]
            if user_chunks:
                transcript.append(
                    {
                        "role": "user",
                        "parts": [{"type": "text", "content": "\n".join(user_chunks).strip()}],
                    }
                )
            continue

        if isinstance(message, ModelResponse):
            parts: list[dict[str, str]] = []
            if include_reasoning:
                reasoning_chunks = [
                    part.content
                    for part in message.parts
                    if getattr(part, "part_kind", "") == "thinking"
                    and isinstance(getattr(part, "content", None), str)
                ]
                if reasoning_chunks:
                    parts.append({"type": "reasoning", "content": "\n".join(reasoning_chunks).strip()})

            assistant_chunks = [
                part.content
                for part in message.parts
                if getattr(part, "part_kind", "") == "text"
                and isinstance(getattr(part, "content", None), str)
            ]
            if assistant_chunks:
                parts.append({"type": "text", "content": "\n".join(assistant_chunks).strip()})

            parts = [part for part in parts if part["content"]]
            if parts:
                transcript.append({"role": "assistant", "parts": parts})

    return transcript


def delete_notebook(session: Session, notebook_id: UUID, current_user: User) -> None:
    notebook = get_notebook(session, notebook_id, current_user)
    try:
        session.delete(notebook)
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error") from exc
