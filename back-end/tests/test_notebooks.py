import os
from collections.abc import Generator
from uuid import UUID
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.dependencies import get_session
from app.main import app
from app.notebooks.models import NotebookDocument, NotebookDocumentChunk
from app.users.models import User

os.environ.setdefault("DATABASE_URL", "sqlite://")


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        jwt_secret_key="test-secret-with-at-least-32-bytes",
        jwt_algorithm="HS256",
    )


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(settings: Settings, session: Session) -> Generator[TestClient, None, None]:
    def override_get_settings() -> Settings:
        return settings

    def override_get_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def make_user(email: str) -> User:
    return User(id=uuid4(), email=email, hashed_password="hashed-password")


def auth_headers(user: User, settings: Settings) -> dict[str, str]:
    token = create_access_token(user, settings)
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_notebooks(
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("user@example.com")
    session.add(user)
    session.commit()

    response = client.post(
        "/api/v1/notebooks/",
        json={
            "name": " Research Notes ",
            "description": " Papers and snippets ",
            "tags": ["AI", "ai", " RAG "],
        },
        headers=auth_headers(user, settings),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Research Notes"
    assert body["description"] == "Papers and snippets"
    assert body["tags"] == ["AI", "RAG"]
    assert "document_count" not in body
    assert "query_count" not in body

    list_response = client.get("/api/v1/notebooks/", headers=auth_headers(user, settings))
    assert list_response.status_code == 200
    assert [notebook["id"] for notebook in list_response.json()] == [body["id"]]
    assert "document_count" not in list_response.json()[0]
    assert "query_count" not in list_response.json()[0]

    populate_response = client.get(
        f"/api/v1/notebooks/{body['id']}/populate",
        headers=auth_headers(user, settings),
    )
    assert populate_response.status_code == 200
    assert populate_response.json()["document_count"] == 0
    assert populate_response.json()["query_count"] == 0


def test_update_and_delete_notebook(
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("user@example.com")
    session.add(user)
    session.commit()
    headers = auth_headers(user, settings)

    created = client.post(
        "/api/v1/notebooks/",
        json={"name": "Draft", "description": "", "tags": []},
        headers=headers,
    ).json()

    update_response = client.patch(
        f"/api/v1/notebooks/{created['id']}",
        json={"name": "Final", "tags": ["Product"]},
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Final"
    assert update_response.json()["tags"] == ["Product"]

    delete_response = client.delete(f"/api/v1/notebooks/{created['id']}", headers=headers)
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/v1/notebooks/{created['id']}", headers=headers)
    assert get_response.status_code == 404


def test_notebook_access_is_scoped_to_owner(
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    owner = make_user("owner@example.com")
    other_user = make_user("other@example.com")
    session.add(owner)
    session.add(other_user)
    session.commit()

    owner_headers = auth_headers(owner, settings)
    other_headers = auth_headers(other_user, settings)

    created = client.post(
        "/api/v1/notebooks/",
        json={"name": "Private", "description": "", "tags": []},
        headers=owner_headers,
    ).json()

    assert client.get(f"/api/v1/notebooks/{created['id']}", headers=other_headers).status_code == 404
    assert client.patch(
        f"/api/v1/notebooks/{created['id']}",
        json={"name": "Stolen"},
        headers=other_headers,
    ).status_code == 404
    assert client.delete(f"/api/v1/notebooks/{created['id']}", headers=other_headers).status_code == 404


def test_list_notebook_documents_is_scoped_to_owner(
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    owner = make_user("owner@example.com")
    other_user = make_user("other@example.com")
    session.add(owner)
    session.add(other_user)
    session.commit()

    owner_notebook = client.post(
        "/api/v1/notebooks/",
        json={"name": "Private", "description": "", "tags": []},
        headers=auth_headers(owner, settings),
    ).json()

    other_notebook = client.post(
        "/api/v1/notebooks/",
        json={"name": "Other", "description": "", "tags": []},
        headers=auth_headers(other_user, settings),
    ).json()

    owner_doc = NotebookDocument(
        notebook_id=UUID(owner_notebook["id"]),
        user_id=owner.id,
        s3_bucket="test-bucket",
        s3_key=f"users/{owner.id}/doc.pdf",
        filename="doc.pdf",
        content_type="application/pdf",
        size=123,
        status="indexed",
    )
    other_doc = NotebookDocument(
        notebook_id=UUID(other_notebook["id"]),
        user_id=other_user.id,
        s3_bucket="test-bucket",
        s3_key=f"users/{other_user.id}/other.pdf",
        filename="other.pdf",
        content_type="application/pdf",
        size=456,
        status="indexed",
    )
    session.add(owner_doc)
    session.add(other_doc)
    session.commit()

    owner_response = client.get(
        f"/api/v1/notebooks/{owner_notebook['id']}/documents",
        headers=auth_headers(owner, settings),
    )
    assert owner_response.status_code == 200
    assert [document["filename"] for document in owner_response.json()] == ["doc.pdf"]
    assert owner_response.json()[0]["status"] == "indexed"

    other_response = client.get(
        f"/api/v1/notebooks/{owner_notebook['id']}/documents",
        headers=auth_headers(other_user, settings),
    )
    assert other_response.status_code == 404


def test_notebook_document_events_requires_auth(
    client: TestClient,
) -> None:
    response = client.get(f"/api/v1/notebooks/{uuid4()}/documents/events")
    assert response.status_code == 401


def test_notebook_document_events_is_scoped_to_owner(
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    owner = make_user("owner-doc-events@example.com")
    other_user = make_user("other-doc-events@example.com")
    session.add(owner)
    session.add(other_user)
    session.commit()

    notebook = client.post(
        "/api/v1/notebooks/",
        json={"name": "Private", "description": "", "tags": []},
        headers=auth_headers(owner, settings),
    ).json()

    response = client.get(
        f"/api/v1/notebooks/{notebook['id']}/documents/events",
        headers=auth_headers(other_user, settings),
    )
    assert response.status_code == 404


def test_delete_notebook_document_removes_source_and_chunks(
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("user@example.com")
    session.add(user)
    session.commit()
    headers = auth_headers(user, settings)

    notebook = client.post(
        "/api/v1/notebooks/",
        json={"name": "Private", "description": "", "tags": []},
        headers=headers,
    ).json()

    document = NotebookDocument(
        notebook_id=UUID(notebook["id"]),
        user_id=user.id,
        s3_bucket="test-bucket",
        s3_key=f"users/{user.id}/doc.pdf",
        filename="doc.pdf",
        content_type="application/pdf",
        size=123,
        status="indexed",
    )
    session.add(document)
    session.commit()
    session.refresh(document)

    chunk = NotebookDocumentChunk(
        document_id=document.id,
        notebook_id=document.notebook_id,
        user_id=user.id,
        chunk_index=0,
        content="Notebook source text",
        chunk_metadata={"source": document.s3_key},
        embedding=[0.0] * 1536,
    )
    session.add(chunk)
    session.commit()

    response = client.delete(
        f"/api/v1/notebooks/{notebook['id']}/documents/{document.id}",
        headers=headers,
    )

    assert response.status_code == 204
    assert session.get(NotebookDocument, document.id) is None
    chunks = session.exec(select(NotebookDocumentChunk).where(NotebookDocumentChunk.document_id == document.id)).all()
    assert chunks == []


def test_delete_notebook_document_is_scoped_to_owner(
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    owner = make_user("owner@example.com")
    other_user = make_user("other@example.com")
    session.add(owner)
    session.add(other_user)
    session.commit()

    notebook = client.post(
        "/api/v1/notebooks/",
        json={"name": "Private", "description": "", "tags": []},
        headers=auth_headers(owner, settings),
    ).json()

    document = NotebookDocument(
        notebook_id=UUID(notebook["id"]),
        user_id=owner.id,
        s3_bucket="test-bucket",
        s3_key=f"users/{owner.id}/doc.pdf",
        filename="doc.pdf",
        content_type="application/pdf",
        size=123,
        status="indexed",
    )
    session.add(document)
    session.commit()
    session.refresh(document)

    response = client.delete(
        f"/api/v1/notebooks/{notebook['id']}/documents/{document.id}",
        headers=auth_headers(other_user, settings),
    )

    assert response.status_code == 404
    assert session.get(NotebookDocument, document.id) is not None


def test_create_notebook_requires_name(
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("user@example.com")
    session.add(user)
    session.commit()

    response = client.post(
        "/api/v1/notebooks/",
        json={"name": "", "description": "", "tags": []},
        headers=auth_headers(user, settings),
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Report generation flow
# ---------------------------------------------------------------------------

from pydantic_ai.exceptions import ModelHTTPError

from app.notebooks.schemas import BriefingDocReport


def _create_notebook(client: TestClient, headers: dict[str, str]) -> str:
    return client.post(
        "/api/v1/notebooks/",
        json={"name": "Reports", "description": "", "tags": []},
        headers=headers,
    ).json()["id"]


def _add_indexed_chunk(session: Session, notebook_id: UUID, user_id: UUID) -> None:
    doc = NotebookDocument(
        id=uuid4(),
        notebook_id=notebook_id,
        user_id=user_id,
        s3_bucket="bucket",
        s3_key=f"key-{uuid4()}",
        filename="source.txt",
        status="indexed",
    )
    session.add(doc)
    session.commit()
    session.add(
        NotebookDocumentChunk(
            id=uuid4(),
            document_id=doc.id,
            notebook_id=notebook_id,
            user_id=user_id,
            chunk_index=0,
            content="Indexed source content about the project.",
            embedding=[0.0] * 1536,
        )
    )
    session.commit()


def test_generate_report_requires_configured_provider(
    client: TestClient,
    settings: Settings,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user("rep1@example.com")
    session.add(user)
    session.commit()
    headers = auth_headers(user, settings)
    notebook_id = _create_notebook(client, headers)

    monkeypatch.setattr("app.notebooks.router.chat_provider_is_configured", lambda: False)

    response = client.post(
        f"/api/v1/notebooks/{notebook_id}/reports",
        json={"report_type": "briefing"},
        headers=headers,
    )
    assert response.status_code == 503


def test_generate_report_requires_indexed_documents(
    client: TestClient,
    settings: Settings,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user("rep2@example.com")
    session.add(user)
    session.commit()
    headers = auth_headers(user, settings)
    notebook_id = _create_notebook(client, headers)

    monkeypatch.setattr("app.notebooks.router.chat_provider_is_configured", lambda: True)

    response = client.post(
        f"/api/v1/notebooks/{notebook_id}/reports",
        json={"report_type": "briefing"},
        headers=headers,
    )
    assert response.status_code == 422
    assert "indexed" in response.json()["detail"].lower()


def test_generate_report_persists_and_lists(
    client: TestClient,
    settings: Settings,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user("rep3@example.com")
    session.add(user)
    session.commit()
    headers = auth_headers(user, settings)
    notebook_id = _create_notebook(client, headers)
    _add_indexed_chunk(session, UUID(notebook_id), user.id)

    monkeypatch.setattr("app.notebooks.router.chat_provider_is_configured", lambda: True)

    captured: dict[str, object] = {}

    async def fake_briefing(context: str, instructions: str | None = None) -> BriefingDocReport:
        captured["context"] = context
        return BriefingDocReport(
            executive_summary="Summary.",
            key_takeaways=["one", "two"],
            strategic_implications=["do x"],
        )

    monkeypatch.setattr("app.notebooks.router.generate_briefing_doc", fake_briefing)

    response = client.post(
        f"/api/v1/notebooks/{notebook_id}/reports",
        json={"report_type": "briefing"},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["report_type"] == "briefing"
    assert body["content"]["key_takeaways"] == ["one", "two"]
    # The notebook's indexed source text was fed to the generator.
    assert "Indexed source content" in str(captured["context"])

    listed = client.get(
        f"/api/v1/notebooks/{notebook_id}/reports",
        headers=headers,
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == body["id"]


def test_generate_report_custom_requires_instructions(
    client: TestClient,
    settings: Settings,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user("rep4@example.com")
    session.add(user)
    session.commit()
    headers = auth_headers(user, settings)
    notebook_id = _create_notebook(client, headers)
    _add_indexed_chunk(session, UUID(notebook_id), user.id)

    monkeypatch.setattr("app.notebooks.router.chat_provider_is_configured", lambda: True)

    response = client.post(
        f"/api/v1/notebooks/{notebook_id}/reports",
        json={"report_type": "custom"},
        headers=headers,
    )
    assert response.status_code == 422
    assert "additional_instructions" in response.json()["detail"]


def test_generate_report_maps_provider_rate_limit(
    client: TestClient,
    settings: Settings,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user("rep5@example.com")
    session.add(user)
    session.commit()
    headers = auth_headers(user, settings)
    notebook_id = _create_notebook(client, headers)
    _add_indexed_chunk(session, UUID(notebook_id), user.id)

    monkeypatch.setattr("app.notebooks.router.chat_provider_is_configured", lambda: True)

    async def rate_limited(context: str, instructions: str | None = None) -> BriefingDocReport:
        raise ModelHTTPError(status_code=429, model_name="gemini-2.5-flash", body={})

    monkeypatch.setattr("app.notebooks.router.generate_briefing_doc", rate_limited)

    response = client.post(
        f"/api/v1/notebooks/{notebook_id}/reports",
        json={"report_type": "briefing"},
        headers=headers,
    )
    assert response.status_code == 429
