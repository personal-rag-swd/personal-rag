from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth.security import hash_password
from app.models.auth import PendingRegistration, RefreshToken
from app.models.user import User


def register(client: TestClient, monkeypatch, email: str = "user@example.com", password: str = "password123") -> str:
    sent: dict[str, str] = {}

    def fake_send_registration_otp(email: str, otp: str, settings) -> None:
        sent["email"] = email
        sent["otp"] = otp

    monkeypatch.setattr("app.auth.service.send_registration_otp", fake_send_registration_otp)
    response = client.post("/auth/registrations", json={"email": email, "password": password})
    assert response.status_code == 202
    assert sent["email"] == email
    return sent["otp"]


def verify(client: TestClient, email: str, otp: str) -> None:
    response = client.post("/auth/email-verifications", json={"email": email, "otp": otp})
    assert response.status_code == 200
    assert response.json() == {"success": True}


def login(client: TestClient, email: str = "user@example.com", password: str = "password123") -> dict[str, str]:
    response = client.post("/auth/sessions", data={"username": email, "password": password})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    return body


def test_registration_creates_pending_state_and_sends_email(client: TestClient, session: Session, monkeypatch) -> None:
    otp = register(client, monkeypatch)

    pending = session.exec(select(PendingRegistration).where(PendingRegistration.email == "user@example.com")).first()
    assert pending is not None
    assert pending.hashed_password != "password123"
    assert pending.hashed_otp != otp


def test_resend_failure_rolls_back_pending_state(client: TestClient, session: Session, monkeypatch) -> None:
    def fail_send_registration_otp(email: str, otp: str, settings) -> None:
        raise RuntimeError("resend failed")

    monkeypatch.setattr("app.auth.service.send_registration_otp", fail_send_registration_otp)
    response = client.post("/auth/registrations", json={"email": "user@example.com", "password": "password123"})

    assert response.status_code == 502
    pending = session.exec(select(PendingRegistration).where(PendingRegistration.email == "user@example.com")).first()
    assert pending is None


def test_duplicate_verified_email_returns_conflict(client: TestClient, monkeypatch) -> None:
    otp = register(client, monkeypatch)
    verify(client, "user@example.com", otp)

    response = client.post("/auth/registrations", json={"email": "user@example.com", "password": "password123"})

    assert response.status_code == 409


def test_otp_verification_creates_user_and_deletes_pending(client: TestClient, session: Session, monkeypatch) -> None:
    otp = register(client, monkeypatch)
    verify(client, "user@example.com", otp)

    user = session.exec(select(User).where(User.email == "user@example.com")).first()
    pending = session.exec(select(PendingRegistration).where(PendingRegistration.email == "user@example.com")).first()
    assert user is not None
    assert user.hashed_password != "password123"
    assert pending is None


def test_wrong_and_expired_otp_are_rejected(client: TestClient, session: Session, monkeypatch) -> None:
    register(client, monkeypatch)

    wrong_response = client.post("/auth/email-verifications", json={"email": "user@example.com", "otp": "000000"})
    assert wrong_response.status_code == 400

    pending = session.exec(select(PendingRegistration).where(PendingRegistration.email == "user@example.com")).first()
    assert pending is not None
    pending.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    session.add(pending)
    session.commit()

    expired_response = client.post("/auth/email-verifications", json={"email": "user@example.com", "otp": "000000"})
    assert expired_response.status_code == 400


def test_login_rejects_unverified_and_inactive_users(client: TestClient, session: Session, monkeypatch) -> None:
    register(client, monkeypatch)
    unverified_response = client.post("/auth/sessions", data={"username": "user@example.com", "password": "password123"})
    assert unverified_response.status_code == 401

    inactive_user = User(email="inactive@example.com", hashed_password=hash_password("password123"), is_active=False)
    session.add(inactive_user)
    session.commit()

    inactive_response = client.post(
        "/auth/sessions",
        data={"username": "inactive@example.com", "password": "password123"},
    )
    assert inactive_response.status_code == 401


def test_login_and_users_me_with_valid_access_token(client: TestClient, monkeypatch) -> None:
    otp = register(client, monkeypatch)
    verify(client, "user@example.com", otp)
    tokens = login(client)

    response = client.get("/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_refresh_rotation_revokes_old_token_and_issues_new_tokens(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    otp = register(client, monkeypatch)
    verify(client, "user@example.com", otp)
    tokens = login(client)

    response = client.post("/auth/token-refreshes", json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 200
    rotated = response.json()
    assert rotated["access_token"] != tokens["access_token"]
    assert rotated["refresh_token"] != tokens["refresh_token"]
    stored_tokens = session.exec(select(RefreshToken)).all()
    assert len(stored_tokens) == 2
    assert sum(token.revoked_at is not None for token in stored_tokens) == 1


def test_reused_refresh_token_revokes_its_family(client: TestClient, session: Session, monkeypatch) -> None:
    otp = register(client, monkeypatch)
    verify(client, "user@example.com", otp)
    tokens = login(client)
    rotated = client.post("/auth/token-refreshes", json={"refresh_token": tokens["refresh_token"]}).json()

    reuse_response = client.post("/auth/token-refreshes", json={"refresh_token": tokens["refresh_token"]})
    new_token_response = client.post("/auth/token-refreshes", json={"refresh_token": rotated["refresh_token"]})

    assert reuse_response.status_code == 401
    assert new_token_response.status_code == 401
    stored_tokens = session.exec(select(RefreshToken)).all()
    assert all(token.revoked_at is not None for token in stored_tokens)


def test_logout_revokes_only_current_session(client: TestClient, monkeypatch) -> None:
    otp = register(client, monkeypatch)
    verify(client, "user@example.com", otp)
    first_session = login(client)
    second_session = login(client)

    logout_response = client.request(
        "DELETE",
        "/auth/sessions/current",
        json={"refresh_token": first_session["refresh_token"]},
    )
    first_refresh = client.post("/auth/token-refreshes", json={"refresh_token": first_session["refresh_token"]})
    second_refresh = client.post("/auth/token-refreshes", json={"refresh_token": second_session["refresh_token"]})

    assert logout_response.status_code == 204
    assert first_refresh.status_code == 401
    assert second_refresh.status_code == 200
