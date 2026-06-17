from typing import Annotated

from fastapi import APIRouter, Depends

from app.users.dependencies import get_current_user, require_role
from app.users.models import User
from app.users.schemas import UserRead

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.get("/", response_model=list[UserRead])
async def read_users(
    _: Annotated[None, Depends(require_role("admin"))],
) -> list[User]:
    return await User.find_all().to_list()
