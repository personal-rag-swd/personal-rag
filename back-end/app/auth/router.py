from typing import Annotated, Literal, cast

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.exceptions import RefreshTokenCookieMissingError
from app.auth.schemas import (
    EmailVerificationCreate,
    PasswordResetCreate,
    PasswordResetVerify,
    RegistrationCreate,
    TokenResponse,
    VerificationResponse,
)
from app.auth.service import (
    complete_password_reset,
    create_session,
    logout_session,
    refresh_session,
    request_password_reset,
    start_registration,
    verify_registration_otp,
)
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
ACCESS_TOKEN_COOKIE_NAME = "access_token"
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"


def is_cookie_secure(request: Request, settings: Settings) -> bool:
    if settings.cookie_secure is not None:
        return settings.cookie_secure
    return request.url.hostname not in ("localhost", "127.0.0.1", "testserver")


def get_cookie_samesite(settings: Settings) -> Literal["lax", "strict", "none"]:
    value = settings.cookie_samesite.lower()
    if value in {"lax", "strict", "none"}:
        return cast(Literal["lax", "strict", "none"], value)
    return "lax"


def set_session_cookies(
    response: Response,
    request: Request,
    tokens: dict[str, str],
    settings: Settings,
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
    response: Response, request: Request, settings: Settings
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


@router.post(
    "/registrations", status_code=status.HTTP_202_ACCEPTED, response_class=Response
)
async def create_registration(
    body: RegistrationCreate,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    await start_registration(body.email, body.password, settings)
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/email-verifications", response_model=VerificationResponse)
async def create_email_verification(
    body: EmailVerificationCreate,
    settings: Annotated[Settings, Depends(get_settings)],
) -> VerificationResponse:
    await verify_registration_otp(body.email, body.otp, settings)
    return VerificationResponse(success=True)


@router.post("/sessions", response_model=TokenResponse)
async def create_auth_session(
    request: Request,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    tokens = await create_session(form_data.username, form_data.password, settings)
    set_session_cookies(response, request, tokens, settings)
    return tokens


@router.post("/token-refreshes", response_model=TokenResponse)
async def create_token_refresh(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> dict[str, str]:
    if not refresh_token:
        raise RefreshTokenCookieMissingError()
    tokens = await refresh_session(refresh_token, settings)
    set_session_cookies(response, request, tokens, settings)
    return tokens


@router.post(
    "/password-resets", status_code=status.HTTP_202_ACCEPTED, response_class=Response
)
async def create_password_reset(
    body: PasswordResetCreate,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    await request_password_reset(body.email, settings)
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/password-resets/verify", response_model=VerificationResponse)
async def verify_password_reset(
    body: PasswordResetVerify,
    settings: Annotated[Settings, Depends(get_settings)],
) -> VerificationResponse:
    await complete_password_reset(body.email, body.otp, body.new_password, settings)
    return VerificationResponse(success=True)


@router.delete(
    "/sessions/current", status_code=status.HTTP_204_NO_CONTENT, response_class=Response
)
async def delete_current_session(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Response:
    if refresh_token:
        await logout_session(refresh_token)
    clear_session_cookies(response, request, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
