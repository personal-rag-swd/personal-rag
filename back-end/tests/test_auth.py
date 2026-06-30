from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient

from app.auth.models import PasswordResetRequest, PendingRegistration
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


class TestPasswordReset:
    async def test_request_reset_for_existing_user(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        await create_user(email="resetme@example.com")
        response = await client.post(
            "/api/v1/auth/password-resets",
            json={"email": "resetme@example.com"},
        )
        assert response.status_code == 202
        reset_req = await PasswordResetRequest.find_one({"email": "resetme@example.com"})
        assert reset_req is not None

    async def test_request_reset_for_nonexistent_user_is_silent(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        # Must return 202 without leaking that the account does not exist
        response = await client.post(
            "/api/v1/auth/password-resets",
            json={"email": "ghost@example.com"},
        )
        assert response.status_code == 202
        reset_req = await PasswordResetRequest.find_one({"email": "ghost@example.com"})
        assert reset_req is None

    async def test_request_reset_replaces_existing_request(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        await create_user(email="replace@example.com")
        first = PasswordResetRequest(
            email="replace@example.com",
            hashed_otp=password_hash.hash("111111"),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        await first.insert()
        first_id = first.id

        await client.post(
            "/api/v1/auth/password-resets",
            json={"email": "replace@example.com"},
        )
        reset_req = await PasswordResetRequest.find_one({"email": "replace@example.com"})
        assert reset_req is not None
        assert reset_req.id != first_id

    async def test_verify_reset_success(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        await create_user(email="pwreset@example.com")
        # Log in to get a refresh token that should be revoked after reset
        login = await client.post(
            "/api/v1/auth/sessions",
            data={"username": "pwreset@example.com", "password": "password123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert login.status_code == 200
        old_refresh_token = login.cookies.get("refresh_token")
        assert old_refresh_token is not None

        reset_req = PasswordResetRequest(
            email="pwreset@example.com",
            hashed_otp=password_hash.hash("123456"),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        await reset_req.insert()

        response = await client.post(
            "/api/v1/auth/password-resets/verify",
            json={
                "email": "pwreset@example.com",
                "otp": "123456",
                "new_password": "NewPassword1!",
            },
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Password actually changed
        updated = await User.find_one({"email": "pwreset@example.com"})
        assert updated is not None
        from app.core.security import verify_password
        assert verify_password("NewPassword1!", updated.hashed_password)
        assert not verify_password("password123", updated.hashed_password)

        # Reset request is deleted
        leftover = await PasswordResetRequest.find_one({"email": "pwreset@example.com"})
        assert leftover is None

        # Old session is revoked
        from app.auth.models import RefreshToken
        from app.auth.service import hash_refresh_token as _hash
        token_doc = await RefreshToken.find_one({"token_hash": _hash(old_refresh_token)})
        assert token_doc is not None
        assert token_doc.revoked_at is not None

    async def test_verify_reset_wrong_otp(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        await create_user(email="wrongotp@example.com")
        reset_req = PasswordResetRequest(
            email="wrongotp@example.com",
            hashed_otp=password_hash.hash("123456"),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        await reset_req.insert()

        response = await client.post(
            "/api/v1/auth/password-resets/verify",
            json={
                "email": "wrongotp@example.com",
                "otp": "000000",
                "new_password": "NewPassword1!",
            },
        )
        assert response.status_code == 400

    async def test_verify_reset_expired(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        await create_user(email="expired@example.com")
        reset_req = PasswordResetRequest(
            email="expired@example.com",
            hashed_otp=password_hash.hash("123456"),
            expires_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        await reset_req.insert()

        response = await client.post(
            "/api/v1/auth/password-resets/verify",
            json={
                "email": "expired@example.com",
                "otp": "123456",
                "new_password": "NewPassword1!",
            },
        )
        assert response.status_code == 400

    async def test_verify_reset_max_attempts_locks_out(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        await create_user(email="maxotp@example.com")
        reset_req = PasswordResetRequest(
            email="maxotp@example.com",
            hashed_otp=password_hash.hash("123456"),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            otp_attempts=5,
        )
        await reset_req.insert()

        response = await client.post(
            "/api/v1/auth/password-resets/verify",
            json={
                "email": "maxotp@example.com",
                "otp": "123456",
                "new_password": "NewPassword1!",
            },
        )
        assert response.status_code == 400

    async def test_verify_reset_no_pending_request(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        response = await client.post(
            "/api/v1/auth/password-resets/verify",
            json={
                "email": "nobody@example.com",
                "otp": "123456",
                "new_password": "NewPassword1!",
            },
        )
        assert response.status_code == 400
