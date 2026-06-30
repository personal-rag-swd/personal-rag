import json
import re
from datetime import UTC, datetime
from typing import Any

from beanie.odm.enums import SortDirection
from pydantic_ai import ModelMessagesTypeAdapter
from pydantic_ai.messages import (
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
    recent_others = (
        other_messages[-recent_limit:]
        if len(other_messages) > recent_limit
        else other_messages
    )
    keep_set = {id(msg) for msg in system_prompts} | {id(msg) for msg in recent_others}
    return [msg for msg in messages if id(msg) in keep_set]


async def load_notebook_chat_history(
    notebook: Notebook,
) -> list[ModelMessage]:
    """Load the full chat history for a notebook from the database.

    Args:
        notebook: The notebook whose message history to fetch.

    Returns:
        Ordered list of pydantic-ai model messages, sorted by sequence number.
    """
    messages = (
        await NotebookMessage.find({"notebook_id": notebook.id})
        .sort(("seq", SortDirection.ASCENDING))
        .to_list()
    )
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

    now = datetime.now(UTC)
    jsonable_new_messages = to_jsonable_python(new_messages)

    last = (
        await NotebookMessage.find({"notebook_id": notebook.id})
        .sort(("seq", SortDirection.DESCENDING))
        .first_or_none()
    )
    max_seq = last.seq if last else 0

    for idx, message in enumerate(jsonable_new_messages, start=max_seq + 1):
        await NotebookMessage(
            notebook_id=notebook.id, seq=idx, message=message
        ).insert()

    notebook.last_active_at = now
    notebook.updated_at = now
    await notebook.save()
    return notebook


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


def parse_chunks_from_context_block(block: str) -> list[dict[str, object]]:
    """Parse SOURCE blocks from a RAG context tool-return string.

    Each block has the form::

        SOURCE [filename=<name> doc_id=<uuid> chunk=<n>]
        <content>

    Args:
        block: Raw string returned by the ``search_notebook_context`` tool.

    Returns:
        List of dicts, each with ``filename``, ``document_id``,
        ``chunk_index``, ``content``, and ``metadata`` keys (the latter carries
        ``chunk_type`` when the source header declares one, e.g. images).
    """
    pattern = r"SOURCE \[filename=(?P<filename>.*?) doc_id=(?P<doc_id>[a-f0-9\-]+) chunk=(?P<chunk>\d+)(?: chunk_type=(?P<chunk_type>\w+))?\]\n(?P<content>.*?)(?=\n+SOURCE \[filename=|\Z)"
    matches = re.finditer(pattern, block, re.DOTALL)
    return [
        {
            "filename": match.group("filename"),
            "document_id": match.group("doc_id"),
            "chunk_index": int(match.group("chunk")),
            "content": match.group("content").strip(),
            "metadata": {"chunk_type": match.group("chunk_type") or "text"},
        }
        for match in matches
    ]


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
    transcript: list[dict[str, object]] = []

    assistant_message_seq = 0
    for idx, message in enumerate(messages):
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
            continue

        if isinstance(message, ModelResponse):
            assistant_message_seq += 1
            parts: list[dict[str, Any]] = []
            if include_reasoning:
                reasoning_chunks = [
                    part.content
                    for part in message.parts
                    if isinstance(part, ThinkingPart)
                ]
                if reasoning_chunks:
                    parts.append(
                        {
                            "type": "reasoning",
                            "content": "\n".join(reasoning_chunks).strip(),
                        }
                    )

            for part in message.parts:
                if isinstance(part, ToolCallPart):
                    tool_name = part.tool_name
                    tool_call_id = part.tool_call_id
                    args = part.args

                    tool_result = None
                    for next_msg in messages[idx + 1 :]:
                        if isinstance(next_msg, ModelRequest):
                            for r_part in next_msg.parts:
                                if (
                                    isinstance(r_part, ToolReturnPart)
                                    and r_part.tool_call_id == tool_call_id
                                ):
                                    tool_result = r_part.content
                                    break
                            if tool_result is not None:
                                break

                    args_text = ""
                    if args:
                        if isinstance(args, dict):
                            args_text = json.dumps(args, indent=2)
                        else:
                            args_text = str(args)

                    parts.append(
                        {
                            "type": "tool-call",
                            "toolCallId": tool_call_id,
                            "toolName": tool_name,
                            "argsText": args_text,
                            "result": tool_result,
                        }
                    )

            assistant_chunks = [
                part.content for part in message.parts if isinstance(part, TextPart)
            ]
            if assistant_chunks:
                parts.append(
                    {"type": "text", "content": "\n".join(assistant_chunks).strip()}
                )

            parts = [
                part
                for part in parts
                if part.get("type") == "tool-call"
                or (isinstance(part.get("content"), str) and part["content"].strip())
            ]
            if parts:
                sources = []
                for prev_msg in reversed(messages[:idx]):
                    if isinstance(prev_msg, ModelResponse):
                        break
                    if isinstance(prev_msg, ModelRequest):
                        for part in prev_msg.parts:
                            if (
                                isinstance(part, ToolReturnPart)
                                and part.tool_name == "search_notebook_context"
                            ):
                                content_str = _tool_return_to_text(part.content)
                                sources.extend(
                                    parse_chunks_from_context_block(content_str)
                                )
                source_lookup: dict[tuple[str, str, int], dict[str, object]] = {}
                for source in sources:
                    source_lookup[
                        (
                            str(source["filename"]),
                            str(source["document_id"]),
                            int(source["chunk_index"]),
                        )
                    ] = source

                references: list[dict[str, object]] = []
                seen_citations: set[tuple[str, str, int]] = set()
                citation_number = 0
                assistant_text = "\n".join(
                    part["content"] for part in parts if part["type"] == "text"
                )
                for match in CITATION_PATTERN.finditer(assistant_text):
                    filename = (
                        match.group("filename_kv")
                        or match.group("filename_legacy")
                        or ""
                    ).strip()
                    chunk_index = int(match.group("chunk"))
                    doc_id = (
                        match.group("doc_id") or match.group("doc_id_end") or ""
                    ).strip()

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

                transcript.append(
                    {
                        "role": "assistant",
                        "parts": parts,
                        "sources": sources,
                        "references": references,
                    }
                )

    return transcript
