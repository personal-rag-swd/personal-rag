from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.notebooks.models import NotebookDocument
from tests.conftest import (
    auth_headers,
    create_indexed_chunk,
    create_notebook,
    create_user,
)

pytestmark = pytest.mark.anyio


class TestNotebookCRUD:
    async def test_create_notebook(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)

        response = await client.post(
            "/api/v1/notebooks/",
            json={"name": "My Notebook", "description": "Test description"},
            headers=headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Notebook"

    async def test_list_notebooks(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)

        await create_notebook(user, name="Notebook A")
        await create_notebook(user, name="Notebook B")

        response = await client.get("/api/v1/notebooks/", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

    async def test_get_notebook(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)

        notebook = await create_notebook(user)
        response = await client.get(
            f"/api/v1/notebooks/{notebook.id}",
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == notebook.name

    async def test_get_notebook_unauthorized(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user1 = await create_user(role="user")
        user2 = await create_user(role="user")
        headers2 = auth_headers(user2, settings)

        notebook = await create_notebook(user1)
        response = await client.get(
            f"/api/v1/notebooks/{notebook.id}",
            headers=headers2,
        )
        assert response.status_code == 404

    async def test_update_notebook(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)

        notebook = await create_notebook(user)
        response = await client.patch(
            f"/api/v1/notebooks/{notebook.id}",
            json={"name": "Updated Name"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    async def test_delete_notebook(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)

        notebook = await create_notebook(user)
        response = await client.delete(
            f"/api/v1/notebooks/{notebook.id}",
            headers=headers,
        )
        assert response.status_code == 204


class TestNotebookDocuments:
    async def test_list_documents(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)
        notebook = await create_notebook(user)

        await create_indexed_chunk(notebook.id, user.id)

        response = await client.get(
            f"/api/v1/notebooks/{notebook.id}/documents",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    async def test_delete_document(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)
        notebook = await create_notebook(user)

        doc, _ = await create_indexed_chunk(notebook.id, user.id)

        response = await client.delete(
            f"/api/v1/notebooks/{notebook.id}/documents/{doc.id}",
            headers=headers,
        )
        assert response.status_code == 204

    async def test_list_chunks_by_filename(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)
        notebook = await create_notebook(user)

        doc, _ = await create_indexed_chunk(notebook.id, user.id)

        response = await client.get(
            f"/api/v1/notebooks/{notebook.id}/documents/chunks?filename={doc.filename}",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["chunk_index"] == 0


class TestNotebookDocumentPreview:
    async def test_preview_document_returns_inline_content(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)
        notebook = await create_notebook(user)
        document = NotebookDocument(
            notebook_id=notebook.id,
            user_id=user.id,
            filename="note.md",
            content_type="text/markdown",
            size=13,
            status="indexed",
            content="# Test Note\n",
        )
        await document.insert()

        response = await client.get(
            f"/api/v1/notebooks/{notebook.id}/documents/{document.id}/preview",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["preview_type"] == "text"
        assert data["content"] == "# Test Note\n"
        assert data["url"] is None

    async def test_preview_document_returns_404_for_missing_document(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        from uuid import uuid4

        user = await create_user(role="user")
        headers = auth_headers(user, settings)
        notebook = await create_notebook(user)

        response = await client.get(
            f"/api/v1/notebooks/{notebook.id}/documents/{uuid4()}/preview",
            headers=headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Document not found"

    async def test_preview_document_is_scoped_to_owner(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        owner = await create_user(role="user")
        other = await create_user(role="user")
        notebook = await create_notebook(owner)
        document = NotebookDocument(
            notebook_id=notebook.id,
            user_id=owner.id,
            filename="private.txt",
            content_type="text/plain",
            size=7,
            status="indexed",
            content="private",
        )
        await document.insert()

        response = await client.get(
            f"/api/v1/notebooks/{notebook.id}/documents/{document.id}/preview",
            headers=auth_headers(other, settings),
        )

        assert response.status_code == 404

    async def test_preview_document_requires_available_content(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)
        notebook = await create_notebook(user)
        document = NotebookDocument(
            notebook_id=notebook.id,
            user_id=user.id,
            filename="missing.txt",
            content_type="text/plain",
            size=7,
            status="uploaded",
        )
        await document.insert()

        response = await client.get(
            f"/api/v1/notebooks/{notebook.id}/documents/{document.id}/preview",
            headers=headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Document content is not available"

    async def test_preview_document_generates_presigned_url(
        self,
        client: AsyncClient,
        settings: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import app.notebooks.router as notebooks_router

        captured: dict[str, Any] = {}

        class FakeS3Client:
            def generate_presigned_url(self, **kwargs: Any) -> str:
                captured.update(kwargs)
                return "http://localhost:9000/presigned-preview"

        monkeypatch.setattr(
            notebooks_router,
            "get_s3_client",
            lambda *args, **kwargs: FakeS3Client(),
        )

        user = await create_user(role="user")
        headers = auth_headers(user, settings)
        notebook = await create_notebook(user)
        document = NotebookDocument(
            notebook_id=notebook.id,
            user_id=user.id,
            s3_bucket="source-bucket",
            s3_key="users/source.pdf",
            filename="source.pdf",
            content_type="application/pdf",
            size=123,
            status="uploaded",
        )
        await document.insert()

        response = await client.get(
            f"/api/v1/notebooks/{notebook.id}/documents/{document.id}/preview",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["preview_type"] == "url"
        assert data["url"] == "http://localhost:9000/presigned-preview"
        assert captured["ClientMethod"] == "get_object"
        assert captured["HttpMethod"] == "GET"
        assert captured["Params"]["Bucket"] == "source-bucket"
        assert captured["Params"]["Key"] == "users/source.pdf"
        assert captured["Params"]["ResponseContentDisposition"].startswith("inline;")


class TestNotebookDocumentChunks:
    async def test_list_chunks_by_document_id(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)
        notebook = await create_notebook(user)

        doc, _ = await create_indexed_chunk(notebook.id, user.id)

        response = await client.get(
            f"/api/v1/notebooks/{notebook.id}/documents/{doc.id}/chunks",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
