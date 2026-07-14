"""Reports must ground themselves in embedded PDF images, not just their
stored text description — Phase 4 attaches a capped set of image chunks'
actual bytes to the report generation prompt.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai import capture_run_messages
from pydantic_ai.messages import BinaryContent, UserPromptPart
from pydantic_ai.models.test import TestModel

from app.core.config import Settings
from app.notebooks.agent.report_agents import generate_briefing_doc
from app.notebooks.models import NotebookDocument, NotebookDocumentChunk
from app.notebooks.service.reports import ReportContext, build_report_context
from tests.conftest import create_notebook, create_user

pytestmark = pytest.mark.anyio


async def _add_document_with_chunks(
    notebook_id, user_id, *, image_chunk_count: int
) -> None:
    document = NotebookDocument(
        notebook_id=notebook_id,
        user_id=user_id,
        filename="figures.pdf",
        status="indexed",
        s3_bucket="test-bucket",
        s3_key="notebooks/figures.pdf",
    )
    await document.insert()

    await NotebookDocumentChunk(
        document_id=document.id,
        notebook_id=notebook_id,
        user_id=user_id,
        chunk_index=0,
        content="Some narrative text.",
        chunk_metadata={"chunk_type": "text"},
    ).insert()

    for i in range(image_chunk_count):
        await NotebookDocumentChunk(
            document_id=document.id,
            notebook_id=notebook_id,
            user_id=user_id,
            chunk_index=i + 1,
            content=f"A chart on page {i + 1}.",
            chunk_metadata={
                "chunk_type": "image",
                "s3_key": f"notebooks/images/img_{i}.png",
                "media_type": "image/png",
                "page_number": i + 1,
            },
        ).insert()


async def test_build_report_context_attaches_image_bytes(settings: Settings) -> None:
    user = await create_user(role="user")
    notebook = await create_notebook(user)
    await _add_document_with_chunks(notebook.id, user.id, image_chunk_count=2)

    fake_bytes = AsyncMock(return_value=b"fake-png-bytes")
    with patch("app.notebooks.rag.image_context.get_object_bytes", fake_bytes):
        context = await build_report_context(notebook, user, settings)

    assert "A chart on page 1." in context.text
    assert "A chart on page 2." in context.text
    # One [label, BinaryContent] pair per image chunk.
    assert len(context.image_parts) == 4
    labels = [part for part in context.image_parts if isinstance(part, str)]
    images = [part for part in context.image_parts if isinstance(part, BinaryContent)]
    assert len(images) == 2
    assert all("Image for SOURCE" in label for label in labels)
    assert fake_bytes.await_count == 2


async def test_build_report_context_caps_image_parts(settings: Settings) -> None:
    settings = settings.model_copy(update={"notebook_report_max_images": 1})
    user = await create_user(role="user")
    notebook = await create_notebook(user)
    await _add_document_with_chunks(notebook.id, user.id, image_chunk_count=3)

    fake_bytes = AsyncMock(return_value=b"fake-png-bytes")
    with patch("app.notebooks.rag.image_context.get_object_bytes", fake_bytes):
        context = await build_report_context(notebook, user, settings)

    # All 3 image chunks still appear as text SOURCE blocks...
    assert context.text.count("chunk_type=image") == 3
    # ...but only the capped count gets actual bytes fetched/attached.
    assert fake_bytes.await_count == 1
    images = [part for part in context.image_parts if isinstance(part, BinaryContent)]
    assert len(images) == 1


async def test_build_report_context_skips_failed_image_downloads(
    settings: Settings,
) -> None:
    user = await create_user(role="user")
    notebook = await create_notebook(user)
    await _add_document_with_chunks(notebook.id, user.id, image_chunk_count=1)

    failing_fetch = AsyncMock(side_effect=RuntimeError("boom"))
    with patch("app.notebooks.rag.image_context.get_object_bytes", failing_fetch):
        context = await build_report_context(notebook, user, settings)

    assert context.image_parts == []


async def test_build_report_context_no_images_for_text_only_notebook(
    settings: Settings,
) -> None:
    user = await create_user(role="user")
    notebook = await create_notebook(user)
    document = NotebookDocument(
        notebook_id=notebook.id,
        user_id=user.id,
        filename="notes.txt",
        status="indexed",
        content="Plain text notes.",
    )
    await document.insert()
    await NotebookDocumentChunk(
        document_id=document.id,
        notebook_id=notebook.id,
        user_id=user.id,
        chunk_index=0,
        content="Plain text notes.",
        chunk_metadata={"chunk_type": "text"},
    ).insert()

    context = await build_report_context(notebook, user, settings)

    assert context.image_parts == []


async def test_build_report_context_empty_notebook(settings: Settings) -> None:
    user = await create_user(role="user")
    notebook = await create_notebook(user)

    context = await build_report_context(notebook, user, settings)

    assert context.text == ""
    assert context.image_parts == []


async def test_generate_briefing_doc_sends_image_parts_to_the_agent() -> None:
    """A report's user prompt must include the image bytes, not just text,
    so the agent can attend to what a chart actually shows.
    """
    context = ReportContext(
        text="SOURCE [filename=figures.pdf doc_id=x chunk=1 chunk_type=image]\nA chart.",
        image_parts=[
            "Image for SOURCE [filename=figures.pdf doc_id=x chunk=1 chunk_type=image]:",
            BinaryContent(data=b"fake-png-bytes", media_type="image/png"),
        ],
    )

    with (
        patch(
            "app.notebooks.agent.report_agents.resolve_chat_provider",
            return_value=TestModel(),
        ),
        capture_run_messages() as messages,
    ):
        await generate_briefing_doc(context)

    prompt_part = messages[0].parts[0]
    assert isinstance(prompt_part, UserPromptPart)
    user_prompt = prompt_part.content
    assert isinstance(user_prompt, list)
    assert any(
        isinstance(part, str) and "SOURCE MATERIAL" in part for part in user_prompt
    )
    assert any(isinstance(part, BinaryContent) for part in user_prompt)


async def test_generate_briefing_doc_sends_plain_text_without_images() -> None:
    context = ReportContext(text="Just some plain source text.")

    with (
        patch(
            "app.notebooks.agent.report_agents.resolve_chat_provider",
            return_value=TestModel(),
        ),
        capture_run_messages() as messages,
    ):
        await generate_briefing_doc(context)

    prompt_part = messages[0].parts[0]
    assert isinstance(prompt_part, UserPromptPart)
    user_prompt = prompt_part.content
    assert isinstance(user_prompt, str)
    assert "Just some plain source text." in user_prompt
