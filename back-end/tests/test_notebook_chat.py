import os
from collections.abc import Generator
from typing import Any
from uuid import UUID
from uuid import uuid4

os.environ["CHAT_API_KEY"] = "test-key"

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import ModelMessagesTypeAdapter
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.ui.ag_ui import AGUIAdapter
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select
from starlette.responses import Response

from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.dependencies import get_session
from app.main import app
from app.notebooks.models import Notebook, NotebookMessage
from app.users.models import User


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    s = Settings(
        database_url="sqlite://",
        jwt_secret_key="test-secret-with-at-least-32-bytes",
        jwt_algorithm="HS256",
        chat_api_key="test-key",
    )
    from app.core import config
    from app.notebooks.agent.providers import OpenRouterChatProvider, OpenAICompatibleChatProvider, GeminiChatProvider
    OpenRouterChatProvider.build_model.cache_clear()
    OpenAICompatibleChatProvider.build_model.cache_clear()
    GeminiChatProvider.build_model.cache_clear()
    config.get_settings.cache_clear()
    
    monkeypatch.setattr(config, "get_settings", lambda: s)
    return s


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


class FakeRunResult:
    def __init__(self, messages: list[ModelMessage]) -> None:
        self._messages = messages

    def all_messages(self) -> list[ModelMessage]:
        return self._messages

    def new_messages(self) -> list[ModelMessage]:
        return self._messages


