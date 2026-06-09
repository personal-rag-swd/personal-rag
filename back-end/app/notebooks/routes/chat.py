from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic_ai.capabilities.process_history import ProcessHistory
from pydantic_ai.messages import ModelMessage, ModelRequest
from pydantic_ai.run import AgentRunResult
from pydantic_ai.ui.ag_ui import AGUIAdapter
from sqlmodel import Session

from app.core.config import get_settings
from app.core.database import get_session
from app.notebooks.agent import NotebookChatDeps, get_notebook_chat_agent
from app.notebooks.memory import (
    append_notebook_chat_history,
    extract_notebook_chat_transcript,
    load_notebook_chat_history,
)
from app.notebooks.schemas import NotebookChatHistoryMessage
from app.notebooks.service import get_notebook
from app.users.dependencies import get_current_user
from app.users.models import User

router = APIRouter()


@router.post("/{notebook_id}/chat", summary="Start a notebook chat session")
async def chat_notebook_route(
    notebook_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    notebook = get_notebook(session, notebook_id, current_user)
    message_history = load_notebook_chat_history(session, notebook)
    settings = get_settings()

    deps = NotebookChatDeps(
        session=session,
        notebook=notebook,
        current_user=current_user,
        settings=settings,
    )

    async def persist_chat_history(result: AgentRunResult[object]) -> None:
        append_notebook_chat_history(session, notebook, result.new_messages())

    async def keep_recent(messages: list[ModelMessage]) -> list[ModelMessage]:
        system_prompts: list[ModelMessage] = []
        other_messages: list[ModelMessage] = []
        for message in messages:
            is_system = False
            if isinstance(message, ModelRequest):
                part_names = {type(part).__name__ for part in message.parts}
                if "SystemPromptPart" in part_names or (
                    message.instructions
                    and not (
                        part_names
                        & {"UserPromptPart", "ToolReturnPart", "RetryPromptPart"}
                    )
                ):
                    is_system = True

            if is_system:
                system_prompts.append(message)
            else:
                other_messages.append(message)

        recent_limit = 15
        recent_others = (
            other_messages[-recent_limit:]
            if len(other_messages) > recent_limit
            else other_messages
        )
        keep_set = {id(message) for message in system_prompts} | {
            id(message) for message in recent_others
        }
        return [message for message in messages if id(message) in keep_set]

    return await AGUIAdapter.dispatch_request(
        request,
        agent=get_notebook_chat_agent(),
        deps=deps,
        message_history=message_history,
        conversation_id=str(notebook.id),
        on_complete=persist_chat_history,
        capabilities=[ProcessHistory(keep_recent)],
    )


@router.get(
    "/{notebook_id}/chat/history", response_model=list[NotebookChatHistoryMessage]
)
def read_notebook_chat_history(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    include_reasoning: bool = False,
) -> list[dict[str, object]]:
    notebook = get_notebook(session, notebook_id, current_user)
    return extract_notebook_chat_transcript(
        session, notebook, include_reasoning=include_reasoning
    )
