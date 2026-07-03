from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import obstore
import obstore.store

from app.core.config import Settings

if TYPE_CHECKING:
    from obstore.store import ClientConfig, S3Config, S3Store


def _build_s3_store(settings: Settings, *, endpoint_url: str | None = None) -> S3Store:
    config: S3Config = {
        "bucket": settings.s3_bucket,
        "region": settings.s3_region,
    }
    if settings.aws_access_key_id:
        config["access_key_id"] = settings.aws_access_key_id
    if settings.aws_secret_access_key:
        config["secret_access_key"] = settings.aws_secret_access_key
    resolved_endpoint = endpoint_url or settings.s3_endpoint_url
    if resolved_endpoint:
        config["endpoint"] = resolved_endpoint

    client_options: ClientConfig = {}
    if resolved_endpoint and resolved_endpoint.startswith("http://"):
        client_options["allow_http"] = True

    return obstore.store.S3Store(
        config=config,
        client_options=client_options or None,
        retry_config={"max_retries": 3},
    )


# Cached so the store's HTTP connection pool is reused across calls (mirrors
# the LRU-cached LLM/embedding providers). Keyed on the S3 config fields so
# tests with different settings get distinct stores.
_store_cache: dict[tuple[str | None, ...], S3Store] = {}


def get_s3_store(settings: Settings) -> S3Store:
    cache_key = (
        settings.s3_bucket,
        settings.s3_region,
        settings.aws_access_key_id,
        settings.aws_secret_access_key,
        settings.s3_endpoint_url,
    )
    store = _store_cache.get(cache_key)
    if store is None:
        store = _store_cache[cache_key] = _build_s3_store(settings)
    return store


async def get_object_bytes(store: S3Store, key: str) -> bytes:
    """Fetch an object's full body from S3/MinIO as bytes."""
    result = await obstore.get_async(store, key)
    return bytes(await result.bytes_async())


def presign_endpoint_url(settings: Settings) -> str | None:
    """The endpoint presigned URLs should be signed against.

    Prefers the publicly reachable endpoint so links work outside the internal
    network (browsers, remote LLM providers), falling back to the internal one.
    """
    return settings.s3_public_endpoint_url or settings.s3_endpoint_url


def generate_presigned_get_url(
    settings: Settings,
    *,
    key: str,
    expires_in: int = 3600,
) -> str:
    """Generate a presigned GET URL for an object, signed against the public endpoint."""
    store = _build_s3_store(settings, endpoint_url=presign_endpoint_url(settings))
    return obstore.sign(store, "GET", key, timedelta(seconds=expires_in))
