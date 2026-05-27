import os
import uuid
import logging
import urllib.parse
from typing import Any

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from fastapi import HTTPException, status

from app.core.config import Settings
from app.users.models import User
from app.file.schemas import PresignedUrlRequest, PresignedUrlResponse, FileCallbackPayload

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    """Strips path traversal components and returns the clean file basename."""
    base = os.path.basename(filename)
    base = base.replace("/", "").replace("\\", "")
    return base


def get_s3_client(settings: Settings):
    s3_config = Config(
        signature_version="s3v4",
        retries={"max_attempts": 3},
    )
    client_kwargs: dict = {
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
        s3_client = get_s3_client(settings)
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
        logger.error("Failed to generate S3 presigned URL: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate presigned URL",
        )

    return PresignedUrlResponse(url=presigned_url, key=s3_key)


_SENSITIVE_HEADERS = {"authorization", "cookie", "proxy-authorization", "x-api-key"}


def handle_file_callback_service(
    payload: FileCallbackPayload,
    headers: dict[str, str],
    query_params: dict[str, str],
) -> dict[str, Any]:
    """Processes an incoming RustFS/S3 webhook callback and returns parsed event details."""
    safe_headers = {k: v for k, v in headers.items() if k.lower() not in _SENSITIVE_HEADERS}

    logger.info(
        "RustFS callback received | query=%s | headers=%s | payload=%s",
        query_params,
        safe_headers,
        payload.model_dump(),
    )

    event_name, bucket, key, size = payload.get_parsed_details()

    if key and isinstance(key, str):
        key = urllib.parse.unquote(key)
        if bucket and key.startswith(f"{bucket}/"):
            key = key[len(bucket) + 1:]

    if key or bucket:
        logger.info(
            "RustFS upload event | event=%s | bucket=%s | key=%s | size=%s",
            event_name, bucket, key, size,
        )

    return {
        "status": "success",
        "message": "Callback processed successfully",
        "details": {"key": key, "bucket": bucket, "size": size, "eventName": event_name},
    }

