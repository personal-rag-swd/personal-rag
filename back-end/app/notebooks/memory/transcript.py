"""Rendering a stored message history into a frontend transcript.

Resolves tool calls to their results and maps the inline citations in
assistant text back to the retrieved source chunks that ground them.
"""

import json
import re
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from app.notebooks.memory.persistence import load_notebook_chat_history
from app.notebooks.models import Notebook
from app.notebooks.prompt.context_prompts import parse_chunks_from_context_block

CITATION_PATTERN = re.compile(
    # Preferred short form: [S3], matching the S-label in the SOURCE header.
    r"\[S(?P<source_number>\d+)\]"
    # Legacy verbose forms: [file=..., doc_id=..., chunk=N] / [filename, chunk N].
    r"|\[(?:file=(?P<filename_kv>[^,\]]+)|(?P<filename_legacy>[^,\]]+)),\s*"
    r"(?:doc_id=(?P<doc_id>[^,\]]+),\s*)?"
    r"chunk(?:=|\s+)(?P<chunk>\d+)"
    r"(?:,\s*doc_id=(?P<doc_id_end>[^,\]]+))?\]"
)

# A source keyed by (filename, document_id, chunk_index) for citation lookup.
SourceKey = tuple[str, str, int]


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


def _user_turn(message: ModelRequest) -> dict[str, object] | None:
    """Build a user transcript turn from a request, or None if it has no text."""
    user_chunks = [
        part.content
        for part in message.parts
        if isinstance(part, UserPromptPart) and isinstance(part.content, str)
    ]
    if not user_chunks:
        return None
    return {
        "role": "user",
        "parts": [{"type": "text", "content": "\n".join(user_chunks).strip()}],
    }


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
    # The last non-empty retrieval: a follow-up turn answered without a fresh
    # search cites the previous search's S-labels, so keep them resolvable.
    last_sources: list[dict[str, object]] = []

    for message in messages:
        if isinstance(message, ModelRequest):
            turn = _user_turn(message)
            if turn is not None:
                transcript.append(turn)
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
            if sources:
                last_sources = sources

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
                    # Resolve against this turn's retrieval, or the previous
                    # one when the model answered without searching again.
                    "references": _build_references(
                        parts, sources or last_sources, assistant_message_seq
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


def _index_sources(
    sources: list[dict[str, object]],
) -> dict[SourceKey, dict[str, object]]:
    """Index sources by ``(filename, document_id, chunk_index)`` for lookup."""
    return {
        (
            str(source["filename"]),
            str(source["document_id"]),
            int(source["chunk_index"]),  # type: ignore[call-overload]
        ): source
        for source in sources
    }


def _resolve_citation_source(
    filename: str,
    doc_id: str,
    chunk_index: int,
    source_lookup: dict[SourceKey, dict[str, object]],
) -> tuple[dict[str, object] | None, str]:
    """Resolve one citation to a source, returning ``(source, resolved_doc_id)``.

    Prefers an exact ``(filename, doc_id, chunk_index)`` match, then falls back
    to matching on ``(filename, chunk_index)`` alone (recovering the doc_id from
    the matched source) so citations that omit or misstate the doc_id still
    resolve. Returns ``(None, doc_id)`` when nothing matches.
    """
    if doc_id:
        source = source_lookup.get((filename, doc_id, chunk_index))
        if source is not None:
            return source, str(source["document_id"])

    for (f, _d, c), src in source_lookup.items():
        if f == filename and c == chunk_index:
            return src, str(src["document_id"])
    return None, doc_id


def _build_references(
    parts: list[dict[str, Any]],
    sources: list[dict[str, object]],
    assistant_message_seq: int,
) -> list[dict[str, object]]:
    """Resolve inline citations in the assistant text against its sources."""
    source_lookup = _index_sources(sources)
    number_lookup = {
        int(source["source_number"]): source  # type: ignore[call-overload]
        for source in sources
        if isinstance(source.get("source_number"), int)
    }

    references: list[dict[str, object]] = []
    seen_citations: set[SourceKey] = set()
    citation_number = 0
    assistant_text = "\n".join(
        part["content"] for part in parts if part["type"] == "text"
    )

    for match in CITATION_PATTERN.finditer(assistant_text):
        source_number = match.group("source_number")
        if source_number is not None:
            source = number_lookup.get(int(source_number))
            if source is None:
                continue
            filename = str(source["filename"])
            doc_id = str(source["document_id"])
            chunk_index = int(source["chunk_index"])  # type: ignore[call-overload]
        else:
            filename = (
                match.group("filename_kv") or match.group("filename_legacy") or ""
            ).strip()
            chunk_index = int(match.group("chunk"))
            doc_id = (match.group("doc_id") or match.group("doc_id_end") or "").strip()

            source, doc_id = _resolve_citation_source(
                filename, doc_id, chunk_index, source_lookup
            )
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
