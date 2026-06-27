from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.notebooks.consumer import (
    parse_minio_object_created_events,
    process_minio_notification_message,
    process_minio_notification_payload,
)
from app.notebooks.models import Notebook, NotebookDocument
from app.notebooks.rag.ingestion_service import TransientIngestionError
from app.users.models import User

pytestmark = pytest.mark.anyio


def make_settings() -> object:
    from app.core.config import Settings

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


async def test_process_minio_notification_payload_skips_unknown_key_safely() -> None:
    settings = make_settings()
    payload = {
        "Records": [
            {
                "eventName": "s3:ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "users/abc/unknown.pdf", "size": 123},
                },
            }
        ]
    }

    result = await process_minio_notification_payload(payload, settings)
    assert result is True


async def test_process_minio_notification_payload_deduplicates_duplicate_deliveries() -> None:
    settings = make_settings()
    document = await make_document(status="pending")
    payload = {
        "Records": [
            {
                "eventName": "s3:ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": document.s3_bucket},
                    "object": {"key": document.s3_key, "size": 123},
                },
            }
        ]
    }

    with patch(
        "app.notebooks.consumer.ingest_document_by_id"
    ) as mock_ingest:
        assert await process_minio_notification_payload(payload, settings) is True
        assert await process_minio_notification_payload(payload, settings) is True
        mock_ingest.assert_called_once()


async def test_process_minio_notification_payload_retries_transient_failures() -> None:
    settings = make_settings()
    document = await make_document(status="pending")
    payload = {
        "Records": [
            {
                "eventName": "s3:ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": document.s3_bucket},
                    "object": {"key": document.s3_key, "size": 123},
                },
            }
        ]
    }

    with patch(
        "app.notebooks.consumer.ingest_document_by_id",
        side_effect=TransientIngestionError("retry"),
    ):
        assert await process_minio_notification_payload(payload, settings) is False


async def test_process_minio_notification_message_reads_real_json_shape() -> None:
    settings = make_settings()
    payload = {
        "Records": [
            {
                "eventName": "s3:ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "users%2Fabc%2Ffile.pdf", "size": 5},
                },
            }
        ]
    }

    body = json.dumps(payload).encode("utf-8")
    assert await process_minio_notification_message(body, settings) is True
