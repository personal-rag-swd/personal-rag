from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlmodel import Field, SQLModel


class PendingRegistration(SQLModel, table=True):
    __tablename__ = "pending_registration" # type: ignore
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=320)
    hashed_password: str
    hashed_otp: str
    otp_attempts: int = Field(default=0)
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_token" # type: ignore
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(
        sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True),
    )
    token_hash: str = Field(sa_column=Column(String(length=64), nullable=False, unique=True, index=True))
    family_id: UUID = Field(default_factory=uuid4, index=True, nullable=False)
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    revoked_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    replaced_by_token_id: UUID | None = Field(default=None, foreign_key="refresh_token.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
