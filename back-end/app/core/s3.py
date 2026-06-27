import boto3
from botocore.client import BaseClient
from botocore.config import Config

from app.core.config import Settings


def get_s3_client(settings: Settings, *, endpoint_url: str | None = None) -> BaseClient:
    s3_config = Config(
        signature_version="s3v4",
        retries={"max_attempts": 3},
    )
    client_kwargs: dict[str, object] = {
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


def presign_endpoint_url(settings: Settings) -> str | None:
    """The endpoint presigned URLs should be signed against.

    Prefers the publicly reachable endpoint so links work outside the internal
    network (browsers, remote LLM providers), falling back to the internal one.
    """
    return settings.s3_public_endpoint_url or settings.s3_endpoint_url


def generate_presigned_get_url(
    settings: Settings,
    *,
    bucket: str,
    key: str,
    expires_in: int = 3600,
) -> str:
    """Generate a presigned GET URL for an object, signed against the public endpoint."""
    client = get_s3_client(settings, endpoint_url=presign_endpoint_url(settings))
    return client.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )
