from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from beanie.odm.enums import SortDirection
from httpx import AsyncClient
from starlette.responses import JSONResponse

from app.notebooks.models import NotebookMessage
from tests.conftest import (
    auth_headers,
    create_indexed_chunk,
    create_notebook,
    create_user,
    make_user,
)

pytestmark = pytest.mark.anyio

CHAT_RESPONSE = JSONResponse(
    content={"choices": [{"message": {"role": "assistant", "content": "Hello!"}}]},
    status_code=200,
)


async def test_notebook_chat_endpoint_returns_response(
    client: AsyncClient,
    settings: Any,
) -> None:
    user = make_user(email="user@example.com")
    await user.insert()

    headers = auth_headers(user, settings)
    created = await client.post(
        "/api/v1/notebooks/",
        json={"name": "Chat", "description": "", "tags": []},
        headers=headers,
    )
    assert created.status_code == 201
    nb_id = created.json()["id"]

    with patch(
        "app.notebooks.router.AGUIAdapter.dispatch_request",
        return_value=CHAT_RESPONSE,
    ):
        response = await client.post(
            f"/api/v1/notebooks/{nb_id}/chat",
            json={"messages": []},
            headers=headers,
        )
    # Chat endpoint returns raw response from AGUIAdapter dispatch
    assert response.status_code == 200


async def test_notebook_chat_endpoint_is_scoped_to_owner(
    client: AsyncClient,
    settings: Any,
) -> None:
    owner = make_user(email="owner@example.com")
    await owner.insert()
    other_user = make_user(email="other@example.com")
    await other_user.insert()

    owner_headers = auth_headers(owner, settings)
    other_headers = auth_headers(other_user, settings)

    created = await client.post(
        "/api/v1/notebooks/",
        json={"name": "Private", "description": "", "tags": []},
        headers=owner_headers,
    )
    assert created.status_code == 201
    nb_id = created.json()["id"]

    with patch(
        "app.notebooks.router.AGUIAdapter.dispatch_request",
        return_value=CHAT_RESPONSE,
    ):
        response = await client.post(
            f"/api/v1/notebooks/{nb_id}/chat",
            json={"messages": []},
            headers=other_headers,
        )
    assert response.status_code == 404


