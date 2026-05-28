import os
import uuid
import logging
import urllib.parse
from typing import Any

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from fastapi import HTTPException, status
from sqlmodel import Session

from app.core.config import Settings
from app.users.models import User
from app.file.schemas import PresignedUrlRequest, PresignedUrlResponse, FileCallbackPayload
from app.notebooks.service import get_notebook
from app.notebooks.tools import mark_document_uploaded_and_get_id, register_pending_notebook_document

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    """Strips path traversal components and returns the clean file basename."""
    base = os.path.basename(filename)
    base = base.replace("/", "").replace("\\", "")
    return base


def get_s3_client(settings: Settings, *, endpoint_url: str | None = None):
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
    resolved_endpoint = endpoint_url or settings.s3_endpoint_url
    if resolved_endpoint:
        client_kwargs["endpoint_url"] = resolved_endpoint

    return boto3.client(**client_kwargs)


def generate_presigned_url_service(
    request: PresignedUrlRequest,
    current_user: User,
    settings: Settings,
    session: Session,
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
        # Sign against the same endpoint the browser will call.
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
        logger.error("Failed to generate S3 presigned URL: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate presigned URL",
        )

    if operation == "upload" and request.notebook_id is not None:
        notebook = get_notebook(session, request.notebook_id, current_user)
        register_pending_notebook_document(
            session,
            notebook=notebook,
            current_user=current_user,
            bucket=settings.s3_bucket,
            key=s3_key,
            filename=cleaned_name,
            content_type=request.content_type,
        )

    return PresignedUrlResponse(url=presigned_url, key=s3_key)


_SENSITIVE_HEADERS = {"authorization", "cookie", "proxy-authorization", "x-api-key"}


def handle_file_callback_service(
    payload: FileCallbackPayload,
    headers: dict[str, str],
    query_params: dict[str, str],
    session: Session,
) -> dict[str, Any]:
    """Processes an incoming S3-compatible webhook callback and returns parsed event details."""
    safe_headers = {k: v for k, v in headers.items() if k.lower() not in _SENSITIVE_HEADERS}

    logger.info(
        "S3 callback received | query=%s | headers=%s | payload=%s",
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
            "S3 upload event | event=%s | bucket=%s | key=%s | size=%s",
            event_name, bucket, key, size,
        )

    document_id = mark_document_uploaded_and_get_id(
        session,
        bucket=bucket,
        key=key,
        size=size,
        event_name=event_name,
    )

    return {
        "status": "success",
        "message": "Callback processed successfully",
        "details": {
            "key": key,
            "bucket": bucket,
            "size": size,
            "eventName": event_name,
            "document_id": str(document_id) if document_id else None,
        },
    }
