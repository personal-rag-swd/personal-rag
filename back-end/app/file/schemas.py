from uuid import UUID

from pydantic import BaseModel, Field


class PresignedUrlRequest(BaseModel):
    filename: str = Field(
        ...,
        description="For upload, the name of the file. For download, the full S3 object key.",
        min_length=1,
        max_length=1024,
    )
    operation: str = Field(
        "upload", description="The S3 operation to perform: 'upload' or 'download'"
    )
    content_type: str | None = Field(
        None,
        description="The content type of the file (e.g. application/pdf) for uploads",
    )
    notebook_id: UUID | None = Field(
        None, description="Notebook id for notebook-scoped upload ingestion"
    )
    expires_in: int = Field(
        3600, ge=60, le=3600, description="URL expiration time in seconds (60 to 3600)"
    )


class PresignedUrlResponse(BaseModel):
    url: str
    key: str


class UploadFailedRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=2048)
    notebook_id: UUID | None = None
    error_message: str | None = Field(None, max_length=4000)
