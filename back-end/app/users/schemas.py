from uuid import UUID
from pydantic import BaseModel, EmailStr

class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    is_active: bool
