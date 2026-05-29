import re
from datetime import UTC, datetime

from pydantic_ai import ModelMessage, ModelMessagesTypeAdapter
from pydantic_ai.messages import ModelRequest, ModelResponse
from pydantic_core import to_jsonable_python
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status
from sqlmodel import Session, delete, select

from app.notebooks.models import Notebook, NotebookMessage

CITATION_PATTERN = re.compile(
    r"\[(?:file=(?P<filename_kv>[^,\]]+)|(?P<filename_legacy>[^,\]]+)),\s*"
    r"(?:doc_id=(?P<doc_id>[^,\]]+),\s*)?"
    r"chunk(?:=|\s+)(?P<chunk>\d+)"
    r"(?:,\s*doc_id=(?P<doc_id_end>[^,\]]+))?\]"
)


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


def append_notebook_chat_history(
    session: Session,
    notebook: Notebook,
    new_messages: list[ModelMessage],
) -> Notebook:
    if not new_messages:
        return notebook

    now = datetime.now(UTC)
    jsonable_new_messages = to_jsonable_python(new_messages)
    max_seq = session.exec(
        select(NotebookMessage.seq)
        .where(NotebookMessage.notebook_id == notebook.id)
        .order_by(NotebookMessage.seq.desc())
    ).first() or 0

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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error") from exc
    return notebook



def parse_chunks_from_context_block(block: str) -> list[dict[str, object]]:
    pattern = r"SOURCE \[filename=(?P<filename>.*?) doc_id=(?P<doc_id>[a-f0-9\-]+) chunk=(?P<chunk>\d+)\]\n(?P<content>.*?)(?=\n+SOURCE \[filename=|\Z)"
    matches = re.finditer(pattern, block, re.DOTALL)
    chunks = []
    for match in matches:
        chunks.append({
            "filename": match.group("filename"),
            "document_id": match.group("doc_id"),
            "chunk_index": int(match.group("chunk")),
            "content": match.group("content").strip()
        })
    return chunks


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
            assistant_message_seq += 1
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
                # scan backward to find search_notebook_context results returned since the previous response
                sources = []
                for prev_msg in reversed(messages[:idx]):
                    if isinstance(prev_msg, ModelResponse):
                        break
                    if isinstance(prev_msg, ModelRequest):
                        for part in prev_msg.parts:
                            if getattr(part, "part_kind", "") == "tool-return" and getattr(part, "tool_name", "") == "search_notebook_context":
                                content_str = str(getattr(part, "content", ""))
                                sources.extend(parse_chunks_from_context_block(content_str))
                source_lookup: dict[tuple[str, str, int], dict[str, object]] = {}
                for source in sources:
                    source_lookup[(str(source["filename"]), str(source["document_id"]), int(source["chunk_index"]))] = source

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
                        match.group("doc_id")
                        or match.group("doc_id_end")
                        or ""
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

                transcript.append({
                    "role": "assistant",
                    "parts": parts,
                    "sources": sources,
                    "references": references,
                })

    return transcript
