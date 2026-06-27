from __future__ import annotations

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from app.auth.models import RefreshToken
from app.auth.service import hash_refresh_token
from tests.conftest import make_user


async def _refresh(client: AsyncClient, rt: str) -> object:
    return await client.post(
        "/api/v1/auth/token-refreshes",
        headers={"Cookie": f"refresh_token={rt}"},
    )


async def _delete_session(client: AsyncClient, rt: str) -> object:
    return await client.delete(
        "/api/v1/auth/sessions/current",
        headers={"Cookie": f"refresh_token={rt}"},
    )


async def test_refresh_rotates_token_and_rejects_reuse(
    client: AsyncClient,
    settings: object,
) -> None:
    user = make_user(email="auth@example.com")
    user.is_active = True
    await user.insert()

    login_response = await client.post(
        "/api/v1/auth/sessions",
        data={"username": "auth@example.com", "password": "password123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login_response.status_code == 200
    first_rt = login_response.cookies.get("refresh_token")
    assert first_rt is not None

    rotate_response = await _refresh(client, first_rt)
    assert rotate_response.status_code == 200
    second_rt = rotate_response.cookies.get("refresh_token")
    assert second_rt is not None
    assert second_rt != first_rt

    reused_response = await _refresh(client, first_rt)
    assert reused_response.status_code == 401

    second_usage_response = await _refresh(client, second_rt)
    assert second_usage_response.status_code == 401


async def test_expired_refresh_token_is_rejected_and_revoked(
    client: AsyncClient,
    settings: object,
) -> None:
    user = make_user(email="expired@example.com")
    user.is_active = True
    await user.insert()

    login_response = await client.post(
        "/api/v1/auth/sessions",
        data={"username": "expired@example.com", "password": "password123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login_response.status_code == 200
    rt = login_response.cookies.get("refresh_token")
    assert rt is not None

    token = await RefreshToken.find_one(
        RefreshToken.token_hash == hash_refresh_token(rt)
    )
    assert token is not None
    token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await token.save()

    response = await _refresh(client, rt)
    assert response.status_code == 401

    refreshed = await RefreshToken.find_one(RefreshToken.id == token.id)
    assert refreshed is not None
    assert refreshed.revoked_at is not None


async def test_logout_revokes_refresh_token_family(
    client: AsyncClient,
    settings: object,
) -> None:
    user = make_user(email="logout@example.com")
    user.is_active = True
    await user.insert()

    login_response = await client.post(
        "/api/v1/auth/sessions",
        data={"username": "logout@example.com", "password": "password123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login_response.status_code == 200
    first_rt = login_response.cookies.get("refresh_token")
    assert first_rt is not None

    rotate_response = await _refresh(client, first_rt)
    assert rotate_response.status_code == 200
    second_rt = rotate_response.cookies.get("refresh_token")
    assert second_rt is not None

    logout_response = await _delete_session(client, second_rt)
    assert logout_response.status_code == 204

    assert (await _refresh(client, second_rt)).status_code == 401
