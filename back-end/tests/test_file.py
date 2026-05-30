import os
from collections.abc import Generator
from uuid import uuid4
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.dependencies import get_session
from app.main import app
from app.notebooks.models import Notebook, NotebookDocument
from app.users.models import User

os.environ.setdefault("DATABASE_URL", "sqlite://")


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        jwt_secret_key="test-secret-with-at-least-32-bytes",
        jwt_algorithm="HS256",
        s3_bucket="test-bucket",
        s3_region="us-east-1"
    )


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(settings: Settings, session: Session) -> Generator[TestClient, None, None]:
    def override_get_settings() -> Settings:
        return settings

    def override_get_session() -> Generator[Session, None, None]:
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
    session: Session
) -> None:
    # Setup mocks
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://test-bucket.s3.amazonaws.com/uploads/foo.pdf?AWSAccessKeyId=mock"
    mock_boto_client.return_value = mock_s3

    user = make_user("user@example.com")
    session.add(user)
    session.commit()

    headers = auth_headers(user, settings)
    response = client.post(
        "/api/v1/file/presigned-url",
        json={"filename": "test-file.pdf", "operation": "upload", "content_type": "application/pdf"},
        headers=headers
    )

    assert response.status_code == 200
    res_data = response.json()
    assert "url" in res_data
    assert "key" in res_data
    assert res_data["url"] == "https://test-bucket.s3.amazonaws.com/uploads/foo.pdf?AWSAccessKeyId=mock"
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
    session: Session
) -> None:
    # Setup mocks
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://test-bucket.s3.amazonaws.com/downloads/foo.pdf?AWSAccessKeyId=mock"
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
        headers=headers
    )

    assert response.status_code == 200
    res_data = response.json()
    assert res_data["url"] == "https://test-bucket.s3.amazonaws.com/downloads/foo.pdf?AWSAccessKeyId=mock"
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
        json={"filename": "test-file.pdf", "operation": "upload"}
    )
    assert response.status_code == 401


def test_get_presigned_url_download_forbidden_other_user(
    client: TestClient,
    settings: Settings,
    session: Session
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
        headers=headers
    )

    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]


def test_get_presigned_url_directory_traversal_denied(
    client: TestClient,
    settings: Settings,
    session: Session
) -> None:
    user = make_user("user@example.com")
    session.add(user)
    session.commit()

    headers = auth_headers(user, settings)
    response = client.post(
        "/api/v1/file/presigned-url",
        json={"filename": "../etc/passwd", "operation": "upload"},
        headers=headers
    )

    assert response.status_code == 400
    assert "directory traversal" in response.json()["detail"].lower()


def test_get_presigned_url_invalid_operation(
    client: TestClient,
    settings: Settings,
    session: Session
) -> None:
    user = make_user("user@example.com")
    session.add(user)
    session.commit()

    headers = auth_headers(user, settings)
    response = client.post(
        "/api/v1/file/presigned-url",
        json={"filename": "test.pdf", "operation": "invalid_op"},
        headers=headers
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
    mock_s3.generate_presigned_url.return_value = "https://test-bucket.s3.amazonaws.com/uploads/foo.pdf?AWSAccessKeyId=mock"
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
    doc = session.exec(select(NotebookDocument).where(NotebookDocument.s3_key == key)).first()
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
    )

    def override_get_settings() -> Settings:
        return settings_override

    app.dependency_overrides[get_settings] = override_get_settings

    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "http://localhost:9000/test-bucket/file"
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