def test_notebook_chat_endpoint_streams_response(
    client: TestClient,
    settings: Settings,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user("user@example.com")
    session.add(user)
    session.commit()

    headers = auth_headers(user, settings)
    created = client.post(
        "/api/v1/notebooks/",
        json={"name": "Chat", "description": "", "tags": []},
        headers=headers,
    ).json()

    async def fake_dispatch_request(request: object, agent: object, **kwargs: Any) -> Response:
        return Response(content="ok", media_type="text/plain")

    monkeypatch.setattr(AGUIAdapter, "dispatch_request", fake_dispatch_request)

    response = client.post(
        f"/api/v1/notebooks/{created['id']}/chat",
        json={"messages": []},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.text == "ok"


def test_notebook_chat_endpoint_persists_message_history(
    client: TestClient,
    settings: Settings,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user("user@example.com")
    session.add(user)
    session.commit()

    headers = auth_headers(user, settings)
    created = client.post(
        "/api/v1/notebooks/",
        json={"name": "Chat", "description": "", "tags": []},
        headers=headers,
    ).json()
    messages = [
        ModelRequest(parts=[UserPromptPart(content="What is in this notebook?")]),
        ModelResponse(parts=[TextPart(content="No documents have been added yet.")]),
    ]
    captured: dict[str, Any] = {}

    async def fake_dispatch_request(request: object, agent: object, **kwargs: Any) -> Response:
        captured["message_history"] = kwargs["message_history"]
        captured["conversation_id"] = kwargs["conversation_id"]
        await kwargs["on_complete"](FakeRunResult(messages))
        return Response(content="ok", media_type="text/plain")

    monkeypatch.setattr(AGUIAdapter, "dispatch_request", fake_dispatch_request)

    response = client.post(
        f"/api/v1/notebooks/{created['id']}/chat",
        json={"messages": []},
        headers=headers,
    )

    notebook_id = UUID(created["id"])
    notebook = session.get(Notebook, notebook_id)
    assert response.status_code == 200
    assert captured["message_history"] == []
    assert captured["conversation_id"] == created["id"]
    assert notebook is not None
    stored_messages = list(
        session.exec(
            select(NotebookMessage.message)
            .where(NotebookMessage.notebook_id == notebook_id)
            .order_by(NotebookMessage.seq.asc())
        ).all()
    )
    assert ModelMessagesTypeAdapter.validate_python(stored_messages) == messages


def test_notebook_chat_endpoint_loads_existing_message_history(
    client: TestClient,
    settings: Settings,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user("user@example.com")
    session.add(user)
    session.commit()

    headers = auth_headers(user, settings)
    created = client.post(
        "/api/v1/notebooks/",
        json={"name": "Chat", "description": "", "tags": []},
        headers=headers,
    ).json()
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Previous question")]),
        ModelResponse(parts=[TextPart(content="Previous answer")]),
    ]
    notebook = session.get(Notebook, UUID(created["id"]))
    assert notebook is not None
    json_messages = ModelMessagesTypeAdapter.dump_python(messages, mode="json")
    session.add_all(
        [
            NotebookMessage(notebook_id=notebook.id, seq=idx, message=message)
            for idx, message in enumerate(json_messages, start=1)
        ]
    )
    session.commit()
    captured: dict[str, Any] = {}

    async def fake_dispatch_request(request: object, agent: object, **kwargs: Any) -> Response:
        captured["message_history"] = kwargs["message_history"]
        return Response(content="ok", media_type="text/plain")

    monkeypatch.setattr(AGUIAdapter, "dispatch_request", fake_dispatch_request)

    response = client.post(
        f"/api/v1/notebooks/{created['id']}/chat",
        json={"messages": []},
        headers=headers,
    )

    assert response.status_code == 200
    assert captured["message_history"] == messages


def test_notebook_chat_endpoint_is_scoped_to_owner(
    client: TestClient,
    settings: Settings,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
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

    called = {"value": False}

    async def fake_dispatch_request(request: object, agent: object, **kwargs: Any) -> Response:
        called["value"] = True
        return Response(content="ok", media_type="text/plain")

    monkeypatch.setattr(AGUIAdapter, "dispatch_request", fake_dispatch_request)

    response = client.post(
        f"/api/v1/notebooks/{created['id']}/chat",
        json={"messages": []},
        headers=other_headers,
    )

    assert response.status_code == 404
    assert called["value"] is False


from app.notebooks.memory.history import parse_chunks_from_context_block
from app.notebooks.models import NotebookDocument, NotebookDocumentChunk


def test_parse_chunks_from_context_block() -> None:
    block = (
        "SOURCE [filename=UDL.pdf doc_id=5f3e9c42-5ba3-4c91-9e7f-1d8975bb42f1 chunk=0]\n"
        "1.1 Supervised learning\n"
        "Supervised learning is nice.\n\n"
        "SOURCE [filename=UDL2.pdf doc_id=6f3e9c42-5ba3-4c91-9e7f-1d8975bb42f2 chunk=1]\n"
        "Some other content."
    )
    chunks = parse_chunks_from_context_block(block)
    assert len(chunks) == 2
    assert chunks[0]["filename"] == "UDL.pdf"
    assert chunks[0]["document_id"] == "5f3e9c42-5ba3-4c91-9e7f-1d8975bb42f1"
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["content"] == "1.1 Supervised learning\nSupervised learning is nice."
    
    assert chunks[1]["filename"] == "UDL2.pdf"
    assert chunks[1]["document_id"] == "6f3e9c42-5ba3-4c91-9e7f-1d8975bb42f2"
    assert chunks[1]["chunk_index"] == 1
    assert chunks[1]["content"] == "Some other content."


def test_chat_history_emits_ordered_references(
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("refs@example.com")
    session.add(user)
    session.commit()
    headers = auth_headers(user, settings)

    created = client.post(
        "/api/v1/notebooks/",
        json={"name": "Refs", "description": "", "tags": []},
        headers=headers,
    ).json()

    context_block = (
        "SOURCE [filename=alpha.pdf doc_id=5f3e9c42-5ba3-4c91-9e7f-1d8975bb42f1 chunk=0]\n"
        "Alpha source text.\n\n"
        "SOURCE [filename=beta.pdf doc_id=6f3e9c42-5ba3-4c91-9e7f-1d8975bb42f2 chunk=1]\n"
        "Beta source text."
    )
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Question?")]),
        ModelRequest(parts=[ToolReturnPart(tool_name="search_notebook_context", content=context_block)]),
        ModelResponse(
            parts=[
                TextPart(
                    content=(
                        "Answer one [alpha.pdf, chunk 0]. "
                        "Answer two [beta.pdf, chunk 1]. "
                        "Repeat [alpha.pdf, chunk 0]."
                    )
                )
            ]
        ),
    ]
    notebook = session.get(Notebook, UUID(created["id"]))
    assert notebook is not None
    json_messages = ModelMessagesTypeAdapter.dump_python(messages, mode="json")
    session.add_all(
        [
            NotebookMessage(notebook_id=notebook.id, seq=idx, message=message)
            for idx, message in enumerate(json_messages, start=1)
        ]
    )
    session.commit()

    response = client.get(
        f"/api/v1/notebooks/{created['id']}/chat/history",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assistant = next(message for message in payload if message["role"] == "assistant")

    assert len(assistant["sources"]) == 2
    assert [ref["citation_number"] for ref in assistant["references"]] == [1, 2]
    assert assistant["references"][0]["ref_id"] == "1:1"
    assert assistant["references"][0]["filename"] == "alpha.pdf"
    assert assistant["references"][0]["chunk_index"] == 0
    assert assistant["references"][1]["ref_id"] == "1:2"
    assert assistant["references"][1]["filename"] == "beta.pdf"
    assert assistant["references"][1]["chunk_index"] == 1


def test_chat_history_reference_ids_reset_per_assistant_message(
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("refs2@example.com")
    session.add(user)
    session.commit()
    headers = auth_headers(user, settings)

    created = client.post(
        "/api/v1/notebooks/",
        json={"name": "Refs2", "description": "", "tags": []},
        headers=headers,
    ).json()

    block_one = (
        "SOURCE [filename=one.pdf doc_id=5f3e9c42-5ba3-4c91-9e7f-1d8975bb42f1 chunk=0]\n"
        "One."
    )
    block_two = (
        "SOURCE [filename=two.pdf doc_id=6f3e9c42-5ba3-4c91-9e7f-1d8975bb42f2 chunk=1]\n"
        "Two."
    )
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Q1")]),
        ModelRequest(parts=[ToolReturnPart(tool_name="search_notebook_context", content=block_one)]),
        ModelResponse(parts=[TextPart(content="A1 [one.pdf, chunk 0].")]),
        ModelRequest(parts=[UserPromptPart(content="Q2")]),
        ModelRequest(parts=[ToolReturnPart(tool_name="search_notebook_context", content=block_two)]),
        ModelResponse(parts=[TextPart(content="A2 [two.pdf, chunk 1].")]),
    ]
    notebook = session.get(Notebook, UUID(created["id"]))
    assert notebook is not None
    json_messages = ModelMessagesTypeAdapter.dump_python(messages, mode="json")
    session.add_all(
        [
            NotebookMessage(notebook_id=notebook.id, seq=idx, message=message)
            for idx, message in enumerate(json_messages, start=1)
        ]
    )
    session.commit()

    response = client.get(
        f"/api/v1/notebooks/{created['id']}/chat/history",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assistant_messages = [message for message in payload if message["role"] == "assistant"]
    assert assistant_messages[0]["references"][0]["ref_id"] == "1:1"
    assert assistant_messages[1]["references"][0]["ref_id"] == "2:1"


def test_chunks_endpoints_scope(
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("owner@example.com")
    session.add(user)
    session.commit()

    headers = auth_headers(user, settings)
    created_nb = client.post(
        "/api/v1/notebooks/",
        json={"name": "Test Notebook", "description": "", "tags": []},
        headers=headers,
    ).json()
    nb_id = created_nb["id"]

    # Add a mock document and chunk
    doc = NotebookDocument(
        id=uuid4(),
        notebook_id=UUID(nb_id),
        user_id=user.id,
        s3_bucket="bucket",
        s3_key="key",
        filename="test.pdf",
        status="indexed",
    )
    session.add(doc)
    session.commit()

    chunk = NotebookDocumentChunk(
        id=uuid4(),
        document_id=doc.id,
        notebook_id=UUID(nb_id),
        user_id=user.id,
        chunk_index=0,
        content="Grounding content",
        embedding=[0.0] * 1536,
    )
    session.add(chunk)
    session.commit()

    # Test GET chunks for document
    resp = client.get(
        f"/api/v1/notebooks/{nb_id}/documents/chunks?filename=test.pdf",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["content"] == "Grounding content"
    assert data[0]["chunk_index"] == 0

    # Test GET single chunk
    resp_single = client.get(
        f"/api/v1/notebooks/{nb_id}/chunks?filename=test.pdf&chunk_index=0",
        headers=headers,
    )
    assert resp_single.status_code == 200
    assert resp_single.json()["content"] == "Grounding content"

    # Test GET chunks for document by document id (frontend path)
    resp_by_id = client.get(
        f"/api/v1/notebooks/{nb_id}/documents/{doc.id}/chunks",
        headers=headers,
    )
    assert resp_by_id.status_code == 200
    by_id_data = resp_by_id.json()
    assert len(by_id_data) == 1
    assert by_id_data[0]["content"] == "Grounding content"
    assert by_id_data[0]["chunk_index"] == 0
    assert by_id_data[0]["document_id"] == str(doc.id)

    # Test GET single chunk by document id + chunk index (frontend path)
    resp_single_by_id = client.get(
        f"/api/v1/notebooks/{nb_id}/documents/{doc.id}/chunks/0",
        headers=headers,
    )
    assert resp_single_by_id.status_code == 200
    assert resp_single_by_id.json()["content"] == "Grounding content"
    assert resp_single_by_id.json()["document_id"] == str(doc.id)


def test_append_notebook_chat_history_does_not_delete_old_messages(session: Session) -> None:
    from app.notebooks.memory.history import append_notebook_chat_history
    from app.notebooks.models import Notebook, NotebookMessage
    import uuid

    notebook = Notebook(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="Test Notebook",
        description="",
        tags=[],
    )
    session.add(notebook)
    session.commit()

    msg_pair_1 = [
        ModelRequest(parts=[UserPromptPart(content="Hello")]),
        ModelResponse(parts=[TextPart(content="Hi there")]),
    ]
    append_notebook_chat_history(session, notebook, msg_pair_1)

    stored_1 = session.exec(
        select(NotebookMessage)
        .where(NotebookMessage.notebook_id == notebook.id)
        .order_by(NotebookMessage.seq.asc())
    ).all()
    assert len(stored_1) == 2
    assert stored_1[0].seq == 1
    assert stored_1[0].message["parts"][0]["content"] == "Hello"
    assert stored_1[1].seq == 2
    assert stored_1[1].message["parts"][0]["content"] == "Hi there"

    msg_pair_2 = [
        ModelRequest(parts=[UserPromptPart(content="How are you?")]),
        ModelResponse(parts=[TextPart(content="I am doing great")]),
    ]
    append_notebook_chat_history(session, notebook, msg_pair_2)

    stored_2 = session.exec(
        select(NotebookMessage)
        .where(NotebookMessage.notebook_id == notebook.id)
        .order_by(NotebookMessage.seq.asc())
    ).all()
    assert len(stored_2) == 4
    assert stored_2[0].seq == 1
    assert stored_2[1].seq == 2
    assert stored_2[2].seq == 3
    assert stored_2[2].message["parts"][0]["content"] == "How are you?"
    assert stored_2[3].seq == 4
    assert stored_2[3].message["parts"][0]["content"] == "I am doing great"

