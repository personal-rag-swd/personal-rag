from datetime import UTC, datetime
from uuid import UUID, uuid4

from beanie import Document
from pydantic import Field


class PendingRegistration(Document):
    id: UUID = Field(default_factory=uuid4)
    email: str
    hashed_password: str
    hashed_otp: str
    otp_attempts: int = 0
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "pending_registrations"
        use_state_management = True
        indexes = [
            [("email", 1)],
        ]


class RefreshToken(Document):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    token_hash: str
    family_id: UUID
    expires_at: datetime
    revoked_at: datetime | None = None
    replaced_by_token_id: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "refresh_tokens"
        use_state_management = True
        indexes = [
            [("token_hash", 1)],
            [("family_id", 1)],
        ]
