import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from app.auth.models import RefreshToken
from app.auth.service import hash_refresh_token
from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.dependencies import get_session
from app.main import app
from app.users.models import User


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        jwt_secret_key="test-secret-with-at-least-32-bytes",
        jwt_algorithm="HS256",
        access_token_expire_minutes=30,
        refresh_token_expire_days=30,
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


@pytest.fixture
def user(session: Session) -> User:
    user = User(email="auth@example.com", hashed_password=hash_password("correct-password"))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def login(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/sessions",
        data={"username": "auth@example.com", "password": "correct-password"},
    )

    assert response.status_code == 200
    return response.json()


def refresh(client: TestClient, refresh_token: str):
    return client.post(
        "/api/v1/auth/token-refreshes",
        json={"refresh_token": refresh_token},
    )


def get_refresh_token(session: Session, raw_refresh_token: str) -> RefreshToken:
    token_hash = hash_refresh_token(raw_refresh_token)
    token = session.exec(select(RefreshToken).where(RefreshToken.token_hash == token_hash)).one()
    return token


def test_refresh_rotates_token_and_rejects_reuse(
    client: TestClient, session: Session, user: User
) -> None:
    first_tokens = login(client)

    rotate_response = refresh(client, first_tokens["refresh_token"])

    assert rotate_response.status_code == 200
    second_tokens = rotate_response.json()
    assert second_tokens["refresh_token"] != first_tokens["refresh_token"]

    reused_response = refresh(client, first_tokens["refresh_token"])

    assert reused_response.status_code == 401

    second_response = refresh(client, second_tokens["refresh_token"])

    assert second_response.status_code == 401

    family_id = get_refresh_token(session, first_tokens["refresh_token"]).family_id
    family_tokens = session.exec(select(RefreshToken).where(RefreshToken.family_id == family_id)).all()
    assert len(family_tokens) == 2
    assert all(token.revoked_at is not None for token in family_tokens)


def test_expired_refresh_token_is_rejected_and_revoked(
    client: TestClient, session: Session, user: User
) -> None:
    tokens = login(client)
    refresh_token = get_refresh_token(session, tokens["refresh_token"])
    refresh_token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.add(refresh_token)
    session.commit()

    response = refresh(client, tokens["refresh_token"])

    assert response.status_code == 401
    session.refresh(refresh_token)
    assert refresh_token.revoked_at is not None


def test_logout_revokes_refresh_token_family(
    client: TestClient, session: Session, user: User
) -> None:
    first_tokens = login(client)
    rotate_response = refresh(client, first_tokens["refresh_token"])
    assert rotate_response.status_code == 200
    second_tokens = rotate_response.json()

    logout_response = client.request(
        "DELETE",
        "/api/v1/auth/sessions/current",
        json={"refresh_token": second_tokens["refresh_token"]},
    )

    assert logout_response.status_code == 204
    assert refresh(client, second_tokens["refresh_token"]).status_code == 401

    family_id = get_refresh_token(session, first_tokens["refresh_token"]).family_id
    family_tokens = session.exec(select(RefreshToken).where(RefreshToken.family_id == family_id)).all()
    assert len(family_tokens) == 2
    assert all(token.revoked_at is not None for token in family_tokens)
