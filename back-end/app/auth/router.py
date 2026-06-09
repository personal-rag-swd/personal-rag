from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from app.auth.config import AuthSettings, get_auth_settings
from app.auth.dependencies import clear_session_cookies, set_session_cookies
from app.auth.schemas import (
    EmailVerificationCreate,
    RegistrationCreate,
    TokenResponse,
    VerificationResponse,
)
from app.auth.service import (
    create_session,
    logout_session,
    refresh_session,
    start_registration,
    verify_registration_otp,
)
from app.core.database import get_session

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/registrations", status_code=status.HTTP_202_ACCEPTED, response_class=Response
)
def create_registration(
    body: RegistrationCreate,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[AuthSettings, Depends(get_auth_settings)],
) -> Response:
    start_registration(session, str(body.email), body.password, settings)
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/email-verifications", response_model=VerificationResponse)
def create_email_verification(
    body: EmailVerificationCreate,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[AuthSettings, Depends(get_auth_settings)],
) -> VerificationResponse:
    verify_registration_otp(session, str(body.email), body.otp, settings)
    return VerificationResponse(success=True)


@router.post("/sessions", response_model=TokenResponse)
def create_auth_session(
    request: Request,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[AuthSettings, Depends(get_auth_settings)],
) -> dict[str, str]:
    tokens = create_session(session, form_data.username, form_data.password, settings)
    set_session_cookies(response, request, tokens, settings)
    return tokens


@router.post("/token-refreshes", response_model=TokenResponse)
def create_token_refresh(
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[AuthSettings, Depends(get_auth_settings)],
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


@router.delete(
    "/sessions/current", status_code=status.HTTP_204_NO_CONTENT, response_class=Response
)
def delete_current_session(
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[AuthSettings, Depends(get_auth_settings)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Response:
    if refresh_token:
        logout_session(session, refresh_token)
    clear_session_cookies(response, request, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
