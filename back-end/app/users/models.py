from datetime import UTC, datetime
from uuid import UUID, uuid4

from beanie import Document
from pydantic import Field


class User(Document):
    id: UUID = Field(default_factory=uuid4)
    email: str
    hashed_password: str
    role: str = "user"
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "users"
        use_state_management = True
        indexes = [
            [("email", 1)],
        ]
