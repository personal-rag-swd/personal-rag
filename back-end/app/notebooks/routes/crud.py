from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlmodel import Session

from app.core.database import get_session
from app.notebooks.schemas import (
    NotebookCreate,
    NotebookPopulateRead,
    NotebookRead,
    NotebookUpdate,
)
from app.notebooks.service import (
    create_notebook,
    delete_notebook,
    get_notebook,
    list_notebooks,
    populate_notebook_metrics,
    touch_notebook,
    update_notebook,
)
from app.users.dependencies import get_current_user
from app.users.models import User

router = APIRouter()


@router.get("/", response_model=list[NotebookRead])
def read_notebooks(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[NotebookRead]:
    return list_notebooks(session, current_user)


@router.post("/", response_model=NotebookRead, status_code=status.HTTP_201_CREATED)
def create_notebook_route(
    payload: NotebookCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> NotebookRead:
    return create_notebook(session, payload, current_user)


@router.get("/{notebook_id}", response_model=NotebookRead)
def read_notebook(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> NotebookRead:
    return get_notebook(session, notebook_id, current_user)


@router.patch("/{notebook_id}", response_model=NotebookRead)
def update_notebook_route(
    notebook_id: UUID,
    payload: NotebookUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> NotebookRead:
    return update_notebook(session, notebook_id, payload, current_user)


@router.post("/{notebook_id}/touch", response_model=NotebookRead)
def touch_notebook_route(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> NotebookRead:
    return touch_notebook(session, notebook_id, current_user)


@router.get("/{notebook_id}/populate", response_model=NotebookPopulateRead)
def populate_notebook_route(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> NotebookPopulateRead:
    return populate_notebook_metrics(session, notebook_id, current_user)


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notebook_route(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    delete_notebook(session, notebook_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
