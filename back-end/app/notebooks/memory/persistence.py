"""Loading and persisting a notebook's raw pydantic-ai message history."""

from datetime import UTC, datetime

from beanie.odm.enums import SortDirection
from pydantic_ai import ModelMessagesTypeAdapter
from pydantic_ai.messages import (
    BinaryContent,
    ModelMessage,
    ModelRequest,
    ToolReturnPart,
)
from pydantic_core import to_jsonable_python

from app.notebooks.models import Notebook, NotebookMessage


async def load_notebook_chat_history(
    notebook: Notebook,
    *,
    limit: int | None = None,
) -> list[ModelMessage]:
    """Load the chat history for a notebook from the database.

    Args:
        notebook: The notebook whose message history to fetch.
        limit: When set, load only the most recent ``limit`` messages. Callers
            that immediately trim the history (the chat route) should pass a
            limit so old notebooks don't pay an unbounded read per request.

    Returns:
        Ordered list of pydantic-ai model messages, sorted by sequence number.
    """
    query = NotebookMessage.find({"notebook_id": notebook.id})
    if limit is None:
        messages = await query.sort(("seq", SortDirection.ASCENDING)).to_list()
    else:
        messages = (
            await query.sort(("seq", SortDirection.DESCENDING)).limit(limit).to_list()
        )
        messages.reverse()
    rows = [msg.message for msg in messages]
    return list(ModelMessagesTypeAdapter.validate_python(rows))


async def append_notebook_chat_history(
    notebook: Notebook,
    new_messages: list[ModelMessage],
) -> Notebook:
    """Persist new messages to a notebook's chat history.

    Assigns sequential sequence numbers continuing from the last stored
    message, then updates the notebook's ``last_active_at`` and
    ``updated_at`` timestamps.

    Args:
        notebook: The notebook to append messages to.
        new_messages: pydantic-ai messages produced by the latest agent run.

    Returns:
        The updated notebook document.
    """
    if not new_messages:
        return notebook

    _strip_binary_tool_content(new_messages)

    now = datetime.now(UTC)
    jsonable_new_messages = to_jsonable_python(new_messages)

    last = (
        await NotebookMessage.find({"notebook_id": notebook.id})
        .sort(("seq", SortDirection.DESCENDING))
        .first_or_none()
    )
    max_seq = last.seq if last else 0

    await NotebookMessage.insert_many(
        [
            NotebookMessage(notebook_id=notebook.id, seq=idx, message=message)
            for idx, message in enumerate(jsonable_new_messages, start=max_seq + 1)
        ]
    )

    notebook.last_active_at = now
    notebook.updated_at = now
    await notebook.save()
    return notebook


def _strip_binary_tool_content(messages: list[ModelMessage]) -> None:
    """Drop BinaryContent from tool returns before they are persisted.

    ``search_notebook_context`` attaches raw image bytes so the model can see
    the image on the turn it retrieved it. Persisting those bytes would store
    multi-MB base64 payloads in Mongo and re-send them as image input on every
    later turn until they age out of the history window. The image chunk's
    text description in the SOURCE block already carries the citable content.
    """
    for message in messages:
        if not isinstance(message, ModelRequest):
            continue
        for part in message.parts:
            # Exact type check: ToolReturnPart subclasses (e.g. builtin tool
            # returns) constrain ``content`` and never carry our image bytes.
            if type(part) is ToolReturnPart and isinstance(part.content, list):
                part.content = [
                    item for item in part.content if not isinstance(item, BinaryContent)
                ]
