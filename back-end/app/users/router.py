from typing import Annotated

from fastapi import APIRouter, Depends

from app.users.dependencies import get_current_user
from app.users.models import User
from app.users.schemas import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)

def read_current_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user
