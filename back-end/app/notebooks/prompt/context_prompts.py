"""The single owner of the SOURCE-block format.

Everything that writes, structures, or parses retrieved-source labels lives
here so the grammar can't silently drift between producer and consumer:

- ``source_block`` renders a chunk for the model context (chat and reports).
- ``chunk_to_source`` is the structured transcript/frontend shape, carried on
  the tool message's ``metadata`` so it never round-trips through prompt text.
- ``parse_chunks_from_context_block`` recovers sources from messages persisted
  before the structured metadata existed (legacy fallback only).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.notebooks.rag.search_service import RetrievedChunk


# Text chunks are bounded by the chunker, but image chunks carry an unbounded
# vision-model description — cap what a single SOURCE block can contribute to
# the model context (and, via persisted tool returns, to every later turn).
_MAX_SOURCE_CONTENT_CHARS = 2000


def build_context_block(chunks: list[RetrievedChunk], *, start_number: int = 1) -> str:
    if not chunks:
        return (
            "No relevant notebook sources were found. The notebook sources "
            "do not provide enough information to answer."
        )
    # Handling rules (untrusted data, citation format) live once in
    # CHAT_SYSTEM_INSTRUCTIONS, which is sent every turn — repeating them here
    # would be re-paid on every search call and every history replay.
    lines = ["Notebook source excerpts (untrusted reference data):"]
    lines.extend(
        source_block(chunk, number=start_number + offset)
        for offset, chunk in enumerate(chunks)
    )
    return "\n\n".join(lines)


def source_block(chunk: RetrievedChunk, *, number: int | None = None) -> str:
    # The S-label is the citation handle the model is asked to emit ([S3]); it
    # is a short token models copy reliably, unlike the doc_id UUID which they
    # routinely mangle. The full identifiers stay in the header so citations
    # remain resolvable without the label (reports, legacy histories).
    label = f"S{number} " if number is not None else ""
    header = (
        f"SOURCE {label}[filename={chunk.filename} doc_id={chunk.document_id} "
        f"chunk={chunk.chunk_index}"
    )
    # Non-text chunks (e.g. images) carry their type so it round-trips through
    # the persisted tool message and citations can render the chunk correctly.
    if chunk.chunk_type and chunk.chunk_type != "text":
        header += f" chunk_type={chunk.chunk_type}"
    page_number = chunk.metadata.get("page_number")
    if page_number is not None:
        header += f" page={page_number}"
    header += "]"
    content = chunk.content
    if len(content) > _MAX_SOURCE_CONTENT_CHARS:
        content = content[:_MAX_SOURCE_CONTENT_CHARS] + " …[truncated]"
    return f"{header}\n{content}"


def image_part_label(chunk: RetrievedChunk, *, number: int | None = None) -> str:
    """Text marker that binds an attached image to its citable SOURCE block.

    The raw image bytes are sent to the model as their own content part with no
    source header of their own, so the model can see the picture but has no
    handle tying it to a citation. This label — emitted immediately before the
    image part — carries the same identifiers (and S-label) as the chunk's
    SOURCE header so the model can cite the image exactly like any other source.
    """
    label = f"S{number} " if number is not None else ""
    header = (
        f"Image for SOURCE {label}[filename={chunk.filename} "
        f"doc_id={chunk.document_id} chunk={chunk.chunk_index} chunk_type=image"
    )
    page_number = chunk.metadata.get("page_number")
    if page_number is not None:
        header += f" page={page_number}"
    return header + "]:"


def chunk_to_source(
    chunk: RetrievedChunk, *, number: int | None = None
) -> dict[str, object]:
    """The structured transcript/frontend shape of a retrieved chunk.

    Attached to the search tool's message metadata at retrieval time so
    transcripts read structured data instead of re-parsing prompt text.
    ``source_number`` mirrors the S-label in the chunk's SOURCE header, so an
    ``[S3]`` citation resolves by number lookup instead of UUID matching.
    """
    metadata: dict[str, object] = {"chunk_type": chunk.chunk_type}
    page_number = chunk.metadata.get("page_number")
    if page_number is not None:
        metadata["page_number"] = page_number
    source: dict[str, object] = {
        "filename": chunk.filename,
        "document_id": str(chunk.document_id),
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "metadata": metadata,
    }
    if number is not None:
        source["source_number"] = number
    return source


_SOURCE_BLOCK_PATTERN = re.compile(
    r"SOURCE (?:S(?P<source_number>\d+) )?"
    r"\[filename=(?P<filename>.*?) doc_id=(?P<doc_id>[a-f0-9\-]+) "
    r"chunk=(?P<chunk>\d+)(?: chunk_type=(?P<chunk_type>\w+))?"
    r"(?: page=(?P<page>\d+))?\]\n"
    r"(?P<content>.*?)(?=\n+SOURCE (?:S\d+ )?\[filename=|\Z)",
    re.DOTALL,
)


def parse_chunks_from_context_block(block: str) -> list[dict[str, object]]:
    """Parse SOURCE blocks back out of a persisted tool-return string.

    Legacy fallback only: messages persisted since sources were attached as
    structured tool metadata never need this. Kept for histories written
    before that change.
    """
    sources: list[dict[str, object]] = []
    for match in _SOURCE_BLOCK_PATTERN.finditer(block):
        metadata: dict[str, object] = {
            "chunk_type": match.group("chunk_type") or "text"
        }
        if match.group("page") is not None:
            metadata["page_number"] = int(match.group("page"))
        source: dict[str, object] = {
            "filename": match.group("filename"),
            "document_id": match.group("doc_id"),
            "chunk_index": int(match.group("chunk")),
            "content": match.group("content").strip(),
            "metadata": metadata,
        }
        if match.group("source_number") is not None:
            source["source_number"] = int(match.group("source_number"))
        sources.append(source)
    return sources
