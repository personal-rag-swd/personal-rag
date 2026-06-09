from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

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
def client(settings: Settings, session: Session) -> Generator[TestClient]:
    def override_get_settings() -> Settings:
        return settings

    def override_get_session() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def user(session: Session) -> User:
    user = User(
        email="auth@example.com", hashed_password=hash_password("correct-password")
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_cookie_value(client: TestClient, name: str) -> str | None:
    for cookie in client.cookies.jar:
        if cookie.name == name:
            return cookie.value
    return None


def login(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/sessions",
        data={"username": "auth@example.com", "password": "correct-password"},
    )

    assert response.status_code == 200
    tokens = response.json()
    refresh_token = get_cookie_value(client, "refresh_token")
    assert get_cookie_value(client, "access_token") == tokens["access_token"]
    assert refresh_token is not None
    return {
        "access_token": tokens["access_token"],
        "refresh_token": refresh_token,
    }


def refresh(client: TestClient, refresh_token: str | None = None):
    if refresh_token is not None:
        client.cookies.clear()
        client.cookies.set(
            "refresh_token", refresh_token, domain="testserver.local", path="/"
        )
    return client.post(
        "/api/v1/auth/token-refreshes",
    )


def get_refresh_token(session: Session, raw_refresh_token: str) -> RefreshToken:
    token_hash = hash_refresh_token(raw_refresh_token)
    return session.exec(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).one()


def test_refresh_rotates_token_and_rejects_reuse(
    client: TestClient, session: Session, user: User
) -> None:
    first_tokens = login(client)
    first_rt = first_tokens["refresh_token"]

    rotate_response = refresh(client, first_rt)

    assert rotate_response.status_code == 200
    assert (
        get_cookie_value(client, "access_token")
        == rotate_response.json()["access_token"]
    )
    second_rt = get_cookie_value(client, "refresh_token")
    assert second_rt != first_rt

    reused_response = refresh(client, first_rt)

    assert reused_response.status_code == 401

    second_response = refresh(client, second_rt)

    assert second_response.status_code == 401

    family_id = get_refresh_token(session, first_rt).family_id
    family_tokens = session.exec(
        select(RefreshToken).where(RefreshToken.family_id == family_id)
    ).all()
    assert len(family_tokens) == 2
    assert all(token.revoked_at is not None for token in family_tokens)


def test_expired_refresh_token_is_rejected_and_revoked(
    client: TestClient, session: Session, user: User
) -> None:
    tokens = login(client)
    rt = tokens["refresh_token"]
    refresh_token = get_refresh_token(session, rt)
    refresh_token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.add(refresh_token)
    session.commit()

    response = refresh(client, rt)

    assert response.status_code == 401
    session.refresh(refresh_token)
    assert refresh_token.revoked_at is not None


def test_logout_revokes_refresh_token_family(
    client: TestClient, session: Session, user: User
) -> None:
    first_tokens = login(client)
    first_rt = first_tokens["refresh_token"]
    rotate_response = refresh(client, first_rt)
    assert rotate_response.status_code == 200
    second_rt = get_cookie_value(client, "refresh_token")

    client.cookies.clear()
    client.cookies.set("refresh_token", second_rt, domain="testserver.local", path="/")
    logout_response = client.request(
        "DELETE",
        "/api/v1/auth/sessions/current",
    )

    assert logout_response.status_code == 204
    assert get_cookie_value(client, "access_token") is None
    assert get_cookie_value(client, "refresh_token") is None
    assert refresh(client, second_rt).status_code == 401

    family_id = get_refresh_token(session, first_rt).family_id
    family_tokens = session.exec(
        select(RefreshToken).where(RefreshToken.family_id == family_id)
    ).all()
    assert len(family_tokens) == 2
    assert all(token.revoked_at is not None for token in family_tokens)
