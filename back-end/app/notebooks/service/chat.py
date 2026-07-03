"""Chat orchestration for the notebook chat endpoint.

Keeps the route handler thin: everything between "a chat request arrived" and
"hand off to the AG-UI adapter" — provider gating, history load, quota check,
scope validation, persisting the user turn — lives here, as does persisting the
assistant result once the stream completes.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

from pydantic_ai.messages import ModelMessage
from pydantic_ai.run import AgentRunResult

from app.billing.service import check_quota_and_raise, record_usage_event
from app.core.config import Settings, get_settings
from app.core.llm_provider import chat_provider_is_configured
from app.notebooks.agent import NotebookChatDeps
from app.notebooks.exceptions import LLMNotConfiguredError
from app.notebooks.memory import (
    append_notebook_chat_history,
    build_user_message_from_agui_payload,
    extract_scoped_document_ids,
    load_notebook_chat_history,
)
from app.notebooks.models import Notebook
from app.notebooks.service.documents import resolve_scoped_document_ids
from app.notebooks.service.notebooks import get_notebook
from app.users.models import User

# Cap the history read: keep_recent_messages only retains the last ~15
# conversational messages, so loading a long-lived notebook's entire history
# per request would be wasted work.
_CHAT_HISTORY_READ_LIMIT = 50


@dataclass
class NotebookChatContext:
    """Everything the chat route needs to dispatch to the AG-UI adapter."""

    notebook: Notebook
    deps: NotebookChatDeps
    message_history: list[ModelMessage]


async def prepare_notebook_chat(
    notebook_id: UUID,
    current_user: User,
    request_payload: object,
    settings: Settings,
) -> NotebookChatContext:
    """Validate, load history, check quota, and persist the incoming user turn."""
    if not chat_provider_is_configured():
        raise LLMNotConfiguredError("openrouter")

    notebook = await get_notebook(notebook_id, current_user)
    message_history = await load_notebook_chat_history(
        notebook, limit=_CHAT_HISTORY_READ_LIMIT
    )

    await check_quota_and_raise(current_user.id, 0, settings)

    # Validate the optional document scope before persisting the user turn, so a
    # rejected scope (deleted/foreign/malformed id) doesn't leave an orphaned
    # user message in the history with no assistant reply.
    scoped_document_ids = await resolve_scoped_document_ids(
        notebook, current_user, extract_scoped_document_ids(request_payload)
    )

    new_user_message = build_user_message_from_agui_payload(request_payload)
    if new_user_message is not None:
        await append_notebook_chat_history(notebook, [new_user_message])

    deps = NotebookChatDeps(
        notebook=notebook,
        current_user=current_user,
        settings=settings,
        document_ids=scoped_document_ids,
    )
    return NotebookChatContext(
        notebook=notebook, deps=deps, message_history=message_history
    )


async def persist_notebook_chat_result(
    notebook: Notebook, current_user: User, result: AgentRunResult[object]
) -> None:
    """Persist the assistant's new messages and record token usage on completion."""
    await append_notebook_chat_history(notebook, result.new_messages())
    usage = result.usage
    if usage.total_tokens:
        await record_usage_event(
            user_id=current_user.id,
            quantity=usage.total_tokens,
            idempotency_key=f"chat:{notebook.id}:{uuid4()}",
            settings=get_settings(),
            notebook_id=notebook.id,
            event_metadata={"source": "chat"},
        )
