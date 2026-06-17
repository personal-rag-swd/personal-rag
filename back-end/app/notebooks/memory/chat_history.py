import json
import re
from datetime import UTC, datetime
from typing import Any

from pydantic_ai import ModelMessage, ModelMessagesTypeAdapter
from pydantic_ai.messages import ModelRequest, ModelResponse
from pydantic_core import to_jsonable_python

from app.notebooks.models import Notebook, NotebookMessage

CITATION_PATTERN = re.compile(
    r"\[(?:file=(?P<filename_kv>[^,\]]+)|(?P<filename_legacy>[^,\]]+)),\s*"
    r"(?:doc_id=(?P<doc_id>[^,\]]+),\s*)?"
    r"chunk(?:=|\s+)(?P<chunk>\d+)"
    r"(?:,\s*doc_id=(?P<doc_id_end>[^,\]]+))?\]"
)


async def load_notebook_chat_history(
    notebook: Notebook,
) -> list[ModelMessage]:
    messages = await NotebookMessage.find(
        {"notebook_id": notebook.id}
    ).sort(("seq", 1)).to_list()
    rows = [msg.message for msg in messages]
    return list(ModelMessagesTypeAdapter.validate_python(rows))


async def append_notebook_chat_history(
    notebook: Notebook,
    new_messages: list[ModelMessage],
) -> Notebook:
    if not new_messages:
        return notebook

    now = datetime.now(UTC)
    jsonable_new_messages = to_jsonable_python(new_messages)

    last = await NotebookMessage.find(
        {"notebook_id": notebook.id}
    ).sort(("seq", -1)).first_or_none()
    max_seq = last.seq if last else 0

    for idx, message in enumerate(jsonable_new_messages, start=max_seq + 1):
        await NotebookMessage(
            notebook_id=notebook.id, seq=idx, message=message
        ).insert()

    notebook.last_active_at = now
    notebook.updated_at = now
    await notebook.save()
    return notebook


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


async def extract_notebook_chat_transcript(
    notebook: Notebook,
    *,
    include_reasoning: bool = False,
) -> list[dict[str, object]]:
    messages = await load_notebook_chat_history(notebook)
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

            for part in message.parts:
                if getattr(part, "part_kind", "") == "tool-call":
                    tool_name = getattr(part, "tool_name", "")
                    tool_call_id = getattr(part, "tool_call_id", "")
                    args = getattr(part, "args", "")

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
