from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        value = tag.strip()
        key = value.lower()
        if value and key not in seen:
            normalized.append(value)
            seen.add(key)
    return normalized


class NotebookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        tags = normalize_tags(value)
        if any(len(tag) > 40 for tag in tags):
            raise ValueError("Tags must be 40 characters or fewer")
        return tags


class NotebookUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    tags: list[str] | None = Field(default=None, max_length=20)

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @field_validator("tags")
    @classmethod
    def validate_optional_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        tags = normalize_tags(value)
        if any(len(tag) > 40 for tag in tags):
            raise ValueError("Tags must be 40 characters or fewer")
        return tags


class NotebookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    last_active_at: datetime
    document_count: int = 0
    query_count: int = 0


class NotebookChatHistoryPart(BaseModel):
    type: str
    content: str


class NotebookChatHistoryMessage(BaseModel):
    role: str
    parts: list[NotebookChatHistoryPart]
