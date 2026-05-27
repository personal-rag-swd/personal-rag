from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.dependencies import get_session
from app.users.dependencies import get_current_user, require_role
from app.users.models import User
from app.users.schemas import UserRead

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.get("/", response_model=list[UserRead])
def read_users(
    _: Annotated[None, Depends(require_role("admin"))],
    session: Annotated[Session, Depends(get_session)],
) -> list[User]:
    return list(session.exec(select(User)).all())
