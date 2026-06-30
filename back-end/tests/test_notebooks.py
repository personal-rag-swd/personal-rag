from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

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
