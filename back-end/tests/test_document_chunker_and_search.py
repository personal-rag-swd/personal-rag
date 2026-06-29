import io

import pytest
from docx import Document as DocxDocument

import app.notebooks.rag.document_chunker as chunking_module
from app.core.config import Settings
from app.notebooks.rag.document_chunker import (
    ChunkingRequest,
    chunk_document,
    chunk_docx,
    chunk_pdf,
)
from app.notebooks.rag.query_rewrite_agent import (
    rewrite_query_text,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="mongodb://localhost:27017/test",
        jwt_secret_key="test-secret-key",
        jwt_algorithm="HS256",
        access_token_expire_minutes=30,
        refresh_token_expire_days=30,
        otp_expire_minutes=10,
        otp_max_attempts=5,
        log_level="DEBUG",
        resend_api_key="",
        cookie_secure=False,
        notebook_chunk_size=100,
        notebook_chunk_overlap=20,
        embedding_dimension=1536,
        embedding_model="text-embedding-3-small",
    )


def test_docx_chunking_includes_table_text() -> None:
    doc = DocxDocument()
    doc.add_paragraph("Intro paragraph")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Header A"
    table.rows[0].cells[1].text = "Header B"

    buffer = io.BytesIO()
    doc.save(buffer)

    chunks = chunk_docx(
        ChunkingRequest(
            content=buffer.getvalue(),
            filename="sample.docx",
            source="docx-source",
            document_id="doc-1",
        ),
        chunk_size=1000,
        chunk_overlap=200,
    )

    combined = "\n".join(chunk.page_content for chunk in chunks)
    assert "Intro paragraph" in combined
    assert "Header A | Header B" in combined


def test_pdf_chunking_extracts_simple_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chunking_module.pymupdf, "open", lambda **kwargs: "fake_doc")
    monkeypatch.setattr(
        chunking_module.pymupdf4llm,
        "to_markdown",
        lambda doc, page_chunks: [{"text": "PDF text"}] if page_chunks else "PDF text",
    )

    chunks = chunk_pdf(
        ChunkingRequest(
            content=b"%PDF-1.7",
            filename="sample.pdf",
            source="pdf-source",
            document_id="doc-2",
        ),
        chunk_size=1000,
        chunk_overlap=200,
    )

    assert any("PDF text" in chunk.page_content for chunk in chunks)


def test_chunk_document_uses_settings_for_docx(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, int] = {}

    def fake_chunk_docx(
        request: ChunkingRequest,
        *,
        settings: Settings | None = None,
        chunk_size: int,
        chunk_overlap: int,
    ):
        captured["chunk_size"] = chunk_size
        captured["chunk_overlap"] = chunk_overlap
        return []

    monkeypatch.setitem(chunking_module.ENGINE_BY_EXTENSION, ".docx", fake_chunk_docx)

    request = ChunkingRequest(
        content=b"docx-bytes",
        filename="sample.docx",
        source="docx-source",
        document_id="doc-3",
    )
    settings = Settings(
        database_url="mongodb://localhost:27017/test",
        jwt_secret_key="test-secret-key",
        jwt_algorithm="HS256",
        access_token_expire_minutes=30,
        refresh_token_expire_days=30,
        notebook_chunk_size=2048,
        notebook_chunk_overlap=128,
        embedding_dimension=1536,
        embedding_model="text-embedding-3-small",
    )

    assert chunk_document(request, settings) == []
    assert captured == {"chunk_size": 2048, "chunk_overlap": 128}


def test_chunk_document_rejects_unsupported_extension() -> None:
    request = ChunkingRequest(
        content=b"plain text",
        filename="sample.csv",
        source="csv-source",
        document_id="doc-4",
    )

    with pytest.raises(ValueError, match=r"Unsupported file type: \.csv"):
        chunk_document(request)


@pytest.mark.anyio
async def test_rewrite_query_text_disabled(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    monkeypatch.setattr(
        "app.notebooks.rag.query_rewrite_agent.chat_provider_is_configured",
        lambda: True,
    )
    settings.enable_query_rewrite = False

    res = await rewrite_query_text("can you find apples?", settings)
    assert res == "can you find apples?"


@pytest.mark.anyio
async def test_rewrite_query_text_success(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    from pydantic_ai.models.test import TestModel

    monkeypatch.setattr(
        "app.notebooks.rag.query_rewrite_agent.chat_provider_is_configured",
        lambda: True,
    )

    monkeypatch.setattr(
        "app.notebooks.rag.query_rewrite_agent.resolve_chat_provider",
        lambda: TestModel(custom_output_text="apples"),
    )

    settings.enable_query_rewrite = True
    res = await rewrite_query_text("can you find apples?", settings)
    assert res == "apples"


@pytest.mark.anyio
async def test_rewrite_query_text_failure_fallback(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    monkeypatch.setattr(
        "app.notebooks.rag.query_rewrite_agent.chat_provider_is_configured",
        lambda: True,
    )

    def failing_resolve():
        raise RuntimeError("LLM error")

    monkeypatch.setattr(
        "app.notebooks.rag.query_rewrite_agent.resolve_chat_provider", failing_resolve
    )

    settings.enable_query_rewrite = True
    res = await rewrite_query_text("can you find apples?", settings)
    assert res == "can you find apples?"
