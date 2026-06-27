from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.notebooks.models import (
    NotebookDocument,
    NotebookDocumentChunk,
    NotebookReport,
)
from tests.conftest import auth_headers, create_notebook, create_user

pytestmark = pytest.mark.anyio


async def _add_document_to_notebook(notebook_id: UUID, user_id: UUID) -> UUID:
    doc = NotebookDocument(
        notebook_id=notebook_id,
        user_id=user_id,
        filename="test.txt",
        status="indexed",
    )
    await doc.insert()
    chunk = NotebookDocumentChunk(
        document_id=doc.id,
        notebook_id=notebook_id,
        user_id=user_id,
        chunk_index=0,
        content="Test content for report generation.",
        chunk_metadata={},
    )
    await chunk.insert()
    return doc.id


class TestNotebookReports:
    async def test_create_report(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)
        notebook = await create_notebook(user)
        await _add_document_to_notebook(notebook.id, user.id)

        response = await client.post(
            f"/api/v1/notebooks/{notebook.id}/reports",
            json={
                "report_type": "briefing",
                "additional_instructions": "Focus on key findings",
                "detail_level": "high",
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["status"] == "pending"

    async def test_list_reports(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)
        notebook = await create_notebook(user)
        await _add_document_to_notebook(notebook.id, user.id)

        now_response = await client.post(
            f"/api/v1/notebooks/{notebook.id}/reports",
            json={"report_type": "briefing"},
            headers=headers,
        )
        assert now_response.status_code == 201, now_response.text

        later_response = await client.post(
            f"/api/v1/notebooks/{notebook.id}/reports",
            json={"report_type": "study_guide"},
            headers=headers,
        )
        assert later_response.status_code == 201, later_response.text

        response = await client.get(
            f"/api/v1/notebooks/{notebook.id}/reports",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

    async def test_get_report(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)
        notebook = await create_notebook(user)
        await _add_document_to_notebook(notebook.id, user.id)

        create_resp = await client.post(
            f"/api/v1/notebooks/{notebook.id}/reports",
            json={"report_type": "briefing"},
            headers=headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        report_id = create_resp.json()["id"]

        response = await client.get(
            f"/api/v1/notebooks/{notebook.id}/reports/{report_id}",
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["report_type"] == "briefing"

    async def test_get_report_unauthorized(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user1 = await create_user(role="user")
        user2 = await create_user(role="user")
        headers2 = auth_headers(user2, settings)

        notebook = await create_notebook(user1)
        report = NotebookReport(
            notebook_id=notebook.id,
            user_id=user1.id,
            report_type="briefing",
            status="pending",
        )
        await report.insert()

        response = await client.get(
            f"/api/v1/notebooks/{notebook.id}/reports/{report.id}",
            headers=headers2,
        )
        assert response.status_code == 404

    async def test_delete_report(
        self,
        client: AsyncClient,
        settings: Any,
    ) -> None:
        user = await create_user(role="user")
        headers = auth_headers(user, settings)
        notebook = await create_notebook(user)
        await _add_document_to_notebook(notebook.id, user.id)

        create_resp = await client.post(
            f"/api/v1/notebooks/{notebook.id}/reports",
            json={"report_type": "briefing"},
            headers=headers,
        )
        assert create_resp.status_code == 201, create_resp.text
        report_id = create_resp.json()["id"]

        response = await client.delete(
            f"/api/v1/notebooks/{notebook.id}/reports/{report_id}",
            headers=headers,
        )
        assert response.status_code == 204
