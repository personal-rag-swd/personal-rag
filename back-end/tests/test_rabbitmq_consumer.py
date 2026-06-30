from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.notebooks.consumer import (
    _process_message,
    parse_minio_object_created_events,
)
from app.notebooks.exceptions import TransientIngestionError
from app.notebooks.models import Notebook, NotebookDocument
from app.users.models import User

pytestmark = pytest.mark.anyio


def make_settings() -> Settings:
    return Settings(
        database_url="mongodb://localhost:27017/test",
        jwt_secret_key="test-secret-key",
        jwt_algorithm="HS256",
        access_token_expire_minutes=30,
        refresh_token_expire_days=30,
        otp_expire_minutes=10,
        otp_max_attempts=5,
        log_level="DEBUG",
        resend_api_key="",
        cookie_secure=False,
        notebook_chunk_size=100,
        notebook_chunk_overlap=20,
        embedding_dimension=1536,
        embedding_model="text-embedding-3-small",
    )


def make_message_body(*, bucket: str, key: str, size: int = 123) -> bytes:
    payload = {
        "Records": [
            {
                "eventName": "s3:ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": bucket},
                    "object": {"key": key, "size": size},
                },
            }
        ]
    }
    return json.dumps(payload).encode("utf-8")


async def make_document(*, status: str = "pending") -> NotebookDocument:
    user = User(
        email=f"{status}@example.com",
        hashed_password="hashed-password",
        role="user",
    )
    await user.insert()

    notebook = Notebook(user_id=user.id, name="Notebook", description="")
    await notebook.insert()

    document = NotebookDocument(
        notebook_id=notebook.id,
        user_id=user.id,
        s3_bucket="test-bucket",
        s3_key=f"users/{user.id}/abc/source.pdf",
        filename="source.pdf",
        status=status,
    )
    await document.insert()
    return document


async def test_parse_minio_object_created_events_decodes_and_normalizes_keys() -> None:
    payload = {
        "Records": [
            {
                "eventName": "s3:ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {
                        "key": "test-bucket/users%2Fabc%2Ffile.pdf",
                        "size": 123,
                    },
                },
            }
        ]
    }

    events = parse_minio_object_created_events(payload)

    assert len(events) == 1
    assert events[0].bucket == "test-bucket"
    assert events[0].key == "users/abc/file.pdf"
    assert events[0].size == 123


async def test_parse_minio_object_created_events_decodes_plus_as_space() -> None:
    payload = {
        "Records": [
            {
                "eventName": "s3:ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {
                        "key": "users%2Fabc%2FSkill_Bridge+%281%29.docx",
                        "size": 123,
                    },
                },
            }
        ]
    }

    events = parse_minio_object_created_events(payload)

    assert len(events) == 1
    assert events[0].key == "users/abc/Skill_Bridge (1).docx"


async def test_parse_minio_object_created_events_ignores_unrelated_events() -> None:
    payload = {
        "Records": [
            {
                "eventName": "s3:ObjectRemoved:Delete",
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "users/abc/file.pdf", "size": 123},
                },
            }
        ]
    }

    assert parse_minio_object_created_events(payload) == []


async def test_process_message_skips_non_json_body() -> None:
    settings = make_settings()
    # Should ack (return without raising) rather than requeue garbage forever.
    await _process_message(b"\xff\xfenot json", settings)


async def test_process_message_skips_unknown_key_safely() -> None:
    settings = make_settings()
    body = make_message_body(bucket="test-bucket", key="users/abc/unknown.pdf")

    with patch("app.notebooks.consumer.ingest_document_by_id") as mock_ingest:
        # No matching document → no ingestion, no raise (ack).
        await _process_message(body, settings)
        mock_ingest.assert_not_called()


async def test_process_message_claims_and_ingests_once_for_duplicate_deliveries() -> (
    None
):
    settings = make_settings()
    document = await make_document(status="pending")
    assert document.s3_bucket is not None
    assert document.s3_key is not None
    body = make_message_body(bucket=document.s3_bucket, key=document.s3_key)

    with patch("app.notebooks.consumer.ingest_document_by_id") as mock_ingest:
        await _process_message(body, settings)
        # Second delivery: the document is already claimed (status="processing"),
        # so the atomic claim returns None and ingestion is not re-triggered.
        await _process_message(body, settings)
        mock_ingest.assert_called_once()


async def test_process_message_propagates_transient_failures() -> None:
    settings = make_settings()
    document = await make_document(status="pending")
    assert document.s3_bucket is not None
    assert document.s3_key is not None
    body = make_message_body(bucket=document.s3_bucket, key=document.s3_key)

    # Propagating the error lets message.process(requeue=True) nack + requeue.
    with (
        patch(
            "app.notebooks.consumer.ingest_document_by_id",
            side_effect=TransientIngestionError("retry"),
        ),
        pytest.raises(TransientIngestionError),
    ):
        await _process_message(body, settings)
