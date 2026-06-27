from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.users.dependencies import get_current_user
from app.users.models import User
from tests.conftest import auth_headers, make_user

pytestmark = pytest.mark.anyio


class TestUserRBAC:
    async def test_access_token_includes_user_role_claim(
        self,
        settings: Any,
    ) -> None:
        user = make_user(email="admin@example.com", role="admin")

        token = create_access_token(user, settings)
        import jwt

        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )

        assert payload["role"] == "admin"

    async def test_new_users_default_to_user_role(self) -> None:
        user = User(email="new@example.com", hashed_password="hashed-password")

        assert user.role == "user"

    async def test_current_user_response_includes_role(
        self,
        client: AsyncClient,
        app: Any,
        settings: Any,
    ) -> None:
        user = make_user(email="me@example.com", role="admin")
        app.dependency_overrides[get_current_user] = lambda: user

        response = await client.get("/api/v1/users/me")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["role"] == "admin"

    async def test_user_token_cannot_list_users(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = make_user(email="user@example.com", role="user")

        response = await client.get(
            "/api/v1/users/", headers=auth_headers(user, settings)
        )

        assert response.status_code == 403

    async def test_admin_token_can_list_users(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        admin = make_user(email="admin@example.com", role="admin")
        await admin.insert()
        user = make_user(email="user@example.com", role="user")
        await user.insert()

        response = await client.get(
            "/api/v1/users/", headers=auth_headers(admin, settings)
        )

        assert response.status_code == 200
        emails = {item["email"] for item in response.json()}
        assert "admin@example.com" in emails
        assert "user@example.com" in emails

    async def test_current_user_can_be_loaded_from_authorization_header(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = make_user(email="header@example.com", role="admin")
        await user.insert()

        response = await client.get(
            "/api/v1/users/me", headers=auth_headers(user, settings)
        )

        assert response.status_code == 200
        assert response.json()["email"] == "header@example.com"
        assert response.json()["role"] == "admin"

    async def test_missing_token_cannot_list_users(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        response = await client.get("/api/v1/users/")

        assert response.status_code == 401

    async def test_invalid_token_cannot_list_users(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        response = await client.get(
            "/api/v1/users/", headers={"Authorization": "Bearer invalid-token"}
        )

        assert response.status_code == 401
