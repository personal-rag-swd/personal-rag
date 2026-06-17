import logging
import uuid
from pathlib import Path

from botocore.exceptions import ClientError
from fastapi import HTTPException, status

from app.core.config import Settings
from app.core.s3 import get_s3_client
from app.file.schemas import PresignedUrlRequest, PresignedUrlResponse
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Operation must be either 'upload' or 'download'",
        )

    if ".." in request.filename or "\\" in request.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid characters or directory traversal detected",
        )

    if operation == "upload":
        cleaned_name = sanitize_filename(request.filename)
        if not cleaned_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename cannot be empty after sanitization",
            )
        unique_id = str(uuid.uuid4())
        s3_key = f"users/{current_user.id}/{unique_id}/{cleaned_name}"
    else:
        expected_prefix = f"users/{current_user.id}/"
        if not request.filename.startswith(expected_prefix):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have access to this resource",
            )
        s3_key = request.filename

    try:
        presign_endpoint = settings.s3_public_endpoint_url or settings.s3_endpoint_url
        s3_client = get_s3_client(settings, endpoint_url=presign_endpoint)
        if operation == "upload":
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
            presigned_url = s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": settings.s3_bucket, "Key": s3_key},
                ExpiresIn=request.expires_in,
                HttpMethod="GET",
            )
    except ClientError as exc:
        logger.exception("Failed to generate S3 presigned URL")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate presigned URL",
        ) from exc

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
