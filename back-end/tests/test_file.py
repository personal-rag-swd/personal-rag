from collections.abc import Generator
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.dependencies import get_session
from app.main import app
from app.notebooks.models import Notebook, NotebookDocument
from app.notebooks.tools.ingestion import (
    TransientIngestionError,
    claim_document_for_ingestion,
    ingest_document_by_id,
    process_unprocessed_notebook_documents,
)
from app.users.models import User


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        jwt_secret_key="test-secret-with-at-least-32-bytes",
        jwt_algorithm="HS256",
        s3_bucket="test-bucket",
        s3_region="us-east-1",
        rabbitmq_consumer_enabled=False,
    )


@pytest.fixture
def client(settings: Settings, session: Session) -> Generator[TestClient]:
    def override_get_settings() -> Settings:
        return settings

    def override_get_session() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def make_user(email: str, role: str = "user") -> User:
    return User(id=uuid4(), email=email, hashed_password="hashed-password", role=role)


def auth_headers(user: User, settings: Settings) -> dict[str, str]:
    token = create_access_token(user, settings)
    return {"Authorization": f"Bearer {token}"}


@patch("app.core.s3.boto3.client")
def test_get_presigned_url_upload_success(
    mock_boto_client: MagicMock,
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    # Setup mocks
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = (
        "https://test-bucket.s3.amazonaws.com/uploads/foo.pdf?AWSAccessKeyId=mock"
    )
    mock_boto_client.return_value = mock_s3

    user = make_user("user@example.com")
    session.add(user)
    session.commit()

    headers = auth_headers(user, settings)
    response = client.post(
        "/api/v1/file/presigned-url",
        json={
            "filename": "test-file.pdf",
            "operation": "upload",
            "content_type": "application/pdf",
        },
        headers=headers,
    )

    assert response.status_code == 200
    res_data = response.json()
    assert "url" in res_data
    assert "key" in res_data
    assert (
        res_data["url"]
        == "https://test-bucket.s3.amazonaws.com/uploads/foo.pdf?AWSAccessKeyId=mock"
    )
    assert res_data["key"].startswith(f"users/{user.id}/")
    assert res_data["key"].endswith("/test-file.pdf")

    # Verify boto3 call parameters
    mock_s3.generate_presigned_url.assert_called_once()
    call_args = mock_s3.generate_presigned_url.call_args[1]
    assert call_args["ClientMethod"] == "put_object"
    assert call_args["Params"]["Bucket"] == "test-bucket"
    assert call_args["Params"]["ContentType"] == "application/pdf"
    assert call_args["Params"]["Key"] == res_data["key"]


@patch("app.core.s3.boto3.client")
def test_get_presigned_url_download_success(
    mock_boto_client: MagicMock,
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    # Setup mocks
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = (
        "https://test-bucket.s3.amazonaws.com/downloads/foo.pdf?AWSAccessKeyId=mock"
    )
    mock_boto_client.return_value = mock_s3

    user = make_user("user@example.com")
    session.add(user)
    session.commit()

    # Valid key that belongs to the user
    valid_key = f"users/{user.id}/some-uuid/test-file.pdf"

    headers = auth_headers(user, settings)
    response = client.post(
        "/api/v1/file/presigned-url",
        json={"filename": valid_key, "operation": "download"},
        headers=headers,
    )

    assert response.status_code == 200
    res_data = response.json()
    assert (
        res_data["url"]
        == "https://test-bucket.s3.amazonaws.com/downloads/foo.pdf?AWSAccessKeyId=mock"
    )
    assert res_data["key"] == valid_key

    # Verify boto3 call parameters
    mock_s3.generate_presigned_url.assert_called_once()
    call_args = mock_s3.generate_presigned_url.call_args[1]
    assert call_args["ClientMethod"] == "get_object"
    assert call_args["Params"]["Bucket"] == "test-bucket"
    assert call_args["Params"]["Key"] == valid_key


def test_get_presigned_url_unauthenticated(client: TestClient) -> None:
    response = client.post(
        "/api/v1/file/presigned-url",
        json={"filename": "test-file.pdf", "operation": "upload"},
    )
    assert response.status_code == 401


def test_get_presigned_url_download_forbidden_other_user(
    client: TestClient, settings: Settings, session: Session
) -> None:
    user = make_user("user@example.com")
    other_user_id = uuid4()
    session.add(user)
    session.commit()

    # Key that belongs to ANOTHER user
    forbidden_key = f"users/{other_user_id}/some-uuid/test-file.pdf"

    headers = auth_headers(user, settings)
    response = client.post(
        "/api/v1/file/presigned-url",
        json={"filename": forbidden_key, "operation": "download"},
        headers=headers,
    )

    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]


def test_get_presigned_url_directory_traversal_denied(
    client: TestClient, settings: Settings, session: Session
) -> None:
    user = make_user("user@example.com")
    session.add(user)
    session.commit()

    headers = auth_headers(user, settings)
    response = client.post(
        "/api/v1/file/presigned-url",
        json={"filename": "../etc/passwd", "operation": "upload"},
        headers=headers,
    )

    assert response.status_code == 400
    assert "directory traversal" in response.json()["detail"].lower()


def test_get_presigned_url_invalid_operation(
    client: TestClient, settings: Settings, session: Session
) -> None:
    user = make_user("user@example.com")
    session.add(user)
    session.commit()

    headers = auth_headers(user, settings)
    response = client.post(
        "/api/v1/file/presigned-url",
        json={"filename": "test.pdf", "operation": "invalid_op"},
        headers=headers,
    )

    assert response.status_code == 400


@patch("app.core.s3.boto3.client")
def test_get_presigned_url_upload_with_notebook_creates_pending_document(
    mock_boto_client: MagicMock,
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = (
        "https://test-bucket.s3.amazonaws.com/uploads/foo.pdf?AWSAccessKeyId=mock"
    )
    mock_boto_client.return_value = mock_s3

    user = make_user("user@example.com")
    session.add(user)
    session.commit()

    notebook = Notebook(user_id=user.id, name="N", description="", tags=[])
    session.add(notebook)
    session.commit()

    headers = auth_headers(user, settings)
    response = client.post(
        "/api/v1/file/presigned-url",
        json={
            "filename": "test-file.pdf",
            "operation": "upload",
            "content_type": "application/pdf",
            "notebook_id": str(notebook.id),
        },
        headers=headers,
    )

    assert response.status_code == 200
    key = response.json()["key"]
    doc = session.exec(
        select(NotebookDocument).where(NotebookDocument.s3_key == key)
    ).first()
    assert doc is not None
    assert doc.notebook_id == notebook.id
    assert doc.user_id == user.id
    assert doc.status == "pending"


@patch("app.core.s3.boto3.client")
def test_get_presigned_url_upload_with_foreign_notebook_rejected(
    mock_boto_client: MagicMock,
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    owner = make_user("owner@example.com")
    other = make_user("other@example.com")
    session.add(owner)
    session.add(other)
    session.commit()

    notebook = Notebook(user_id=other.id, name="Other N", description="", tags=[])
    session.add(notebook)
    session.commit()

    headers = auth_headers(owner, settings)
    response = client.post(
        "/api/v1/file/presigned-url",
        json={
            "filename": "test-file.pdf",
            "operation": "upload",
            "notebook_id": str(notebook.id),
        },
        headers=headers,
    )

    assert response.status_code == 404


@patch("app.core.s3.boto3.client")
def test_get_presigned_url_uses_public_endpoint_for_signing(
    mock_boto_client: MagicMock,
    client: TestClient,
    session: Session,
) -> None:
    settings_override = Settings(
        database_url="sqlite://",
        jwt_secret_key="test-secret-with-at-least-32-bytes",
        jwt_algorithm="HS256",
        s3_bucket="test-bucket",
        s3_region="us-east-1",
        s3_endpoint_url="http://minio:9000",
        s3_public_endpoint_url="http://localhost:9000",
        rabbitmq_consumer_enabled=False,
    )

    def override_get_settings() -> Settings:
        return settings_override

    app.dependency_overrides[get_settings] = override_get_settings

    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = (
        "http://localhost:9000/test-bucket/file"
    )
    mock_boto_client.return_value = mock_s3

    user = make_user("user@example.com")
    session.add(user)
    session.commit()

    response = client.post(
        "/api/v1/file/presigned-url",
        json={"filename": "test-file.pdf", "operation": "upload"},
        headers=auth_headers(user, settings_override),
    )

    assert response.status_code == 200
    assert mock_boto_client.call_args[1]["endpoint_url"] == "http://localhost:9000"


def test_report_upload_failed_marks_pending_document_failed(
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("user@example.com")
    session.add(user)
    session.commit()

    notebook = Notebook(user_id=user.id, name="N", description="", tags=[])
    session.add(notebook)
    session.commit()

    key = f"users/{user.id}/abc/test-file.pdf"
    document = NotebookDocument(
        notebook_id=notebook.id,
        user_id=user.id,
        s3_bucket="test-bucket",
        s3_key=key,
        filename="test-file.pdf",
        content_type="application/pdf",
        status="pending",
    )
    session.add(document)
    session.commit()

    response = client.post(
        "/api/v1/file/upload-failed",
        json={"key": key, "error_message": "Storage upload failed: HTTP 403 Forbidden"},
        headers=auth_headers(user, settings),
    )
    assert response.status_code == 200
    assert response.json()["updated"] is True

    session.refresh(document)
    assert document.status == "failed"
    assert "403" in (document.error_message or "")


@patch("app.notebooks.tools.ingestion.ingest_document_by_id")
@patch("app.notebooks.tools.ingestion.get_s3_client")
def test_process_unprocessed_documents_promotes_visible_pending_upload(
    mock_get_s3_client: MagicMock,
    mock_ingest_document_by_id: MagicMock,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("user@example.com")
    session.add(user)
    session.commit()

    notebook = Notebook(user_id=user.id, name="N", description="", tags=[])
    session.add(notebook)
    session.commit()

    document = NotebookDocument(
        notebook_id=notebook.id,
        user_id=user.id,
        s3_bucket="test-bucket",
        s3_key=f"users/{user.id}/abc/test-file.pdf",
        filename="test-file.pdf",
        content_type="application/pdf",
        status="pending",
    )
    session.add(document)
    session.commit()

    mock_s3 = MagicMock()
    mock_s3.head_object.return_value = {"ContentLength": 1234}
    mock_get_s3_client.return_value = mock_s3

    stats = process_unprocessed_notebook_documents(session, settings)

    assert stats == {
        "checked": 1,
        "uploaded": 1,
        "ingested": 1,
        "skipped": 0,
        "recovered": 0,
    }
    mock_s3.head_object.assert_called_once_with(
        Bucket="test-bucket", Key=document.s3_key
    )
    mock_get_s3_client.assert_called_once_with(settings)
    mock_ingest_document_by_id.assert_called_once_with(
        session,
        document.id,
        settings,
        s3_client=mock_s3,
    )

    session.refresh(document)
    assert document.status == "uploaded"
    assert document.size == 1234


@patch("app.notebooks.tools.ingestion.ingest_document_by_id")
@patch("app.notebooks.tools.ingestion.get_s3_client")
def test_process_unprocessed_documents_skips_pending_upload_until_object_exists(
    mock_get_s3_client: MagicMock,
    mock_ingest_document_by_id: MagicMock,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("user@example.com")
    session.add(user)
    session.commit()

    notebook = Notebook(user_id=user.id, name="N", description="", tags=[])
    session.add(notebook)
    session.commit()

    document = NotebookDocument(
        notebook_id=notebook.id,
        user_id=user.id,
        s3_bucket="test-bucket",
        s3_key=f"users/{user.id}/abc/missing.pdf",
        filename="missing.pdf",
        content_type="application/pdf",
        status="pending",
    )
    session.add(document)
    session.commit()

    mock_s3 = MagicMock()
    mock_s3.head_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey"}, "ResponseMetadata": {"HTTPStatusCode": 404}},
        "HeadObject",
    )
    mock_get_s3_client.return_value = mock_s3

    stats = process_unprocessed_notebook_documents(session, settings)

    assert stats == {
        "checked": 1,
        "uploaded": 0,
        "ingested": 0,
        "skipped": 1,
        "recovered": 0,
    }
    mock_get_s3_client.assert_called_once_with(settings)
    mock_ingest_document_by_id.assert_not_called()

    session.refresh(document)
    assert document.status == "pending"


@patch("app.notebooks.tools.ingestion.ingest_document_by_id")
def test_process_unprocessed_documents_marks_stale_processing_failed(
    mock_ingest_document_by_id: MagicMock,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("stale@example.com")
    session.add(user)
    session.commit()
    notebook = Notebook(user_id=user.id, name="N", description="", tags=[])
    session.add(notebook)
    session.commit()

    stale_doc = NotebookDocument(
        notebook_id=notebook.id,
        user_id=user.id,
        s3_bucket="test-bucket",
        s3_key=f"users/{user.id}/abc/stale.pdf",
        filename="stale.pdf",
        content_type="application/pdf",
        status="processing",
    )
    session.add(stale_doc)
    session.commit()
    stale_doc.updated_at = stale_doc.updated_at.replace(year=2020)
    session.add(stale_doc)
    session.commit()

    stats = process_unprocessed_notebook_documents(session, settings)
    session.refresh(stale_doc)

    assert stats["recovered"] == 1
    assert stale_doc.status == "failed"
    assert "timed out" in (stale_doc.error_message or "").lower()
    mock_ingest_document_by_id.assert_not_called()


@patch("app.notebooks.tools.ingestion.ingest_document_by_id")
def test_process_unprocessed_documents_keeps_recent_processing_untouched(
    mock_ingest_document_by_id: MagicMock,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("recent@example.com")
    session.add(user)
    session.commit()
    notebook = Notebook(user_id=user.id, name="N", description="", tags=[])
    session.add(notebook)
    session.commit()

    recent_doc = NotebookDocument(
        notebook_id=notebook.id,
        user_id=user.id,
        s3_bucket="test-bucket",
        s3_key=f"users/{user.id}/abc/recent.pdf",
        filename="recent.pdf",
        content_type="application/pdf",
        status="processing",
    )
    session.add(recent_doc)
    session.commit()

    stats = process_unprocessed_notebook_documents(session, settings)
    session.refresh(recent_doc)

    assert stats["recovered"] == 0
    assert recent_doc.status == "processing"
    mock_ingest_document_by_id.assert_not_called()


def test_ingest_document_rejects_non_1536_dimension(
    settings: Settings, session: Session
) -> None:
    user = make_user("dimension@example.com")
    session.add(user)
    session.commit()
    notebook = Notebook(user_id=user.id, name="N", description="", tags=[])
    session.add(notebook)
    session.commit()
    doc = NotebookDocument(
        notebook_id=notebook.id,
        user_id=user.id,
        s3_bucket="test-bucket",
        s3_key=f"users/{user.id}/abc/reject.pdf",
        filename="reject.pdf",
        content_type="application/pdf",
        status="uploaded",
    )
    session.add(doc)
    session.commit()

    bad_settings = settings.model_copy(update={"embedding_dimension": 1024})
    with pytest.raises(RuntimeError, match="EMBEDDING_DIMENSION"):
        ingest_document_by_id(session, doc.id, bad_settings)


@patch("app.notebooks.tools.ingestion.ingest_document_by_id")
def test_process_unprocessed_documents_marks_stale_pending_failed(
    mock_ingest_document_by_id: MagicMock,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("stale-pending@example.com")
    session.add(user)
    session.commit()
    notebook = Notebook(user_id=user.id, name="N", description="", tags=[])
    session.add(notebook)
    session.commit()

    stale_pending_doc = NotebookDocument(
        notebook_id=notebook.id,
        user_id=user.id,
        s3_bucket="test-bucket",
        s3_key=f"users/{user.id}/abc/stale_pending.pdf",
        filename="stale_pending.pdf",
        content_type="application/pdf",
        status="pending",
    )
    session.add(stale_pending_doc)
    session.commit()
    stale_pending_doc.created_at = stale_pending_doc.created_at.replace(year=2020)
    session.add(stale_pending_doc)
    session.commit()

    stats = process_unprocessed_notebook_documents(session, settings)
    session.refresh(stale_pending_doc)

    assert stats["recovered"] == 1
    assert stale_pending_doc.status == "failed"
    assert "upload timed out" in (stale_pending_doc.error_message or "").lower()
    mock_ingest_document_by_id.assert_not_called()


@patch("app.notebooks.tools.ingestion.ingest_document_by_id")
@patch("app.notebooks.tools.ingestion.get_s3_client")
def test_process_unprocessed_documents_prioritizes_uploaded_before_pending(
    mock_get_s3_client: MagicMock,
    mock_ingest_document_by_id: MagicMock,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("priority@example.com")
    session.add(user)
    session.commit()
    notebook = Notebook(user_id=user.id, name="N", description="", tags=[])
    session.add(notebook)
    session.commit()

    # Create 3 pending documents. Since they are pending and missing, they will be skipped.
    pending_docs = []
    for i in range(3):
        doc = NotebookDocument(
            notebook_id=notebook.id,
            user_id=user.id,
            s3_bucket="test-bucket",
            s3_key=f"users/{user.id}/abc/pending_{i}.pdf",
            filename=f"pending_{i}.pdf",
            content_type="application/pdf",
            status="pending",
        )
        session.add(doc)
        pending_docs.append(doc)

    # Create 1 uploaded document. This should be prioritized even if created later.
    uploaded_doc = NotebookDocument(
        notebook_id=notebook.id,
        user_id=user.id,
        s3_bucket="test-bucket",
        s3_key=f"users/{user.id}/abc/uploaded.pdf",
        filename="uploaded.pdf",
        content_type="application/pdf",
        status="uploaded",
    )
    session.add(uploaded_doc)
    session.commit()

    # S3 client mock for head_object (will return NoSuchKey for the pending files)
    mock_s3 = MagicMock()
    mock_s3.head_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey"}, "ResponseMetadata": {"HTTPStatusCode": 404}},
        "HeadObject",
    )
    mock_get_s3_client.return_value = mock_s3

    # Set limit to 2. This forces a choice:
    # If it orders by created_at, it will get pending_0 and pending_1, check them, skip them, and end.
    # If it orders by status desc (uploaded first), it will get uploaded (status=uploaded) and pending_0,
    # process/ingest uploaded, check/skip pending_0, and we will see ingested=1, skipped=1.
    stats = process_unprocessed_notebook_documents(session, settings, limit=2)

    assert stats["ingested"] == 1
    assert stats["skipped"] == 1
    mock_get_s3_client.assert_called_once_with(settings)
    mock_ingest_document_by_id.assert_called_once_with(
        session,
        uploaded_doc.id,
        settings,
        s3_client=mock_s3,
    )


@patch("app.notebooks.tools.ingestion.get_s3_client")
def test_ingest_document_marks_failed_when_object_read_fails(
    mock_get_s3_client: MagicMock,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("ingest-failure@example.com")
    session.add(user)
    session.commit()
    notebook = Notebook(user_id=user.id, name="N", description="", tags=[])
    session.add(notebook)
    session.commit()

    document = NotebookDocument(
        notebook_id=notebook.id,
        user_id=user.id,
        s3_bucket="test-bucket",
        s3_key=f"users/{user.id}/abc/failure.pdf",
        filename="failure.pdf",
        content_type="application/pdf",
        status="uploaded",
    )
    session.add(document)
    session.commit()

    mock_s3 = MagicMock()
    mock_s3.get_object.side_effect = RuntimeError("storage read failed")
    mock_get_s3_client.return_value = mock_s3

    ingest_document_by_id(session, document.id, settings)

    mock_get_s3_client.assert_called_once_with(settings)
    mock_s3.get_object.assert_called_once_with(
        Bucket="test-bucket", Key=document.s3_key
    )
    session.refresh(document)
    assert document.status == "failed"
    assert "storage read failed" in (document.error_message or "")


@pytest.mark.parametrize("initial_status", ["pending", "uploaded"])
def test_claim_document_for_ingestion_claims_once(
    initial_status: str,
    session: Session,
) -> None:
    user = make_user(f"{initial_status}@example.com")
    session.add(user)
    session.commit()
    notebook = Notebook(user_id=user.id, name="N", description="", tags=[])
    session.add(notebook)
    session.commit()

    document = NotebookDocument(
        notebook_id=notebook.id,
        user_id=user.id,
        s3_bucket="test-bucket",
        s3_key=f"users/{user.id}/claim/{initial_status}.pdf",
        filename=f"{initial_status}.pdf",
        status=initial_status,
    )
    session.add(document)
    session.commit()

    claimed = claim_document_for_ingestion(session, document.id, size=42)

    assert claimed is not None
    assert claimed.status == "processing"
    assert claimed.size == 42
    assert claim_document_for_ingestion(session, document.id) is None


@pytest.mark.parametrize("initial_status", ["processing", "indexed", "failed"])
def test_claim_document_for_ingestion_rejects_non_claimable_statuses(
    initial_status: str,
    session: Session,
) -> None:
    user = make_user(f"{initial_status}@example.com")
    session.add(user)
    session.commit()
    notebook = Notebook(user_id=user.id, name="N", description="", tags=[])
    session.add(notebook)
    session.commit()

    document = NotebookDocument(
        notebook_id=notebook.id,
        user_id=user.id,
        s3_bucket="test-bucket",
        s3_key=f"users/{user.id}/claim/{initial_status}.pdf",
        filename=f"{initial_status}.pdf",
        status=initial_status,
    )
    session.add(document)
    session.commit()

    assert claim_document_for_ingestion(session, document.id) is None


@patch("app.notebooks.tools.ingestion.get_s3_client")
def test_ingest_document_requeues_transient_storage_failures(
    mock_get_s3_client: MagicMock,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("transient@example.com")
    session.add(user)
    session.commit()
    notebook = Notebook(user_id=user.id, name="N", description="", tags=[])
    session.add(notebook)
    session.commit()

    document = NotebookDocument(
        notebook_id=notebook.id,
        user_id=user.id,
        s3_bucket="test-bucket",
        s3_key=f"users/{user.id}/abc/transient.pdf",
        filename="transient.pdf",
        content_type="application/pdf",
        status="processing",
    )
    session.add(document)
    session.commit()

    mock_s3 = MagicMock()
    mock_s3.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey"}, "ResponseMetadata": {"HTTPStatusCode": 404}},
        "GetObject",
    )
    mock_get_s3_client.return_value = mock_s3

    with pytest.raises(TransientIngestionError):
        ingest_document_by_id(
            session, document.id, settings, require_processing_status=True
        )

    session.refresh(document)
    assert document.status == "uploaded"
    assert document.error_message is None
