from pydantic import BaseModel, Field
from uuid import UUID


class PresignedUrlRequest(BaseModel):
    filename: str = Field(
        ...,
        description="For upload, the name of the file. For download, the full S3 object key.",
        min_length=1,
        max_length=1024,
    )
    operation: str = Field("upload", description="The S3 operation to perform: 'upload' or 'download'")
    content_type: str | None = Field(None, description="The content type of the file (e.g. application/pdf) for uploads")
    notebook_id: UUID | None = Field(None, description="Notebook id for notebook-scoped upload ingestion")
    expires_in: int = Field(3600, ge=60, le=3600, description="URL expiration time in seconds (60 to 3600)")


class PresignedUrlResponse(BaseModel):
    url: str
    key: str


class UploadFailedRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=2048)
    notebook_id: UUID | None = None
    error_message: str | None = Field(None, max_length=4000)


class S3Bucket(BaseModel):
    name: str | None = None


class S3Object(BaseModel):
    key: str | None = None
    size: int | None = None


class S3Data(BaseModel):
    bucket: S3Bucket | None = None
    object: S3Object | None = None


class S3Record(BaseModel):
    eventName: str | None = None
    s3: S3Data | None = None


class FileCallbackPayload(BaseModel):
    Records: list[S3Record] | None = None

    # Fallbacks (for flat/custom callback styles, checking both standard casings)
    key: str | None = None
    Key: str | None = None
    object_key: str | None = None

    bucket: str | None = None
    Bucket: str | None = None
    bucket_name: str | None = None

    size: int | None = None
    Size: int | None = None
    file_size: int | None = None

    eventName: str | None = None
    EventName: str | None = None
    event: str | None = None
    type: str | None = None

    model_config = {
        "extra": "ignore",
    }

    def get_parsed_details(self) -> tuple[str | None, str | None, int | None, str | None]:
        """Extracts eventName, bucket, key, and size, resolving nested vs. flat fallbacks."""
        ev_name = None
        b_name = None
        k_name = None
        s_val = None

        if self.Records:
            record = self.Records[0]
            ev_name = record.eventName
            if record.s3:
                if record.s3.bucket:
                    b_name = record.s3.bucket.name
                if record.s3.object:
                    k_name = record.s3.object.key
                    s_val = record.s3.object.size

        # Fallbacks
        ev_name = ev_name or self.eventName or self.EventName or self.event or self.type
        b_name = b_name or self.bucket or self.Bucket or self.bucket_name
        k_name = k_name or self.key or self.Key or self.object_key
        s_val = s_val if s_val is not None else (self.size or self.Size or self.file_size)

        return ev_name, b_name, k_name, s_val
