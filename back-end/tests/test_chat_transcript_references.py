"""Unit tests for resolving inline citations to source references.

These are pure-function tests for the transcript reference builder and the
SOURCE-block parser — the pieces that turn model-emitted citation text into
the structured references the frontend's citation popover relies on.
"""

from uuid import uuid4

from app.notebooks.memory.transcript import _build_references
from app.notebooks.prompt.context_prompts import (
    build_context_block,
    parse_chunks_from_context_block,
)
from app.notebooks.rag.search_service import RetrievedChunk


def _source(
    *,
    filename: str = "report.pdf",
    chunk_index: int = 0,
    source_number: int | None = None,
    content: str = "Source content.",
) -> dict[str, object]:
    source: dict[str, object] = {
        "filename": filename,
        "document_id": str(uuid4()),
        "chunk_index": chunk_index,
        "content": content,
        "metadata": {"chunk_type": "text"},
    }
    if source_number is not None:
        source["source_number"] = source_number
    return source


def _text_parts(text: str) -> list[dict[str, object]]:
    return [{"type": "text", "content": text}]


def test_s_label_citation_resolves_by_source_number() -> None:
    sources = [
        _source(chunk_index=1, source_number=1),
        _source(filename="notes.md", chunk_index=4, source_number=2),
    ]

    references = _build_references(
        _text_parts("Revenue grew [S2]. Costs fell [S2]."), sources, 1
    )

    # Duplicate citations of the same source collapse into one reference.
    assert len(references) == 1
    assert references[0]["citation_number"] == 1
    assert references[0]["filename"] == "notes.md"
    assert references[0]["document_id"] == sources[1]["document_id"]
    assert references[0]["chunk_index"] == 4


def test_unknown_s_label_is_dropped() -> None:
    references = _build_references(
        _text_parts("Fabricated claim [S9]."),
        [_source(source_number=1)],
        1,
    )

    assert references == []


def test_legacy_citation_with_mangled_doc_id_falls_back_to_filename() -> None:
    source = _source(filename="report.pdf", chunk_index=2, source_number=1)

    references = _build_references(
        _text_parts("Claim [file=report.pdf, doc_id=not-a-real-uuid, chunk=2]."),
        [source],
        1,
    )

    # The bogus doc_id is repaired from the matched source, so the frontend's
    # "View source" gets a real document id.
    assert len(references) == 1
    assert references[0]["document_id"] == source["document_id"]


def test_mixed_s_label_and_legacy_citations_number_by_appearance() -> None:
    sources = [
        _source(filename="a.pdf", chunk_index=0, source_number=1),
        _source(filename="b.pdf", chunk_index=3, source_number=2),
    ]

    references = _build_references(
        _text_parts("First [b.pdf, chunk 3]. Second [S1]."), sources, 1
    )

    assert [ref["filename"] for ref in references] == ["b.pdf", "a.pdf"]
    assert [ref["citation_number"] for ref in references] == [1, 2]


def test_source_blocks_round_trip_with_source_numbers() -> None:
    document_id = uuid4()
    chunks = [
        RetrievedChunk(
            document_id=document_id,
            filename="research.pdf",
            chunk_index=3,
            content="First excerpt.",
            metadata={},
        ),
        RetrievedChunk(
            document_id=document_id,
            filename="figure.pdf",
            chunk_index=7,
            content="A bar chart.",
            metadata={"chunk_type": "image"},
            chunk_type="image",
        ),
    ]

    parsed = parse_chunks_from_context_block(
        build_context_block(chunks, start_number=5)
    )

    assert [source["source_number"] for source in parsed] == [5, 6]
    assert parsed[0]["filename"] == "research.pdf"
    assert parsed[0]["content"] == "First excerpt."
    assert parsed[1]["metadata"] == {"chunk_type": "image"}


def test_legacy_source_blocks_parse_without_source_numbers() -> None:
    document_id = uuid4()
    block = (
        f"SOURCE [filename=old.pdf doc_id={document_id} chunk=1]\n"
        "Persisted before S-labels existed."
    )

    parsed = parse_chunks_from_context_block(block)

    assert len(parsed) == 1
    assert "source_number" not in parsed[0]
    assert parsed[0]["chunk_index"] == 1
