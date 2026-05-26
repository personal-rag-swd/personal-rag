from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from app.auth.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    is_active: bool


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user
