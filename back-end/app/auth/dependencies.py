from __future__ import annotations

from fastapi import Request, Response

from app.auth.config import AuthSettings

ACCESS_TOKEN_COOKIE_NAME = "access_token"
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"


def is_cookie_secure(request: Request, settings: AuthSettings) -> bool:
    if settings.cookie_secure is not None:
        return settings.cookie_secure
    return request.url.hostname not in ("localhost", "127.0.0.1", "testserver")


def get_cookie_samesite(settings: AuthSettings) -> str:
    value = settings.cookie_samesite.lower()
    if value in {"lax", "strict", "none"}:
        return value
    return "lax"


def set_session_cookies(
    response: Response,
    request: Request,
    tokens: dict[str, str],
    settings: AuthSettings,
) -> None:
    cookie_secure = is_cookie_secure(request, settings)
    cookie_samesite = get_cookie_samesite(settings)
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=tokens["access_token"],
        httponly=True,
        secure=cookie_secure,
        samesite=cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=tokens["refresh_token"],
        httponly=True,
        secure=cookie_secure,
        samesite=cookie_samesite,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )


def clear_session_cookies(
    response: Response, request: Request, settings: AuthSettings
) -> None:
    cookie_secure = is_cookie_secure(request, settings)
    cookie_samesite = get_cookie_samesite(settings)
    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=cookie_secure,
        samesite=cookie_samesite,
    )
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=cookie_secure,
        samesite=cookie_samesite,
    )
