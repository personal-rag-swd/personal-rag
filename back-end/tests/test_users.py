from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, create_user, make_user

pytestmark = pytest.mark.anyio


class TestUsersAPI:
    async def test_list_users_as_admin(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        admin = make_user(email="admin@example.com", role="admin")
        await admin.insert()
        admin.is_active = True
        await admin.save()

        await create_user(email="user1@example.com", role="user")
        await create_user(email="user2@example.com", role="user")

        headers = auth_headers(admin, settings)
        response = await client.get("/api/v1/users/", headers=headers)
        assert response.status_code == 200
        users = response.json()
        assert len(users) >= 3

    async def test_list_users_as_non_admin(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = make_user(email="regular@example.com", role="user")
        await user.insert()
        user.is_active = True
        await user.save()

        headers = auth_headers(user, settings)
        response = await client.get("/api/v1/users/", headers=headers)
        assert response.status_code == 403

    async def test_get_current_user(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(email="current@example.com", role="user")
        headers = auth_headers(user, settings)

        response = await client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "current@example.com"

    async def test_get_current_user_unauthenticated(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        response = await client.get("/api/v1/users/me")
        assert response.status_code == 401
