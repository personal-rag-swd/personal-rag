import os
import uuid
import logging
from typing import Annotated

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from fastapi import HTTPException, status

from app.core.config import Settings
from app.users.models import User
from app.file.schemas import PresignedUrlRequest, PresignedUrlResponse

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    """Strips path traversal components and returns the clean file basename."""
    # Extract basename to strip out path traversal sequences (../ or ..\)
    base = os.path.basename(filename)
    # Remove any remaining slash/backslash just in case
    base = base.replace("/", "").replace("\\", "")
    return base


def get_s3_client(settings: Settings):
    s3_config = Config(
        signature_version="s3v4",
        retries={"max_attempts": 3}
    )
    client_kwargs = {
        "service_name": "s3",
        "region_name": settings.s3_region,
        "config": s3_config,
    }
    if settings.aws_access_key_id:
        client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
    if settings.aws_secret_access_key:
        client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    if settings.s3_endpoint_url:
        client_kwargs["endpoint_url"] = settings.s3_endpoint_url
        
    return boto3.client(**client_kwargs)


def generate_presigned_url_service(
    request: PresignedUrlRequest,
    current_user: User,
    settings: Settings,
) -> PresignedUrlResponse:
    # 1. Enforce validation of operation type
    operation = request.operation.lower()
    if operation not in ("upload", "download"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Operation must be either 'upload' or 'download'"
        )

    # 2. Defend against directory traversal attacks in the request filename
    if ".." in request.filename or "\\" in request.filename:
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail="Invalid characters or directory traversal detected"
         )

    # 3. Handle key generation and strict owner authorization
    if operation == "upload":
        cleaned_name = sanitize_filename(request.filename)
        if not cleaned_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename cannot be empty after sanitization"
            )
        
        # User isolation using user ID and unique UUID to avoid collisions
        unique_id = str(uuid.uuid4())
        s3_key = f"users/{current_user.id}/{unique_id}/{cleaned_name}"
    else:  # download
        # Enforce that downloading user must own the S3 path prefix
        expected_prefix = f"users/{current_user.id}/"
        if not request.filename.startswith(expected_prefix):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You do not have access to this resource"
            )
        s3_key = request.filename

    # 4. Generate the S3 presigned URL
    try:
        s3_client = get_s3_client(settings)
        if operation == "upload":
            params = {
                "Bucket": settings.s3_bucket,
                "Key": s3_key,
            }
            if request.content_type:
                params["ContentType"] = request.content_type
            
            presigned_url = s3_client.generate_presigned_url(
                ClientMethod="put_object",
                Params=params,
                ExpiresIn=request.expires_in,
                HttpMethod="PUT",
            )
        else:  # download
            presigned_url = s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": settings.s3_bucket,
                    "Key": s3_key,
                },
                ExpiresIn=request.expires_in,
                HttpMethod="GET",
            )
            
    except ClientError as exc:
        # TODO(security): Log full error details in diagnostic log, but fail-close with generic message
        logger.error("Failed to generate S3 presigned URL: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate presigned URL"
        )

    return PresignedUrlResponse(url=presigned_url, key=s3_key)
