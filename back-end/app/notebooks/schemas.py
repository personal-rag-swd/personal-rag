from datetime import datetime
from typing import Any, Literal
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


class NotebookPopulateRead(NotebookRead):
    document_count: int = 0
    query_count: int = 0


class NotebookDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    notebook_id: UUID
    filename: str
    content_type: str | None
    size: int | None
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class NotebookChatHistoryPart(BaseModel):
    type: str
    content: str | None = None
    toolCallId: str | None = None
    toolName: str | None = None
    argsText: str | None = None
    result: Any | None = None


class NotebookChatSource(BaseModel):
    filename: str
    document_id: UUID
    chunk_index: int
    content: str


class NotebookChatReference(BaseModel):
    ref_id: str
    citation_number: int
    filename: str
    document_id: UUID
    chunk_index: int
    content: str


class NotebookChatHistoryMessage(BaseModel):
    role: str
    parts: list[NotebookChatHistoryPart]
    sources: list[NotebookChatSource] = Field(default_factory=list)
    references: list[NotebookChatReference] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Report structured-output schemas (returned by the LLM via pydantic-ai)
# ---------------------------------------------------------------------------


class GlossaryEntry(BaseModel):
    term: str
    definition: str


class QuizItem(BaseModel):
    question: str
    options: list[str]
    answer: str
    explanation: str


class BriefingDocReport(BaseModel):
    executive_summary: str
    key_takeaways: list[str]
    strategic_implications: list[str]


class StudyGuideReport(BaseModel):
    glossary: list[GlossaryEntry]
    quiz: list[QuizItem]


class BlogPostReport(BaseModel):
    title: str
    hook: str
    markdown_body: str


class CustomReport(BaseModel):
    markdown_content: str


class MindMapNode(BaseModel):
    id: str = Field(description="Unique node identifier, e.g. 'root', 'm1', 's1_1'")
    label: str = Field(description="Short text label of the concept")
    type: Literal["root", "main", "sub"] = Field(description="Branch level hierarchy")
    parent_id: str | None = Field(
        default=None, description="Parent node ID or null for central topic"
    )
    description: str | None = Field(
        default=None, description="Detailed explanation/definition of the concept"
    )


class MindMapRelationship(BaseModel):
    source: str = Field(description="Source node ID")
    target: str = Field(description="Target node ID")
    label: str = Field(
        description="Description of concept relationship, e.g., 'prerequisite of'"
    )


class MindMapReport(BaseModel):
    central_topic: str = Field(description="Central theme of the documents")
    nodes: list[MindMapNode] = Field(description="Tree structure nodes")
    relationships: list[MindMapRelationship] = Field(
        default_factory=list, description="Cross-connections"
    )


# ---------------------------------------------------------------------------
# Report API schemas
# ---------------------------------------------------------------------------

ReportType = Literal["briefing", "study_guide", "blog", "custom", "mindmap"]


class ReportGenerateRequest(BaseModel):
    report_type: ReportType
    additional_instructions: str | None = Field(default=None, max_length=2000)
    detail_level: str | None = Field(default=None, max_length=20)


class NotebookReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    notebook_id: UUID
    report_type: str
    status: str
    error_message: str | None = None
    additional_instructions: str | None = None
    detail_level: str | None = None
    content: dict[str, Any]
    created_at: datetime
    updated_at: datetime
