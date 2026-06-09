from uuid import uuid4

from app.notebooks.prompt.context import build_context_block
from app.notebooks.prompt.system import CHAT_SYSTEM_INSTRUCTIONS
from app.notebooks.tools.search import RetrievedChunk


def test_notebook_core_instructions_require_source_grounding() -> None:
    assert "Answer only from the retrieved source text" in CHAT_SYSTEM_INSTRUCTIONS
    assert (
        "If the retrieved sources do not contain enough evidence"
        in CHAT_SYSTEM_INSTRUCTIONS
    )
    assert "[filename, chunk N]" in CHAT_SYSTEM_INSTRUCTIONS
    assert "Do not fabricate filenames" in CHAT_SYSTEM_INSTRUCTIONS


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
            )
        ]
    )

    assert "Cite claims with the matching source label: [filename, chunk N]." in context
    assert (
        f"SOURCE [filename=research-notes.pdf doc_id={document_id} chunk=3]" in context
    )
    assert "Notebook content from the source." in context


def test_empty_context_block_tells_agent_not_to_guess() -> None:
    context = build_context_block([])

    assert "No relevant notebook sources were found" in context
    assert "do not provide enough information" in context
