from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.core.config import Settings
from app.core.security import create_access_token, hash_password
from app.main import app
from app.users.dependencies import get_current_user
from app.users.models import User


def login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/sessions",
        data={"username": "auth@example.com", "password": "correct-password"},
    )

    assert response.status_code == 200


def test_access_token_includes_user_role_claim(
    settings: Settings, user_factory
) -> None:
    user = user_factory("admin@example.com", role="admin")

    token = create_access_token(user, settings)
    payload = jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )

    assert payload["role"] == "admin"


def test_new_users_default_to_user_role() -> None:
    user = User(email="new@example.com", hashed_password="hashed-password")

    assert user.role == "user"


def test_user_role_is_constrained(session: Session) -> None:
    session.add(
        User(
            email="bad-role@example.com",
            hashed_password="hashed-password",
            role="owner",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_current_user_response_includes_role(client: TestClient) -> None:
    user = User(
        id=uuid4(),
        email="me@example.com",
        hashed_password="hashed-password",
        role="admin",
    )
    app.dependency_overrides[get_current_user] = lambda: user

    response = client.get("/api/v1/users/me")

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_user_token_cannot_list_users(
    client: TestClient, auth_headers, user_factory
) -> None:
    user = user_factory("user@example.com", role="user")

    response = client.get("/api/v1/users/", headers=auth_headers(user))

    assert response.status_code == 403


def test_admin_token_can_list_users(
    client: TestClient, auth_headers, session: Session, user_factory
) -> None:
    admin = user_factory("admin@example.com", role="admin")
    user = user_factory("user@example.com", role="user")
    session.add(admin)
    session.add(user)
    session.commit()

    response = client.get("/api/v1/users/", headers=auth_headers(admin))

    assert response.status_code == 200
    assert {item["email"] for item in response.json()} == {
        "admin@example.com",
        "user@example.com",
    }
    assert {item["role"] for item in response.json()} == {"admin", "user"}


def test_current_user_can_be_loaded_from_access_token_cookie(
    client: TestClient, session: Session
) -> None:
    user = User(
        email="auth@example.com", hashed_password=hash_password("correct-password")
    )
    session.add(user)
    session.commit()

    login(client)

    response = client.get("/api/v1/users/me")

    assert response.status_code == 200
    assert response.json()["email"] == "auth@example.com"
    assert response.json()["role"] == "user"


def test_current_user_can_be_loaded_from_authorization_header(
    client: TestClient, auth_headers, session: Session, user_factory
) -> None:
    user = user_factory("header@example.com", role="admin")
    session.add(user)
    session.commit()

    response = client.get("/api/v1/users/me", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["email"] == "header@example.com"
    assert response.json()["role"] == "admin"


def test_missing_token_cannot_list_users(client: TestClient) -> None:
    response = client.get("/api/v1/users/")

    assert response.status_code == 401


def test_invalid_token_cannot_list_users(client: TestClient) -> None:
    response = client.get(
        "/api/v1/users/", headers={"Authorization": "Bearer invalid-token"}
    )

    assert response.status_code == 401
