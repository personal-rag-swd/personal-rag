import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import obstore
import obstore.exceptions

from app.core.config import Settings
from app.core.event_bus import domain_event_bus
from app.core.s3 import (
    _build_s3_store,
    generate_presigned_get_url,
    presign_endpoint_url,
)
from app.file.exceptions import (
    EmptyFilenameError,
    ForbiddenResourceError,
    InvalidFilenameCharactersError,
    InvalidOperationError,
    PresignedUrlGenerationFailedError,
    UnsupportedNotebookSourceContentTypeError,
)
from app.file.schemas import (
    PresignedUrlRequest,
    PresignedUrlResponse,
    UploadFailedRequest,
)
from app.notebooks.domain_events import DocumentFailed
from app.notebooks.models import NotebookDocument
from app.users.models import User

logger = logging.getLogger(__name__)

SAFE_NOTEBOOK_UPLOAD_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
}


def sanitize_filename(filename: str) -> str:
    base = Path(filename).name
    return base.replace("/", "").replace("\\", "")


def normalize_content_type(content_type: str | None) -> str:
    return (content_type or "").split(";", maxsplit=1)[0].strip().lower()


async def generate_presigned_url_service(
    request: PresignedUrlRequest,
    current_user: User,
    settings: Settings,
) -> PresignedUrlResponse:
    operation = request.operation.lower()
    if operation not in ("upload", "download"):
        raise InvalidOperationError()

    if ".." in request.filename or "\\" in request.filename:
        raise InvalidFilenameCharactersError()

    cleaned_name = ""
    if operation == "upload":
        cleaned_name = sanitize_filename(request.filename)
        if not cleaned_name:
            raise EmptyFilenameError()
        if request.notebook_id is not None:
            content_type = normalize_content_type(request.content_type)
            if content_type and content_type not in SAFE_NOTEBOOK_UPLOAD_CONTENT_TYPES:
                raise UnsupportedNotebookSourceContentTypeError()
        unique_id = str(uuid.uuid4())
        s3_key = f"users/{current_user.id}/{unique_id}/{cleaned_name}"
    else:
        expected_prefix = f"users/{current_user.id}/"
        if not request.filename.startswith(expected_prefix):
            raise ForbiddenResourceError()
        s3_key = request.filename

    try:
        if operation == "upload":
            store = _build_s3_store(
                settings, endpoint_url=presign_endpoint_url(settings)
            )
            presigned_url = obstore.sign(
                store,
                "PUT",
                s3_key,
                timedelta(seconds=request.expires_in),
            )
        else:
            presigned_url = generate_presigned_get_url(
                settings,
                key=s3_key,
                expires_in=request.expires_in,
            )
    except obstore.exceptions.BaseError as exc:
        logger.exception("Failed to generate S3 presigned URL")
        raise PresignedUrlGenerationFailedError() from exc

    if operation == "upload" and request.notebook_id is not None:
        document = NotebookDocument(
            notebook_id=request.notebook_id,
            user_id=current_user.id,
            s3_bucket=settings.s3_bucket,
            s3_key=s3_key,
            filename=cleaned_name,
            content_type=request.content_type,
            status="pending",
        )
        await document.insert()

    return PresignedUrlResponse(url=presigned_url, key=s3_key)


async def mark_upload_failed(
    request: UploadFailedRequest, user_id: UUID
) -> dict[str, object]:
    document = await NotebookDocument.find_one(
        {"s3_key": request.key, "user_id": user_id},
    )
    if document is None:
        return {"status": "ok", "updated": False}
    if document.status in {"indexed", "processing", "uploaded"}:
        return {"status": "ok", "updated": True}
    document.status = "failed"
    document.error_message = (
        request.error_message
        or "Upload failed before object storage accepted the file."
    )[:4000]
    document.updated_at = datetime.now(UTC)
    await document.save()
    await domain_event_bus.emit(DocumentFailed(document))
    return {"status": "ok", "updated": True}
