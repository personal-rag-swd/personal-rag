from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import choice, token_urlsafe
from string import digits
from uuid import UUID

import resend
from fastapi import HTTPException, status

from app.auth.domain_events import RegistrationRequested, RegistrationVerified
from app.auth.models import PendingRegistration, RefreshToken
from app.core.config import Settings
from app.core.event_bus import domain_event_bus
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


async def start_registration(
    email: str, password: str, settings: Settings
) -> None:
    normalized_email = normalize_email(email)
    existing_user = await User.find_one({"email": normalized_email})
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email is already registered"
        )

    existing_pending = await PendingRegistration.find_one(
        {"email": normalized_email}
    )
    if existing_pending is not None:
        await existing_pending.delete()

    otp = generate_otp()
    pending = PendingRegistration(
        email=normalized_email,
        hashed_password=hash_password(password),
        hashed_otp=hash_password(otp),
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.otp_expire_minutes),
    )
    try:
        # The OTP email is delivered by the (critical) RegistrationRequested
        # listener; a delivery failure propagates here and is surfaced as a 502,
        # so no pending registration is stored when the email cannot be sent.
        await domain_event_bus.emit(
            RegistrationRequested(email=normalized_email, otp=otp, settings=settings)
        )
        await pending.insert()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not send verification email",
        ) from exc


async def verify_registration_otp(
    email: str, otp: str, settings: Settings
) -> None:
    normalized_email = normalize_email(email)
    pending = await PendingRegistration.find_one(
        {"email": normalized_email}
    )
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    if (
        as_utc(pending.expires_at) <= datetime.now(UTC)
        or pending.otp_attempts >= settings.otp_max_attempts
    ):
        await pending.delete()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    if not verify_password(otp, pending.hashed_otp):
        pending.otp_attempts += 1
        pending.updated_at = datetime.now(UTC)
        if pending.otp_attempts >= settings.otp_max_attempts:
            await pending.delete()
        else:
            await pending.save()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    existing_user = await User.find_one({"email": normalized_email})
    if existing_user is not None:
        await pending.delete()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email is already registered"
        )

    user = User(email=normalized_email, hashed_password=pending.hashed_password)
    await user.insert()
    await pending.delete()
    await domain_event_bus.emit(
        RegistrationVerified(user_id=user.id, email=normalized_email)
    )


async def authenticate_user(email: str, password: str) -> User:
    normalized_email = normalize_email(email)
    user = await User.find_one({"email": normalized_email})
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


async def issue_token_pair(
    user: User, settings: Settings, family_id: UUID | None = None
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
    await refresh_token.insert()
    return {
        "access_token": create_access_token(user, settings),
        "refresh_token": raw_refresh_token,
        "token_type": "bearer",
        "_refresh_token_id": str(refresh_token.id),
    }


async def create_session(
    email: str, password: str, settings: Settings
) -> dict[str, str]:
    user = await authenticate_user(email, password)
    tokens = await issue_token_pair(user, settings)
    tokens.pop("_refresh_token_id", None)
    return tokens


async def revoke_token_family(family_id: UUID) -> None:
    now = datetime.now(UTC)
    tokens = await RefreshToken.find(
        {"family_id": family_id}
    ).to_list()
    for token in tokens:
        if token.revoked_at is None:
            token.revoked_at = now
    if tokens:
        for token in tokens:
            await token.save()


async def refresh_session(
    raw_refresh_token: str, settings: Settings
) -> dict[str, str]:
    token_hash = hash_refresh_token(raw_refresh_token)
    refresh_token = await RefreshToken.find_one(
        {"token_hash": token_hash}
    )
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    now = datetime.now(UTC)
    if refresh_token.revoked_at is not None:
        await revoke_token_family(refresh_token.family_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    if as_utc(refresh_token.expires_at) <= now:
        refresh_token.revoked_at = now
        await refresh_token.save()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    user = await User.find_one({"_id": refresh_token.user_id})
    if user is None or not user.is_active:
        await revoke_token_family(refresh_token.family_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    refresh_token.revoked_at = now
    await refresh_token.save()
    tokens = await issue_token_pair(
        user, settings, family_id=refresh_token.family_id
    )
    refresh_token.replaced_by_token_id = UUID(tokens["_refresh_token_id"])
    await refresh_token.save()
    tokens.pop("_refresh_token_id", None)
    return tokens


async def logout_session(raw_refresh_token: str) -> None:
    token_hash = hash_refresh_token(raw_refresh_token)
    refresh_token = await RefreshToken.find_one(
        {"token_hash": token_hash}
    )
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    await revoke_token_family(refresh_token.family_id)
