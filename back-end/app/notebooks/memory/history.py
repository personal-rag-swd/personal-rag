import json
import re
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from pydantic_ai import ModelMessage, ModelMessagesTypeAdapter
from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart
from pydantic_core import to_jsonable_python
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, delete, select

from app.notebooks.models import Notebook, NotebookMessage

CITATION_PATTERN = re.compile(
    r"\[(?:file=(?P<filename_kv>[^,\]]+)|(?P<filename_legacy>[^,\]]+)),\s*"
    r"(?:doc_id=(?P<doc_id>[^,\]]+),\s*)?"
    r"chunk(?:=|\s+)(?P<chunk>\d+)"
    r"(?:,\s*doc_id=(?P<doc_id_end>[^,\]]+))?\]"
)


def load_notebook_chat_history(
    session: Session, notebook: Notebook
) -> list[ModelMessage]:
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
        session.exec(
            delete(NotebookMessage).where(NotebookMessage.notebook_id == notebook.id)
        )
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error"
        ) from exc
    return notebook


def append_notebook_chat_history(
    session: Session,
    notebook: Notebook,
    new_messages: list[ModelMessage],
) -> Notebook:
    if not new_messages:
        return notebook

    now = datetime.now(UTC)
    jsonable_new_messages = to_jsonable_python(new_messages)
    max_seq = (
        session.exec(
            select(NotebookMessage.seq)
            .where(NotebookMessage.notebook_id == notebook.id)
            .order_by(NotebookMessage.seq.desc())
        ).first()
        or 0
    )

    for idx, message in enumerate(jsonable_new_messages, start=max_seq + 1):
        session.add(NotebookMessage(notebook_id=notebook.id, seq=idx, message=message))

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


def build_user_message_from_agui_payload(
    payload: object,
) -> ModelRequest | None:
    """Extract the latest user turn from an AG-UI chat request body.

    The AG-UI adapter passes incoming messages to the agent as ``message_history``
    rather than as a fresh prompt, so they are excluded from
    ``AgentRunResult.new_messages()``. We therefore reconstruct the user's new
    message from the request payload so it can be persisted alongside the
    assistant response. Returns ``None`` when no user text is present (e.g. an
    empty ``messages`` array).
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


def parse_chunks_from_context_block(block: str) -> list[dict[str, object]]:
    pattern = r"SOURCE \[filename=(?P<filename>.*?) doc_id=(?P<doc_id>[a-f0-9\-]+) chunk=(?P<chunk>\d+)\]\n(?P<content>.*?)(?=\n+SOURCE \[filename=|\Z)"
    matches = re.finditer(pattern, block, re.DOTALL)
    return [
        {
            "filename": match.group("filename"),
            "document_id": match.group("doc_id"),
            "chunk_index": int(match.group("chunk")),
            "content": match.group("content").strip(),
        }
        for match in matches
    ]


def extract_notebook_chat_transcript(
    session: Session,
    notebook: Notebook,
    *,
    include_reasoning: bool = False,
) -> list[dict[str, object]]:
    messages = load_notebook_chat_history(session, notebook)
    transcript: list[dict[str, object]] = []

    assistant_message_seq = 0
    for idx, message in enumerate(messages):
        if isinstance(message, ModelRequest):
            user_chunks = [
                part.content
                for part in message.parts
                if getattr(part, "part_kind", "") == "user-prompt"
                and isinstance(getattr(part, "content", None), str)
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
                    if getattr(part, "part_kind", "") == "thinking"
                    and isinstance(getattr(part, "content", None), str)
                ]
                if reasoning_chunks:
                    parts.append(
                        {
                            "type": "reasoning",
                            "content": "\n".join(reasoning_chunks).strip(),
                        }
                    )

            # Extract tool calls
            for part in message.parts:
                if getattr(part, "part_kind", "") == "tool-call":
                    tool_name = getattr(part, "tool_name", "")
                    tool_call_id = getattr(part, "tool_call_id", "")
                    args = getattr(part, "args", "")

                    # Find matching tool return in subsequent messages
                    tool_result = None
                    for next_msg in messages[idx + 1 :]:
                        if isinstance(next_msg, ModelRequest):
                            for r_part in next_msg.parts:
                                if (
                                    getattr(r_part, "part_kind", "") == "tool-return"
                                    and getattr(r_part, "tool_call_id", "")
                                    == tool_call_id
                                ):
                                    tool_result = getattr(r_part, "content", None)
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
                part.content
                for part in message.parts
                if getattr(part, "part_kind", "") == "text"
                and isinstance(getattr(part, "content", None), str)
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
                # scan backward to find search_notebook_context results returned since the previous response
                sources = []
                for prev_msg in reversed(messages[:idx]):
                    if isinstance(prev_msg, ModelResponse):
                        break
                    if isinstance(prev_msg, ModelRequest):
                        for part in prev_msg.parts:
                            if (
                                getattr(part, "part_kind", "") == "tool-return"
                                and getattr(part, "tool_name", "")
                                == "search_notebook_context"
                            ):
                                content_str = str(getattr(part, "content", ""))
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
                        # Fallback for legacy citations or missing doc_id
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
