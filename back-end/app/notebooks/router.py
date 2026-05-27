from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic_ai.run import AgentRunResult
from pydantic_ai.ui.ag_ui import AGUIAdapter
from sqlmodel import Session

from app.core.database import get_session
from app.notebooks.chat import get_notebook_chat_agent
from app.notebooks.schemas import NotebookChatHistoryMessage, NotebookCreate, NotebookRead, NotebookUpdate
from app.notebooks.service import (
    create_notebook,
    delete_notebook,
    extract_notebook_chat_transcript,
    get_notebook,
    list_notebooks,
    load_notebook_chat_history,
    save_notebook_chat_history,
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


@router.post("/{notebook_id}/chat")
async def chat_notebook_route(
    notebook_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    notebook = get_notebook(session, notebook_id, current_user)
    message_history = load_notebook_chat_history(session, notebook)

    async def persist_chat_history(result: AgentRunResult[object]) -> None:
        save_notebook_chat_history(session, notebook, result.all_messages())

    return await AGUIAdapter.dispatch_request(
        request,
        agent=get_notebook_chat_agent(),
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


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notebook_route(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    delete_notebook(session, notebook_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
