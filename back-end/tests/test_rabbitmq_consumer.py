import json
import os
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import Settings
from app.notebooks.models import Notebook, NotebookDocument
from app.notebooks.tools.ingestion import TransientIngestionError
from app.users.models import User

os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.notebooks.consumer import (
    MessageOutcome,
    parse_minio_object_created_events,
    process_minio_notification_message,
    process_minio_notification_payload,
)


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def make_settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        jwt_secret_key="test-secret-with-at-least-32-bytes",
        jwt_algorithm="HS256",
        rabbitmq_consumer_enabled=False,
        s3_bucket="test-bucket",
        s3_region="us-east-1",
    )


def make_document(session: Session, *, status: str = "pending") -> NotebookDocument:
    user = User(
        id=uuid4(),
        email=f"{status}@example.com",
        hashed_password="hashed-password",
        role="user",
    )
    notebook = Notebook(user_id=user.id, name="Notebook", description="", tags=[])
    session.add(user)
    session.add(notebook)
    session.commit()

    document = NotebookDocument(
        notebook_id=notebook.id,
        user_id=user.id,
        s3_bucket="test-bucket",
        s3_key=f"users/{user.id}/abc/source.pdf",
        filename="source.pdf",
        status=status,
    )
    session.add(document)
    session.commit()
    return document


def test_parse_minio_object_created_events_decodes_and_normalizes_keys() -> None:
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


def test_parse_minio_object_created_events_decodes_plus_as_space() -> None:
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


def test_parse_minio_object_created_events_ignores_unrelated_events() -> None:
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


def test_process_minio_notification_payload_skips_unknown_key_safely() -> None:
    settings = make_settings()
    session = make_session()
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

    with patch("app.notebooks.consumer.engine", session.get_bind()):
        assert (
            process_minio_notification_payload(payload, settings) is MessageOutcome.ACK
        )


def test_process_minio_notification_payload_deduplicates_duplicate_deliveries() -> None:
    settings = make_settings()
    session = make_session()
    document = make_document(session, status="pending")
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

    with (
        patch("app.notebooks.consumer.engine", session.get_bind()),
        patch("app.notebooks.consumer.ingest_document_by_id") as mock_ingest,
    ):
        assert (
            process_minio_notification_payload(payload, settings) is MessageOutcome.ACK
        )
        assert (
            process_minio_notification_payload(payload, settings) is MessageOutcome.ACK
        )
        mock_ingest.assert_called_once()


def test_process_minio_notification_payload_retries_transient_failures() -> None:
    settings = make_settings()
    session = make_session()
    document = make_document(session, status="pending")
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

    with (
        patch("app.notebooks.consumer.engine", session.get_bind()),
        patch(
            "app.notebooks.consumer.ingest_document_by_id",
            side_effect=TransientIngestionError("retry"),
        ),
    ):
        assert (
            process_minio_notification_payload(payload, settings)
            is MessageOutcome.RETRY
        )


def test_process_minio_notification_message_reads_real_json_shape() -> None:
    session = make_session()
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
    with patch("app.notebooks.consumer.engine", session.get_bind()):
        assert (
            process_minio_notification_message(body, make_settings())
            is MessageOutcome.ACK
        )
