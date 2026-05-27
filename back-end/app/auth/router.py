from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from app.core.config import Settings
from app.dependencies import get_session, get_settings
from app.auth.service import (
    create_session,
    logout_session,
    refresh_session,
    start_registration,
    verify_registration_otp,
)
from app.auth.schemas import (
    RegistrationCreate,
    EmailVerificationCreate,
    TokenResponse,
    VerificationResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
ACCESS_TOKEN_COOKIE_NAME = "access_token"
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"


def is_cookie_secure(request: Request) -> bool:
    if request.url.hostname in ("localhost", "127.0.0.1", "testserver"):
        return False
    return True


def set_session_cookies(
    response: Response,
    request: Request,
    tokens: dict[str, str],
    settings: Settings,
) -> None:
    cookie_secure = is_cookie_secure(request)
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=tokens["access_token"],
        httponly=True,
        secure=cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=tokens["refresh_token"],
        httponly=True,
        secure=cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )


def clear_session_cookies(response: Response, request: Request) -> None:
    cookie_secure = is_cookie_secure(request)
    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=cookie_secure,
        samesite="lax",
    )
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=cookie_secure,
        samesite="lax",
    )


@router.post("/registrations", status_code=status.HTTP_202_ACCEPTED, response_class=Response)
def create_registration(
    body: RegistrationCreate,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    start_registration(session, str(body.email), body.password, settings)
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/email-verifications", response_model=VerificationResponse)
def create_email_verification(
    body: EmailVerificationCreate,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> VerificationResponse:
    verify_registration_otp(session, str(body.email), body.otp, settings)
    return VerificationResponse(success=True)


@router.post("/sessions", response_model=TokenResponse)
def create_auth_session(
    request: Request,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    tokens = create_session(session, form_data.username, form_data.password, settings)
    set_session_cookies(response, request, tokens, settings)
    return tokens


@router.post("/token-refreshes", response_model=TokenResponse)
def create_token_refresh(
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> dict[str, str]:
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token cookie missing",
        )
    tokens = refresh_session(session, refresh_token, settings)
    set_session_cookies(response, request, tokens, settings)
    return tokens


@router.delete("/sessions/current", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_current_session(
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Response:
    if refresh_token:
        logout_session(session, refresh_token)
    clear_session_cookies(response, request)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
