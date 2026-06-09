import io
import os
from uuid import uuid4

import pytest
from docx import Document as DocxDocument
from sqlmodel import Session

import app.notebooks.tools.chunking as chunking_module
from app.core.config import Settings
from app.notebooks.models import Notebook, NotebookDocument, NotebookDocumentChunk
from app.notebooks.tools.chunking import (
    ChunkingRequest,
    chunk_document,
    chunk_docx,
    chunk_pdf,
)
from app.notebooks.tools.search import search_notebook_chunks
from app.users.models import User


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url=os.environ["DATABASE_URL"],
        jwt_secret_key="test-secret-with-at-least-32-bytes",
        jwt_algorithm="HS256",
        embedding_provider="openai_compatible",
        embedding_api_key="key",
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
    class FakePage:
        def extract_text(self) -> str:
            return "PDF text"

    class FakePdf:
        def __init__(self) -> None:
            self.pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "app.notebooks.tools.chunking.pdfplumber.open", lambda _f: FakePdf()
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
        request: ChunkingRequest, *, chunk_size: int, chunk_overlap: int
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
        database_url=os.environ["DATABASE_URL"],
        jwt_secret_key="test-secret-with-at-least-32-bytes",
        jwt_algorithm="HS256",
        notebook_chunk_size=2048,
        notebook_chunk_overlap=128,
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


def test_search_postgres_orders_chunks_by_vector_similarity(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, session: Session
) -> None:
    user_id = uuid4()
    query_vector = [1.0] + [0.0] * 1535
    monkeypatch.setattr(
        "app.notebooks.tools.search.embed_texts",
        lambda texts, _settings: [query_vector],
    )

    notebook = Notebook(user_id=user_id, name="Notebook", description="", tags=[])
    current_user = User(
        id=user_id, email="user@example.com", hashed_password="hashed-password"
    )
    session.add(current_user)
    session.commit()
    session.add(notebook)
    session.commit()

    matching_document = NotebookDocument(
        notebook_id=notebook.id,
        user_id=current_user.id,
        s3_bucket="bucket",
        s3_key=f"users/{current_user.id}/matching.txt",
        filename="matching.txt",
        status="indexed",
    )
    distant_document = NotebookDocument(
        notebook_id=notebook.id,
        user_id=current_user.id,
        s3_bucket="bucket",
        s3_key=f"users/{current_user.id}/distant.txt",
        filename="distant.txt",
        status="indexed",
    )
    session.add(matching_document)
    session.add(distant_document)
    session.commit()

    session.add(
        NotebookDocumentChunk(
            document_id=matching_document.id,
            chunk_index=0,
            content="matching content",
            embedding=query_vector,
        )
    )
    session.add(
        NotebookDocumentChunk(
            document_id=distant_document.id,
            chunk_index=0,
            content="distant content",
            embedding=[0.0, 1.0] + [0.0] * 1534,
        )
    )
    session.commit()

    results = search_notebook_chunks(
        session,
        notebook=notebook,
        current_user=current_user,
        query="q",
        settings=settings,
        top_k=4,
    )

    assert [result.filename for result in results] == [
        "matching.txt",
        "distant.txt",
    ]
    assert results[0].content == "matching content"
