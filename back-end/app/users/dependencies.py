from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.core.exceptions import CouldNotValidateCredentialsError
from app.core.security import decode_access_token
from app.users.exceptions import ForbiddenError
from app.users.models import User


def get_access_token(request: Request) -> str | None:
    authorization = request.headers.get("Authorization")
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            return token

    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token

    return None


async def get_current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    token = get_access_token(request)
    if token is None:
        raise CouldNotValidateCredentialsError()

    payload = decode_access_token(token, settings)
    subject = payload.get("sub")
    try:
        user_id = UUID(str(subject))
    except (TypeError, ValueError) as exc:
        raise CouldNotValidateCredentialsError() from exc

    user = await User.find_one({"_id": user_id})
    if user is None or not user.is_active:
        raise CouldNotValidateCredentialsError()
    return user


def require_role(required_role: str) -> Callable[..., None]:
    def dependency(
        request: Request,
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> None:
        token = get_access_token(request)
        if token is None:
            raise CouldNotValidateCredentialsError()
        payload = decode_access_token(token, settings)
        if payload.get("role") != required_role:
            raise ForbiddenError()

    return dependency
