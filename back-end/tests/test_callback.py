import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as client:
        yield client


def test_callback_s3_event_payload(client: TestClient) -> None:
    """Standard S3 event notification format (Records array)."""
    payload = {
        "Records": [
            {
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": "personal-rag-users-files"},
                    "object": {"key": "users/user1/file123.pdf", "size": 102456},
                },
            }
        ]
    }

    response = client.post(
        "/api/v1/file/callback",
        json=payload,
        headers={"X-Test-Header": "test-value"},
        params={"test_param": "param-value"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["details"]["key"] == "users/user1/file123.pdf"
    assert data["details"]["bucket"] == "personal-rag-users-files"
    assert data["details"]["size"] == 102456
    assert data["details"]["eventName"] == "ObjectCreated:Put"


def test_callback_custom_flat_payload(client: TestClient) -> None:
    """Custom / simplified flat payload format."""
    payload = {
        "key": "users/user2/file456.txt",
        "bucket": "custom-bucket",
        "size": 789,
        "eventName": "ObjectCreated:Post",
    }

    response = client.post(
        "/api/v1/file/callback",
        json=payload,
        headers={"Authorization": "Bearer secret-token", "X-Custom": "val"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["details"]["key"] == "users/user2/file456.txt"
    assert data["details"]["bucket"] == "custom-bucket"
    assert data["details"]["size"] == 789
    assert data["details"]["eventName"] == "ObjectCreated:Post"


def test_callback_empty_body(client: TestClient) -> None:
    """Empty / missing body returns success with null details."""
    response = client.post("/api/v1/file/callback")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["details"]["key"] is None
    assert data["details"]["bucket"] is None
    assert data["details"]["size"] is None
    assert data["details"]["eventName"] is None


def test_callback_rustfs_real_payload(client: TestClient) -> None:
    """Real RustFS payload: URL-encoded key, bucket prefix stripped."""
    payload = {
        "EventName": "s3:ObjectCreated:Put",
        "Key": "personal-rag-users-files/users/f0122594-fb20-41d7-b124-ab33d754fb24/475613f1-f592-4c46-a982-4cf14096131f/Skill_Bridge.docx",
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "rustfs:s3",
                "eventName": "s3:ObjectCreated:Put",
                "s3": {
                    "bucket": {
                        "name": "personal-rag-users-files",
                        "arn": "arn:aws:s3:::personal-rag-users-files",
                    },
                    "object": {
                        "key": "users%2Ff0122594-fb20-41d7-b124-ab33d754fb24%2F475613f1-f592-4c46-a982-4cf14096131f%2FSkill_Bridge.docx",
                        "size": 28788,
                        "contentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    },
                },
            }
        ],
    }

    response = client.post("/api/v1/file/callback", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["details"]["bucket"] == "personal-rag-users-files"
    # Key must be URL-decoded and must not carry the bucket name prefix
    assert data["details"]["key"] == (
        "users/f0122594-fb20-41d7-b124-ab33d754fb24"
        "/475613f1-f592-4c46-a982-4cf14096131f/Skill_Bridge.docx"
    )
    assert data["details"]["size"] == 28788
    assert data["details"]["eventName"] == "s3:ObjectCreated:Put"
