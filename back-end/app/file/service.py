import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from botocore.exceptions import ClientError

from app.core.config import Settings
from app.core.s3 import (
    generate_presigned_get_url,
    get_s3_client,
    presign_endpoint_url,
)
from app.file.exceptions import (
    EmptyFilenameError,
    ForbiddenResourceError,
    InvalidFilenameCharactersError,
    InvalidOperationError,
    PresignedUrlGenerationFailedError,
)
from app.file.schemas import (
    PresignedUrlRequest,
    PresignedUrlResponse,
    UploadFailedRequest,
)
from app.notebooks.models import NotebookDocument
from app.users.models import User

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    base = Path(filename).name
    return base.replace("/", "").replace("\\", "")


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
        unique_id = str(uuid.uuid4())
        s3_key = f"users/{current_user.id}/{unique_id}/{cleaned_name}"
    else:
        expected_prefix = f"users/{current_user.id}/"
        if not request.filename.startswith(expected_prefix):
            raise ForbiddenResourceError()
        s3_key = request.filename

    try:
        if operation == "upload":
            s3_client = get_s3_client(
                settings, endpoint_url=presign_endpoint_url(settings)
            )
            params: dict = {"Bucket": settings.s3_bucket, "Key": s3_key}
            if request.content_type:
                params["ContentType"] = request.content_type
            presigned_url = s3_client.generate_presigned_url(
                ClientMethod="put_object",
                Params=params,
                ExpiresIn=request.expires_in,
                HttpMethod="PUT",
            )
        else:
            presigned_url = generate_presigned_get_url(
                settings,
                bucket=settings.s3_bucket,
                key=s3_key,
                expires_in=request.expires_in,
            )
    except ClientError as exc:
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
    return {"status": "ok", "updated": True}