async def test_chat_history_endpoint(
    client: AsyncClient,
    settings: Any,
) -> None:
    user = await create_user(role="user")
    headers = auth_headers(user, settings)
    notebook = await create_notebook(user)

    response = await client.get(
        f"/api/v1/notebooks/{notebook.id}/chat/history",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_chunks_endpoints(
    client: AsyncClient,
    settings: Any,
) -> None:
    user = make_user(email="owner@example.com")
    await user.insert()
    headers = auth_headers(user, settings)

    created = await client.post(
        "/api/v1/notebooks/",
        json={"name": "Test Notebook", "description": "", "tags": []},
        headers=headers,
    )
    nb_id = created.json()["id"]

    from tests.conftest import create_indexed_chunk

    notebook_id = created.json()["id"]
    from uuid import UUID

    doc, _ = await create_indexed_chunk(UUID(notebook_id), user.id)

    resp = await client.get(
        f"/api/v1/notebooks/{nb_id}/documents/chunks?filename=test.txt",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["chunk_index"] == 0

    resp_by_id = await client.get(
        f"/api/v1/notebooks/{nb_id}/documents/{doc.id}/chunks",
        headers=headers,
    )
    assert resp_by_id.status_code == 200
    by_id_data = resp_by_id.json()
    assert len(by_id_data) == 1
    assert by_id_data[0]["document_id"] == str(doc.id)

    resp_single_by_id = await client.get(
        f"/api/v1/notebooks/{nb_id}/documents/{doc.id}/chunks/0",
        headers=headers,
    )
    assert resp_single_by_id.status_code == 200
    assert resp_single_by_id.json()["document_id"] == str(doc.id)


async def test_notebook_message_stores_and_retrieves_history() -> None:
    from uuid import uuid4

    notebook_id = uuid4()

    msg1 = NotebookMessage(
        notebook_id=notebook_id,
        seq=1,
        message={"role": "user", "content": "Hello"},
    )
    await msg1.insert()

    msg2 = NotebookMessage(
        notebook_id=notebook_id,
        seq=2,
        message={"role": "assistant", "content": "Hi there"},
    )
    await msg2.insert()

    stored = (
        await NotebookMessage.find({"notebook_id": notebook_id})
        .sort(("seq", SortDirection.ASCENDING))
        .to_list()
    )
    assert len(stored) == 2
    assert stored[0].message["content"] == "Hello"
    assert stored[1].message["content"] == "Hi there"


async def test_notebook_chat_persists_messages_in_db(
    client: AsyncClient,
    settings: Any,
) -> None:
    user = await create_user(role="user")
    headers = auth_headers(user, settings)
    notebook = await create_notebook(user)

    from unittest.mock import patch

    from pydantic_ai.models.test import TestModel

    test_model = TestModel(custom_output_text="Hello from TestModel!")

    with (
        patch("app.notebooks.router.resolve_chat_provider", return_value=test_model),
        patch("app.notebooks.agent.chat_agent.search_notebook_chunks", return_value=[]),
    ):
        response = await client.post(
            f"/api/v1/notebooks/{notebook.id}/chat",
            json={
                "threadId": str(notebook.id),
                "runId": "msg-1-run",
                "state": {},
                "messages": [
                    {
                        "role": "user",
                        "id": "msg-1",
                        "content": "Hi agent",
                    }
                ],
                "tools": [],
                "context": [],
                "forwardedProps": {},
            },
            headers=headers,
        )
        assert response.status_code == 200
        # Fully consume the stream response content so that on_complete triggers
        await response.aread()

    # Now verify that NotebookMessages were inserted in MongoDB
    messages = (
        await NotebookMessage.find({"notebook_id": notebook.id})
        .sort(("seq", SortDirection.ASCENDING))
        .to_list()
    )
    assert len(messages) == 4


async def test_notebook_chat_scopes_search_to_document_id(
    client: AsyncClient,
    settings: Any,
) -> None:
    from pydantic_ai.models.test import TestModel

    user = await create_user(role="user")
    headers = auth_headers(user, settings)
    notebook = await create_notebook(user)
    doc, _ = await create_indexed_chunk(notebook.id, user.id)

    test_model = TestModel(custom_output_text="Hello from TestModel!")
    search_mock = AsyncMock(return_value=[])

    with (
        patch("app.notebooks.router.resolve_chat_provider", return_value=test_model),
        patch("app.notebooks.agent.chat_agent.search_notebook_chunks", search_mock),
    ):
        response = await client.post(
            f"/api/v1/notebooks/{notebook.id}/chat",
            json={
                "threadId": str(notebook.id),
                "runId": "msg-1-run",
                "state": {},
                "messages": [{"role": "user", "id": "msg-1", "content": "Hi agent"}],
                "tools": [],
                "context": [],
                "forwardedProps": {"documentIds": [str(doc.id)]},
            },
            headers=headers,
        )
        assert response.status_code == 200
        await response.aread()

    search_mock.assert_awaited()
    assert search_mock.await_args is not None
    assert search_mock.await_args.kwargs["document_ids"] == [doc.id]


async def test_notebook_chat_rejects_unknown_document_id(
    client: AsyncClient,
    settings: Any,
) -> None:
    user = await create_user(role="user")
    headers = auth_headers(user, settings)
    notebook = await create_notebook(user)

    response = await client.post(
        f"/api/v1/notebooks/{notebook.id}/chat",
        json={
            "threadId": str(notebook.id),
            "runId": "msg-1-run",
            "state": {},
            "messages": [{"role": "user", "id": "msg-1", "content": "Hi agent"}],
            "tools": [],
            "context": [],
            "forwardedProps": {"documentIds": [str(uuid4())]},
        },
        headers=headers,
    )
    assert response.status_code == 404


async def test_notebook_chat_rejects_document_id_from_other_owner(
    client: AsyncClient,
    settings: Any,
) -> None:
    owner = await create_user(email="owner@example.com", role="user")
    other_user = await create_user(email="other@example.com", role="user")
    owner_notebook = await create_notebook(owner)
    other_notebook = await create_notebook(other_user)
    foreign_doc, _ = await create_indexed_chunk(other_notebook.id, other_user.id)

    headers = auth_headers(owner, settings)
    response = await client.post(
        f"/api/v1/notebooks/{owner_notebook.id}/chat",
        json={
            "threadId": str(owner_notebook.id),
            "runId": "msg-1-run",
            "state": {},
            "messages": [{"role": "user", "id": "msg-1", "content": "Hi agent"}],
            "tools": [],
            "context": [],
            "forwardedProps": {"documentIds": [str(foreign_doc.id)]},
        },
        headers=headers,
    )
    assert response.status_code == 404
