import json
import re
from datetime import UTC, datetime
from typing import Any

from beanie.odm.enums import SortDirection
from pydantic_ai import ModelMessagesTypeAdapter
from pydantic_ai.messages import (
    BinaryContent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_core import to_jsonable_python

from app.notebooks.models import Notebook, NotebookMessage
from app.notebooks.prompt.context_prompts import parse_chunks_from_context_block

CITATION_PATTERN = re.compile(
    r"\[(?:file=(?P<filename_kv>[^,\]]+)|(?P<filename_legacy>[^,\]]+)),\s*"
    r"(?:doc_id=(?P<doc_id>[^,\]]+),\s*)?"
    r"chunk(?:=|\s+)(?P<chunk>\d+)"
    r"(?:,\s*doc_id=(?P<doc_id_end>[^,\]]+))?\]"
)


async def keep_recent_messages(messages: list[ModelMessage]) -> list[ModelMessage]:
    system_prompts = []
    other_messages = []
    for msg in messages:
        is_system = False
        if isinstance(msg, ModelRequest):
            has_system_part = any(
                isinstance(part, SystemPromptPart) for part in msg.parts
            )
            has_conversational_part = any(
                isinstance(part, (UserPromptPart, ToolReturnPart, RetryPromptPart))
                for part in msg.parts
            )
            if has_system_part or (msg.instructions and not has_conversational_part):
                is_system = True
        if is_system:
            system_prompts.append(msg)
        else:
            other_messages.append(msg)

    recent_limit = 15
    recent_others = other_messages[-recent_limit:]
    # The slice can land between a tool call and its return, leaving the window
    # starting with an orphaned ToolReturnPart — which chat providers reject.
    # Drop leading tool-return requests until the window starts on a clean turn.
    while recent_others and _is_tool_return_request(recent_others[0]):
        recent_others.pop(0)

    keep_set = {id(msg) for msg in system_prompts} | {id(msg) for msg in recent_others}
    return [msg for msg in messages if id(msg) in keep_set]


def _is_tool_return_request(message: ModelMessage) -> bool:
    return isinstance(message, ModelRequest) and any(
        isinstance(part, ToolReturnPart) for part in message.parts
    )


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


def build_user_message_from_agui_payload(
    payload: object,
) -> ModelRequest | None:
    """Extract the latest user turn from an AG-UI chat request body.

    Args:
        payload: The raw AG-UI request body, expected to be a dict with a
            ``messages`` list.

    Returns:
        A ``ModelRequest`` containing the latest user text, or ``None`` when
        no user text is present (e.g. an empty ``messages`` array).
    """
    if not isinstance(payload, dict):
        return None
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return None

    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        text = ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        if text.strip():
            return ModelRequest(parts=[UserPromptPart(content=text)])
        return None
    return None


def extract_scoped_document_ids(payload: object) -> list[object]:
    """Extract the optional document-scope ids from an AG-UI request body.

    The frontend sends the selected document ids under
    ``forwardedProps.documentIds`` to scope chat retrieval to a subset of
    sources. Returns an empty list when no scope is present; the ids are
    returned raw (unvalidated) for the service layer to resolve.
    """
    if not isinstance(payload, dict):
        return []
    forwarded_props = payload.get("forwardedProps")
    if not isinstance(forwarded_props, dict):
        return []
    raw_document_ids = forwarded_props.get("documentIds")
    if not isinstance(raw_document_ids, list):
        return []
    return raw_document_ids


def _tool_return_to_text(content: object) -> str:
    """Coerce a ToolReturnPart's content to the searchable context string.

    ``search_notebook_context`` returns ``list[str | BinaryContent]`` (text
    block + image bytes), which pydantic-ai persists as a raw list; older
    messages stored a plain string. Join the string parts and drop binaries so
    the SOURCE-block regex sees real text rather than a list ``repr``.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(item for item in content if isinstance(item, str))
    return ""


def _sources_from_tool_return(part: ToolReturnPart) -> list[dict[str, object]]:
    """Recover the retrieved-chunk sources carried by a search tool return.

    New messages carry them structurally on the part's ``metadata`` (attached
    by the tool at retrieval time); histories persisted before that change
    fall back to regex-parsing the SOURCE blocks out of the prompt text.
    """
    metadata = part.metadata
    if isinstance(metadata, dict) and isinstance(metadata.get("sources"), list):
        return [source for source in metadata["sources"] if isinstance(source, dict)]
    return parse_chunks_from_context_block(_tool_return_to_text(part.content))


async def extract_notebook_chat_transcript(
    notebook: Notebook,
    *,
    include_reasoning: bool = False,
) -> list[dict[str, object]]:
    """Build a structured transcript from a notebook's raw message history.

    Converts pydantic-ai ``ModelMessage`` objects into a frontend-friendly
    format, resolving tool calls to their results and mapping inline citations
    to their source chunks.

    Args:
        notebook: The notebook to extract the transcript from.
        include_reasoning: When ``True``, include ``ThinkingPart`` content as
            ``reasoning`` parts in assistant turns.

    Returns:
        List of turn dicts. Each user turn has ``role="user"`` and a
        ``parts`` list with a single text entry. Each assistant turn has
        ``role="assistant"``, a ``parts`` list (text, reasoning, and/or
        tool-call entries), a ``sources`` list of all retrieved chunks, and a
        ``references`` list of de-duplicated citations found in the assistant
        text.
    """
    messages = await load_notebook_chat_history(notebook)
    tool_results = _tool_results_by_call_id(messages)

    transcript: list[dict[str, object]] = []
    assistant_message_seq = 0
    # Sources retrieved since the last assistant response; they ground the
    # next assistant turn's citations.
    pending_sources: list[dict[str, object]] = []

    for message in messages:
        if isinstance(message, ModelRequest):
            user_chunks = [
                part.content
                for part in message.parts
                if isinstance(part, UserPromptPart) and isinstance(part.content, str)
            ]
            if user_chunks:
                transcript.append(
                    {
                        "role": "user",
                        "parts": [
                            {"type": "text", "content": "\n".join(user_chunks).strip()}
                        ],
                    }
                )
            for part in message.parts:
                if (
                    isinstance(part, ToolReturnPart)
                    and part.tool_name == "search_notebook_context"
                ):
                    pending_sources.extend(_sources_from_tool_return(part))
            continue

        if isinstance(message, ModelResponse):
            assistant_message_seq += 1
            sources = pending_sources
            pending_sources = []

            parts = _assistant_parts(
                message, tool_results, include_reasoning=include_reasoning
            )
            if not parts:
                continue

            transcript.append(
                {
                    "role": "assistant",
                    "parts": parts,
                    "sources": sources,
                    "references": _build_references(
                        parts, sources, assistant_message_seq
                    ),
                }
            )

    return transcript


def _tool_results_by_call_id(messages: list[ModelMessage]) -> dict[str, object]:
    """Map tool_call_id → returned content in one pass over the history."""
    return {
        part.tool_call_id: part.content
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    }


def _assistant_parts(
    message: ModelResponse,
    tool_results: dict[str, object],
    *,
    include_reasoning: bool,
) -> list[dict[str, Any]]:
    """Convert a ModelResponse into frontend part dicts (reasoning/tool/text)."""
    parts: list[dict[str, Any]] = []

    if include_reasoning:
        reasoning_chunks = [
            part.content for part in message.parts if isinstance(part, ThinkingPart)
        ]
        if reasoning_chunks:
            parts.append(
                {"type": "reasoning", "content": "\n".join(reasoning_chunks).strip()}
            )

    for part in message.parts:
        if isinstance(part, ToolCallPart):
            args = part.args
            args_text = ""
            if args:
                args_text = (
                    json.dumps(args, indent=2) if isinstance(args, dict) else str(args)
                )
            parts.append(
                {
                    "type": "tool-call",
                    "toolCallId": part.tool_call_id,
                    "toolName": part.tool_name,
                    "argsText": args_text,
                    "result": tool_results.get(part.tool_call_id),
                }
            )

    assistant_chunks = [
        part.content for part in message.parts if isinstance(part, TextPart)
    ]
    if assistant_chunks:
        parts.append({"type": "text", "content": "\n".join(assistant_chunks).strip()})

    return [
        part
        for part in parts
        if part.get("type") == "tool-call"
        or (isinstance(part.get("content"), str) and part["content"].strip())
    ]


def _build_references(
    parts: list[dict[str, Any]],
    sources: list[dict[str, object]],
    assistant_message_seq: int,
) -> list[dict[str, object]]:
    """Resolve inline citations in the assistant text against its sources."""
    source_lookup: dict[tuple[str, str, int], dict[str, object]] = {
        (
            str(source["filename"]),
            str(source["document_id"]),
            int(source["chunk_index"]),  # type: ignore[call-overload]
        ): source
        for source in sources
    }

    references: list[dict[str, object]] = []
    seen_citations: set[tuple[str, str, int]] = set()
    citation_number = 0
    assistant_text = "\n".join(
        part["content"] for part in parts if part["type"] == "text"
    )

    for match in CITATION_PATTERN.finditer(assistant_text):
        filename = (
            match.group("filename_kv") or match.group("filename_legacy") or ""
        ).strip()
        chunk_index = int(match.group("chunk"))
        doc_id = (match.group("doc_id") or match.group("doc_id_end") or "").strip()

        source = None
        if doc_id:
            source = source_lookup.get((filename, doc_id, chunk_index))

        if source is None:
            for (f, d, c), src in source_lookup.items():
                if f == filename and c == chunk_index:
                    source = src
                    doc_id = d
                    break
        else:
            doc_id = str(source["document_id"])

        if source is None:
            continue

        source_key = (filename, doc_id, chunk_index)
        if source_key in seen_citations:
            continue
        seen_citations.add(source_key)

        citation_number += 1
        references.append(
            {
                "ref_id": f"{assistant_message_seq}:{citation_number}",
                "citation_number": citation_number,
                "filename": filename,
                "document_id": doc_id,
                "chunk_index": chunk_index,
                "content": source["content"],
                "metadata": source.get("metadata", {}),
            }
        )

    return references
