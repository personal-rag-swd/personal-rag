from uuid import uuid4

from app.notebooks.prompt.context_prompts import build_context_block, image_part_label
from app.notebooks.prompt.system_prompts import CHAT_SYSTEM_INSTRUCTIONS
from app.notebooks.rag.search_service import RetrievedChunk


def test_notebook_core_instructions_require_source_grounding() -> None:
    assert "Answer only from the retrieved source text" in CHAT_SYSTEM_INSTRUCTIONS
    assert (
        "If the retrieved sources do not contain enough evidence"
        in CHAT_SYSTEM_INSTRUCTIONS
    )
    # Citations use the short S-label as the primary handle (models copy short
    # tokens reliably; UUIDs get mangled), with the legacy format as fallback.
    assert "[S3]" in CHAT_SYSTEM_INSTRUCTIONS
    assert "[filename, chunk N]" in CHAT_SYSTEM_INSTRUCTIONS
    assert "Do not fabricate filenames" in CHAT_SYSTEM_INSTRUCTIONS
    # Images must be citable, otherwise they never appear in the references.
    assert "Image sources are citable" in CHAT_SYSTEM_INSTRUCTIONS


def test_image_part_label_carries_source_identifiers() -> None:
    document_id = uuid4()
    label = image_part_label(
        RetrievedChunk(
            document_id=document_id,
            filename="figure.pdf",
            chunk_index=7,
            content="A bar chart of quarterly revenue.",
            metadata={"chunk_type": "image"},
            chunk_type="image",
        ),
        number=4,
    )

    # The label prefixes the raw image bytes so the model can bind the picture it
    # sees to the same identifiers the SOURCE header carries, and cite it.
    assert "SOURCE S4 [" in label
    assert "filename=figure.pdf" in label
    assert f"doc_id={document_id}" in label
    assert "chunk=7" in label
    assert "chunk_type=image" in label


def test_context_block_labels_sources_for_citation() -> None:
    document_id = uuid4()
    context = build_context_block(
        [
            RetrievedChunk(
                document_id=document_id,
                filename="research-notes.pdf",
                chunk_index=3,
                content="Notebook content from the source.",
                metadata={},
            ),
            RetrievedChunk(
                document_id=document_id,
                filename="research-notes.pdf",
                chunk_index=5,
                content="More notebook content.",
                metadata={},
            ),
        ],
        start_number=2,
    )

    # Citation/handling rules live once in CHAT_SYSTEM_INSTRUCTIONS; the
    # context block itself only labels the excerpts. Each excerpt carries an
    # S-label the model cites, numbered sequentially from start_number so a
    # second search call in the same run keeps numbering unique.
    assert context.startswith("Notebook source excerpts (untrusted reference data):")
    assert (
        f"SOURCE S2 [filename=research-notes.pdf doc_id={document_id} chunk=3]"
        in context
    )
    assert (
        f"SOURCE S3 [filename=research-notes.pdf doc_id={document_id} chunk=5]"
        in context
    )
    assert "Notebook content from the source." in context


def test_empty_context_block_tells_agent_not_to_guess() -> None:
    context = build_context_block([])

    assert "No relevant notebook sources were found" in context
    assert "do not provide enough information" in context
