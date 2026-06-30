from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.notebooks.models import NotebookDocument
from tests.conftest import auth_headers, create_notebook, create_user

pytestmark = pytest.mark.anyio


class TestFilePresignedURL:
    async def test_get_presigned_url(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)
        notebook = await create_notebook(user)

        response = await client.post(
            "/api/v1/file/presigned-url",
            json={
                "filename": "test.txt",
                "content_type": "text/plain",
                "operation": "upload",
                "notebook_id": str(notebook.id),
            },
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert "key" in data

    async def test_get_presigned_url_creates_document(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)
        notebook = await create_notebook(user)

        response = await client.post(
            "/api/v1/file/presigned-url",
            json={
                "filename": "test.txt",
                "content_type": "text/plain",
                "operation": "upload",
                "notebook_id": str(notebook.id),
            },
            headers=headers,
        )
        key = response.json()["key"]

        doc = await NotebookDocument.find_one(
            {"s3_key": key},
        )
        assert doc is not None
        assert doc.filename == "test.txt"
        assert doc.status == "pending"

    async def test_get_presigned_url_rejects_unsafe_notebook_content_type(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)
        notebook = await create_notebook(user)

        response = await client.post(
            "/api/v1/file/presigned-url",
            json={
                "filename": "payload.txt",
                "content_type": "text/html",
                "operation": "upload",
                "notebook_id": str(notebook.id),
            },
            headers=headers,
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Unsupported notebook source content type"

    async def test_report_upload_failed(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)
        notebook = await create_notebook(user)

        presigned = await client.post(
            "/api/v1/file/presigned-url",
            json={
                "filename": "fail.txt",
                "content_type": "text/plain",
                "operation": "upload",
                "notebook_id": str(notebook.id),
            },
            headers=headers,
        )
        key = presigned.json()["key"]

        response = await client.post(
            "/api/v1/file/upload-failed",
            json={
                "key": key,
                "error_message": "Upload cancelled",
            },
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
