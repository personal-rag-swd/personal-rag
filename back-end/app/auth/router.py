from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
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
    RefreshTokenCreate,
    TokenPair,
    VerificationResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


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


@router.post("/sessions", response_model=TokenPair)
def create_auth_session(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    return create_session(session, form_data.username, form_data.password, settings)


@router.post("/token-refreshes", response_model=TokenPair)
def create_token_refresh(
    body: RefreshTokenCreate,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    return refresh_session(session, body.refresh_token, settings)


@router.delete("/sessions/current", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_current_session(
    body: RefreshTokenCreate,
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    logout_session(session, body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
