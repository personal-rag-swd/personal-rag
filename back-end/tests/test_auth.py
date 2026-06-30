from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient

from app.auth.models import PendingRegistration
from app.users.models import User
from tests.conftest import create_user, make_user, password_hash

pytestmark = pytest.mark.anyio


class TestAuthRegistration:
    async def test_register_success(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        response = await client.post(
            "/api/v1/auth/registrations",
            json={
                "email": "newuser@example.com",
                "password": "StrongPass1!",
                "confirm_password": "StrongPass1!",
            },
        )
        assert response.status_code == 202

        pending = await PendingRegistration.find_one(
            PendingRegistration.email == "newuser@example.com"
        )
        assert pending is not None
        assert pending.otp_attempts == 0

    async def test_register_duplicate_email(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        await create_user(email="existing@example.com")

        response = await client.post(
            "/api/v1/auth/registrations",
            json={
                "email": "existing@example.com",
                "password": "StrongPass1!",
                "confirm_password": "StrongPass1!",
            },
        )
        assert response.status_code == 409

    async def test_register_weak_password(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        response = await client.post(
            "/api/v1/auth/registrations",
            json={
                "email": "user@example.com",
                "password": "ab",
            },
        )
        assert response.status_code == 422


class TestAuthEmailVerification:
    async def test_verify_email_success(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        from datetime import UTC, datetime, timedelta

        expires_at = datetime.now(UTC) + timedelta(hours=1)
        pending = PendingRegistration(
            email="otpuser@example.com",
            hashed_password=password_hash.hash("StrongPass1!"),
            hashed_otp=password_hash.hash("123456"),
            expires_at=expires_at,
        )
        await pending.insert()

        response = await client.post(
            "/api/v1/auth/email-verifications",
            json={
                "email": "otpuser@example.com",
                "otp": "123456",
            },
        )
        assert response.status_code == 200

        user = await User.find_one(User.email == "otpuser@example.com")
        assert user is not None
        assert user.is_active

    async def test_verify_email_invalid(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        from datetime import UTC, datetime, timedelta

        expires_at = datetime.now(UTC) + timedelta(hours=1)
        pending = PendingRegistration(
            email="otpuser2@example.com",
            hashed_password=password_hash.hash("StrongPass1!"),
            hashed_otp=password_hash.hash("123456"),
            expires_at=expires_at,
        )
        await pending.insert()

        response = await client.post(
            "/api/v1/auth/email-verifications",
            json={
                "email": "otpuser2@example.com",
                "otp": "000000",
            },
        )
        assert response.status_code == 400

    async def test_verify_email_expired(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        pending = PendingRegistration(
            email="expired@example.com",
            hashed_password=password_hash.hash("StrongPass1!"),
            hashed_otp=password_hash.hash("123456"),
            expires_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        await pending.insert()

        response = await client.post(
            "/api/v1/auth/email-verifications",
            json={"email": "expired@example.com", "otp": "123456"},
        )
        assert response.status_code == 400

    async def test_verify_email_too_many_attempts(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        from datetime import UTC, datetime, timedelta

        expires_at = datetime.now(UTC) + timedelta(hours=1)
        pending = PendingRegistration(
            email="maxed@example.com",
            hashed_password=password_hash.hash("StrongPass1!"),
            hashed_otp=password_hash.hash("123456"),
            expires_at=expires_at,
            otp_attempts=5,
        )
        await pending.insert()

        response = await client.post(
            "/api/v1/auth/email-verifications",
            json={"email": "maxed@example.com", "otp": "123456"},
        )
        assert response.status_code == 400


class TestAuthSessions:
    async def test_login_success(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = make_user(email="login@example.com")
        await user.insert()
        user.is_active = True
        await user.save()

        response = await client.post(
            "/api/v1/auth/sessions",
            data={
                "username": "login@example.com",
                "password": "password123",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        refresh_token = response.cookies.get("refresh_token")
        assert refresh_token is not None

    async def test_login_inactive(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = make_user(email="inactive@example.com")
        user.is_active = False
        await user.insert()

        response = await client.post(
            "/api/v1/auth/sessions",
            data={
                "username": "inactive@example.com",
                "password": "password123",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 401

    async def test_login_wrong_password(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = make_user(email="wrongpw@example.com")
        user.is_active = True
        await user.insert()

        response = await client.post(
            "/api/v1/auth/sessions",
            data={
                "username": "wrongpw@example.com",
                "password": "wrongpass",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 401


class TestAuthTokenRefresh:
    async def test_refresh_success(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = make_user(email="refresh@example.com", role="user")
        user.is_active = True
        await user.insert()

        login_response = await client.post(
            "/api/v1/auth/sessions",
            data={
                "username": "refresh@example.com",
                "password": "password123",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        refresh_token = login_response.cookies.get("refresh_token")
        assert refresh_token is not None

        response = await client.post(
            "/api/v1/auth/token-refreshes",
            headers={"Cookie": f"refresh_token={refresh_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        new_refresh_token = response.cookies.get("refresh_token")
        assert new_refresh_token is not None

    async def test_refresh_missing_cookie(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        response = await client.post("/api/v1/auth/token-refreshes")
        assert response.status_code == 401


class TestAuthLogout:
    async def test_logout(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = make_user(email="logout@example.com", role="user")
        user.is_active = True
        await user.insert()

        login_response = await client.post(
            "/api/v1/auth/sessions",
            data={
                "username": "logout@example.com",
                "password": "password123",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert login_response.status_code == 200
        refresh_token = login_response.cookies.get("refresh_token")
        assert refresh_token is not None

        response = await client.delete(
            "/api/v1/auth/sessions/current",
            headers={"Cookie": f"refresh_token={refresh_token}"},
        )
        assert response.status_code == 204
