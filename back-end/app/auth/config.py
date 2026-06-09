from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class AuthSettings:
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    otp_expire_minutes: int
    otp_max_attempts: int
    resend_api_key: str
    resend_from_email: str
    cookie_secure: bool | None
    cookie_samesite: str


def build_auth_settings(settings: Settings) -> AuthSettings:
    return AuthSettings(
        jwt_secret_key=settings.jwt_secret_key,
        jwt_algorithm=settings.jwt_algorithm,
        access_token_expire_minutes=settings.access_token_expire_minutes,
        refresh_token_expire_days=settings.refresh_token_expire_days,
        otp_expire_minutes=settings.otp_expire_minutes,
        otp_max_attempts=settings.otp_max_attempts,
        resend_api_key=settings.resend_api_key,
        resend_from_email=settings.resend_from_email,
        cookie_secure=settings.cookie_secure,
        cookie_samesite=settings.cookie_samesite,
    )


def get_auth_settings(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthSettings:
    return build_auth_settings(settings)
