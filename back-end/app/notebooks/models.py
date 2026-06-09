from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel

chat_history_type = JSON()


class Notebook(SQLModel, table=True):
    __tablename__ = "notebook"  # type: ignore

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(
        sa_column=Column(
            ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
        ),
    )
    name: str = Field(max_length=120, nullable=False)
    description: str = Field(default="", max_length=1000, nullable=False)
    tags: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    last_active_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class NotebookMessage(SQLModel, table=True):
    __tablename__ = "notebook_message"  # type: ignore
    __table_args__ = (
        UniqueConstraint(
            "notebook_id", "seq", name="uq_notebook_message_notebook_id_seq"
        ),
        Index("ix_notebook_message_notebook_id_seq", "notebook_id", "seq"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    notebook_id: UUID = Field(
        sa_column=Column(
            ForeignKey("notebook.id", ondelete="CASCADE"), nullable=False, index=True
        ),
    )
    seq: int = Field(nullable=False)
    message: dict[str, Any] = Field(sa_column=Column(chat_history_type, nullable=False))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


document_status_type = String(24)


class NotebookDocument(SQLModel, table=True):
    __tablename__ = "notebook_document"  # type: ignore
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'uploaded', 'processing', 'indexed', 'failed')",
            name="ck_notebook_document_status_valid",
        ),
        Index(
            "ix_notebook_document_notebook_user_created_at",
            "notebook_id",
            "user_id",
            "created_at",
        ),
        Index(
            "ix_notebook_document_notebook_user_filename",
            "notebook_id",
            "user_id",
            "filename",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    notebook_id: UUID = Field(
        sa_column=Column(
            ForeignKey("notebook.id", ondelete="CASCADE"), nullable=False, index=True
        ),
    )
    user_id: UUID = Field(
        sa_column=Column(
            ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
        ),
    )
    s3_bucket: str = Field(max_length=255, nullable=False)
    s3_key: str = Field(sa_column=Column(String(1024), nullable=False, unique=True))
    filename: str = Field(max_length=255, nullable=False)
    content_type: str | None = Field(default=None, max_length=255)
    size: int | None = Field(default=None)
    status: str = Field(
        default="pending",
        sa_column=Column(document_status_type, nullable=False, index=True),
    )
    error_message: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


report_content_type = JSON()

report_status_type = String(16)


class NotebookReport(SQLModel, table=True):
    __tablename__ = "notebook_report"  # type: ignore
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'generating', 'completed', 'failed', 'cancelled')",
            name="ck_notebook_report_status_valid",
        ),
        Index("ix_notebook_report_notebook_id", "notebook_id"),
        Index("ix_notebook_report_user_id", "user_id"),
        Index(
            "ix_notebook_report_notebook_user_created_at",
            "notebook_id",
            "user_id",
            "created_at",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    notebook_id: UUID = Field(
        sa_column=Column(ForeignKey("notebook.id", ondelete="CASCADE"), nullable=False),
    )
    user_id: UUID = Field(
        sa_column=Column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
    )
    report_type: str = Field(sa_column=Column(String(32), nullable=False))
    status: str = Field(
        default="pending", sa_column=Column(report_status_type, nullable=False)
    )
    error_message: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    additional_instructions: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    detail_level: str | None = Field(
        default=None, sa_column=Column(String(16), nullable=True)
    )
    content: dict[str, Any] = Field(
        sa_column=Column(report_content_type, nullable=False)
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


def _embedding_column() -> Column:
    return Column(Vector(1536), nullable=False)


class NotebookDocumentChunk(SQLModel, table=True):
    __tablename__ = "notebook_document_chunk"  # type: ignore

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    document_id: UUID = Field(
        sa_column=Column(
            ForeignKey("notebook_document.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    chunk_index: int = Field(nullable=False)
    content: str = Field(sa_column=Column(Text, nullable=False))
    chunk_metadata: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON, nullable=False),
    )
    embedding: list[float] = Field(sa_column=_embedding_column())
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
