from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import choice, token_urlsafe
from string import digits
from uuid import UUID

import resend
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.auth.models import PendingRegistration, RefreshToken
from app.core.config import Settings
from app.core.security import create_access_token, hash_password, verify_password
from app.users.models import User


def normalize_email(email: str) -> str:
    return email.strip().lower()


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def generate_otp() -> str:
    return "".join(choice(digits) for _ in range(6))


def hash_refresh_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def send_registration_otp(email: str, otp: str, settings: Settings) -> None:
    if not settings.resend_api_key:
        raise RuntimeError("RESEND_API_KEY must be set to send registration email.")

    resend.api_key = settings.resend_api_key
    resend.Emails.send(
        {
            "from": settings.resend_from_email,
            "to": [email],
            "subject": "Your verification code",
            "html": f"<p>Your verification code is <strong>{otp}</strong>.</p>",
        }
    )


def start_registration(
    session: Session, email: str, password: str, settings: Settings
) -> None:
    normalized_email = normalize_email(email)
    existing_user = session.exec(
        select(User).where(User.email == normalized_email)
    ).first()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email is already registered"
        )

    existing_pending = session.exec(
        select(PendingRegistration).where(PendingRegistration.email == normalized_email)
    ).first()
    if existing_pending is not None:
        session.delete(existing_pending)
        session.flush()

    otp = generate_otp()
    pending = PendingRegistration(
        email=normalized_email,
        hashed_password=hash_password(password),
        hashed_otp=hash_password(otp),
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.otp_expire_minutes),
    )
    session.add(pending)
    session.flush()

    try:
        send_registration_otp(normalized_email, otp, settings)
        session.commit()
    except Exception as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not send verification email",
        ) from exc


def verify_registration_otp(
    session: Session, email: str, otp: str, settings: Settings
) -> None:
    normalized_email = normalize_email(email)
    pending = session.exec(
        select(PendingRegistration).where(PendingRegistration.email == normalized_email)
    ).first()
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    if (
        as_utc(pending.expires_at) <= datetime.now(UTC)
        or pending.otp_attempts >= settings.otp_max_attempts
    ):
        session.delete(pending)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    if not verify_password(otp, pending.hashed_otp):
        pending.otp_attempts += 1
        pending.updated_at = datetime.now(UTC)
        if pending.otp_attempts >= settings.otp_max_attempts:
            session.delete(pending)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    existing_user = session.exec(
        select(User).where(User.email == normalized_email)
    ).first()
    if existing_user is not None:
        session.delete(pending)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email is already registered"
        )

    user = User(email=normalized_email, hashed_password=pending.hashed_password)
    session.add(user)
    session.delete(pending)
    session.commit()


def authenticate_user(session: Session, email: str, password: str) -> User:
    normalized_email = normalize_email(email)
    user = session.exec(select(User).where(User.email == normalized_email)).first()
    if (
        user is None
        or not user.is_active
        or not verify_password(password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def issue_token_pair(
    session: Session, user: User, settings: Settings, family_id: UUID | None = None
) -> dict[str, str]:
    raw_refresh_token = token_urlsafe(64)
    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh_token),
        family_id=family_id or UUID(int=0),
        expires_at=datetime.now(UTC)
        + timedelta(days=settings.refresh_token_expire_days),
    )
    if family_id is None:
        refresh_token.family_id = refresh_token.id
    session.add(refresh_token)
    session.flush()
    return {
        "access_token": create_access_token(user, settings),
        "refresh_token": raw_refresh_token,
        "token_type": "bearer",
        "_refresh_token_id": str(refresh_token.id),
    }


def create_session(
    session: Session, email: str, password: str, settings: Settings
) -> dict[str, str]:
    user = authenticate_user(session, email, password)
    tokens = issue_token_pair(session, user, settings)
    session.commit()
    tokens.pop("_refresh_token_id", None)
    return tokens


def revoke_token_family(session: Session, family_id: UUID) -> None:
    now = datetime.now(UTC)
    tokens = session.exec(
        select(RefreshToken).where(RefreshToken.family_id == family_id)
    ).all()
    for token in tokens:
        if token.revoked_at is None:
            token.revoked_at = now
            session.add(token)


def refresh_session(
    session: Session, raw_refresh_token: str, settings: Settings
) -> dict[str, str]:
    token_hash = hash_refresh_token(raw_refresh_token)
    refresh_token = session.exec(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).first()
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    now = datetime.now(UTC)
    if refresh_token.revoked_at is not None:
        revoke_token_family(session, refresh_token.family_id)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    if as_utc(refresh_token.expires_at) <= now:
        refresh_token.revoked_at = now
        session.add(refresh_token)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    user = session.get(User, refresh_token.user_id)
    if user is None or not user.is_active:
        revoke_token_family(session, refresh_token.family_id)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    refresh_token.revoked_at = now
    session.add(refresh_token)
    tokens = issue_token_pair(
        session, user, settings, family_id=refresh_token.family_id
    )
    refresh_token.replaced_by_token_id = UUID(tokens["_refresh_token_id"])
    session.add(refresh_token)
    session.commit()
    tokens.pop("_refresh_token_id", None)
    return tokens


def logout_session(session: Session, raw_refresh_token: str) -> None:
    token_hash = hash_refresh_token(raw_refresh_token)
    refresh_token = session.exec(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).first()
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    try:
        revoke_token_family(session, refresh_token.family_id)
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error"
        ) from exc
