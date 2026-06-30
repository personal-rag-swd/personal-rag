from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4

from beanie import Document
from pydantic import Field


class Notebook(Document):
    id: UUID = Field(default_factory=uuid4)  # type: ignore
    user_id: UUID
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_active_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "notebooks"
        use_state_management = True
        indexes: ClassVar[list[list[tuple[str, int]]]] = [
            [("user_id", 1)],
        ]


class NotebookMessage(Document):
    id: UUID = Field(default_factory=uuid4)  # type: ignore
    notebook_id: UUID
    seq: int
    message: dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "notebook_messages"
        use_state_management = True
        indexes: ClassVar[list[list[tuple[str, int]]]] = [
            [("notebook_id", 1)],
        ]


class NotebookDocument(Document):
    id: UUID = Field(default_factory=uuid4)  # type: ignore
    notebook_id: UUID
    user_id: UUID
    s3_bucket: str | None = None
    s3_key: str | None = None
    content: str | None = None
    filename: str
    content_type: str | None = None
    size: int | None = None
    status: str = "pending"
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "notebook_documents"
        use_state_management = True
        indexes: ClassVar[list[list[tuple[str, int]]]] = [
            [("notebook_id", 1), ("user_id", 1), ("created_at", -1)],
            [("notebook_id", 1), ("user_id", 1), ("filename", 1)],
            [("status", 1)],
            [("s3_key", 1)],
        ]


class NotebookDocumentChunk(Document):
    id: UUID = Field(default_factory=uuid4)  # type: ignore
    document_id: UUID
    notebook_id: UUID
    user_id: UUID
    chunk_index: int
    content: str
    embedding: list[float] = Field(default_factory=list)
    chunk_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "notebook_document_chunks"
        use_state_management = True
        indexes: ClassVar[list[list[tuple[str, int]]]] = [
            [("document_id", 1)],
            [("notebook_id", 1)],
            [("user_id", 1)],
        ]


class NotebookReport(Document):
    id: UUID = Field(default_factory=uuid4)  # type: ignore
    notebook_id: UUID
    user_id: UUID
    report_type: str
    status: str = "pending"
    error_message: str | None = None
    additional_instructions: str | None = None
    detail_level: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "notebook_reports"
        use_state_management = True
        indexes: ClassVar[list[list[tuple[str, int]]]] = [
            [("notebook_id", 1)],
            [("user_id", 1)],
            [("notebook_id", 1), ("user_id", 1), ("created_at", -1)],
        ]
