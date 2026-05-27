from collections.abc import Generator
from typing import Any
from uuid import UUID
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import ModelMessagesTypeAdapter
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
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


class FakeRunResult:
    def __init__(self, messages: list[ModelMessage]) -> None:
        self._messages = messages

    def all_messages(self) -> list[ModelMessage]:
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
