import os
from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.dependencies import get_session
from app.main import app
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
    assert body["document_count"] == 0
    assert body["query_count"] == 0

    list_response = client.get("/api/v1/notebooks/", headers=auth_headers(user, settings))
    assert list_response.status_code == 200
    assert [notebook["id"] for notebook in list_response.json()] == [body["id"]]


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
