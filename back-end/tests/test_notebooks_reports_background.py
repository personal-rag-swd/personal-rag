"""Tests for background report generation, cancellation, and crash recovery."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.security import create_access_token
from app.main import app
from app.notebooks.models import (
    Notebook,
    NotebookDocument,
    NotebookDocumentChunk,
    NotebookReport,
)
from app.notebooks.report_service import run_report_generation
from app.users.models import User

# Shared PostgreSQL engine for all tests in this module
_shared_engine = create_engine(
    os.environ["DATABASE_URL"],
    pool_pre_ping=True,
)


@pytest.fixture
def session() -> Generator[Session]:
    with Session(_shared_engine) as s:
        yield s


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url=os.environ["DATABASE_URL"],
        jwt_secret_key="test-secret-with-at-least-32-bytes",
        jwt_algorithm="HS256",
    )


@pytest.fixture
def client(settings: Settings, session: Session) -> Generator[TestClient]:
    def override_get_settings() -> Settings:
        return settings

    def override_get_session() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_user(email: str) -> User:
    return User(id=uuid4(), email=email, hashed_password="hashed-pw")


def auth_headers(user: User, settings: Settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user, settings)}"}


def _create_notebook(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/notebooks/",
        json={"name": "Test NB", "description": "", "tags": []},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _add_indexed_chunk(session: Session, notebook_id: UUID, user_id: UUID) -> None:
    doc = NotebookDocument(
        notebook_id=notebook_id,
        user_id=user_id,
        s3_bucket="test",
        s3_key=f"key-{uuid4()}",
        filename="source.txt",
        status="indexed",
    )
    session.add(doc)
    session.commit()
    session.add(
        NotebookDocumentChunk(
            document_id=doc.id,
            chunk_index=0,
            content="Indexed source content about the project.",
            embedding=[0.0] * 1536,
        )
    )
    session.commit()


# ---------------------------------------------------------------------------
# POST returns immediately with status=pending
# ---------------------------------------------------------------------------


def test_report_post_returns_pending(
    client: TestClient,
    settings: Settings,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /reports should return 201 with status=pending and empty content."""
    user = make_user("bg1@example.com")
    session.add(user)
    session.commit()
    headers = auth_headers(user, settings)
    notebook_id = _create_notebook(client, headers)
    _add_indexed_chunk(session, UUID(notebook_id), user.id)

    monkeypatch.setattr(
        "app.notebooks.report_service.chat_provider_is_configured", lambda: True
    )

    async def noop_gen(context: str, instructions: str | None = None):
        from app.notebooks.schemas import BriefingDocReport

        return BriefingDocReport(
            executive_summary="s", key_takeaways=[], strategic_implications=[]
        )

    monkeypatch.setattr("app.notebooks.report_service.generate_briefing_doc", noop_gen)

    resp = client.post(
        f"/api/v1/notebooks/{notebook_id}/reports",
        json={"report_type": "briefing"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    assert body["content"] == {}
    assert body["report_type"] == "briefing"

    # Verify the report was persisted (may have transitioned by background task)
    report = session.get(NotebookReport, UUID(body["id"]))
    assert report is not None
    assert report.report_type == "briefing"


# ---------------------------------------------------------------------------
# Background task transitions: pending -> generating -> completed
# ---------------------------------------------------------------------------


async def test_background_task_completes_successfully(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user("bg2@example.com")
    session.add(user)
    session.commit()

    notebook = Notebook(user_id=user.id, name="NB", description="", tags=[])
    session.add(notebook)
    session.commit()

    # Create report directly in _shared_engine so run_report_generation can find it
    with Session(_shared_engine) as shared_session:
        report = NotebookReport(
            notebook_id=notebook.id,
            user_id=user.id,
            report_type="briefing",
            status="pending",
            content={},
        )
        shared_session.add(report)
        shared_session.commit()
        shared_session.refresh(report)
        report_id = report.id

    async def fake_briefing(context: str, instructions: str | None = None):
        from app.notebooks.schemas import BriefingDocReport

        return BriefingDocReport(
            executive_summary="Done",
            key_takeaways=["k1"],
            strategic_implications=["s1"],
        )

    monkeypatch.setattr(
        "app.notebooks.report_service.generate_briefing_doc", fake_briefing
    )

    await run_report_generation(
        report_id=report_id,
        report_type="briefing",
        context="some context",
        instructions=None,
        detail_level=None,
        _engine=_shared_engine,
    )

    with Session(_shared_engine) as check:
        result = check.get(NotebookReport, report_id)
        assert result is not None
        assert result.status == "completed"
        assert result.content["executive_summary"] == "Done"
        assert result.error_message is None


# ---------------------------------------------------------------------------
# Background task on failure: pending -> generating -> failed
# ---------------------------------------------------------------------------


async def test_background_task_sets_failed_on_error(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user("bg3@example.com")
    session.add(user)
    session.commit()

    notebook = Notebook(user_id=user.id, name="NB", description="", tags=[])
    session.add(notebook)
    session.commit()

    with Session(_shared_engine) as shared_session:
        report = NotebookReport(
            notebook_id=notebook.id,
            user_id=user.id,
            report_type="briefing",
            status="pending",
            content={},
        )
        shared_session.add(report)
        shared_session.commit()
        shared_session.refresh(report)
        report_id = report.id

    async def failing_gen(context: str, instructions: str | None = None):
        raise RuntimeError("LLM exploded")

    monkeypatch.setattr(
        "app.notebooks.report_service.generate_briefing_doc", failing_gen
    )

    await run_report_generation(
        report_id=report_id,
        report_type="briefing",
        context="some context",
        instructions=None,
        detail_level=None,
        _engine=_shared_engine,
    )

    with Session(_shared_engine) as check:
        result = check.get(NotebookReport, report_id)
        assert result is not None
        assert result.status == "failed"
        assert "unexpected error" in result.error_message.lower()


# ---------------------------------------------------------------------------
# Cancel: pending -> cancelled
# ---------------------------------------------------------------------------


def test_cancel_pending_report(
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("cancel1@example.com")
    session.add(user)
    session.commit()
    headers = auth_headers(user, settings)
    notebook_id = _create_notebook(client, headers)

    report = NotebookReport(
        notebook_id=UUID(notebook_id),
        user_id=user.id,
        report_type="briefing",
        status="pending",
        content={},
    )
    session.add(report)
    session.commit()
    session.refresh(report)

    resp = client.post(
        f"/api/v1/notebooks/{notebook_id}/reports/{report.id}/cancel",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_cancel_generating_report(
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("cancel2@example.com")
    session.add(user)
    session.commit()
    headers = auth_headers(user, settings)
    notebook_id = _create_notebook(client, headers)

    report = NotebookReport(
        notebook_id=UUID(notebook_id),
        user_id=user.id,
        report_type="briefing",
        status="generating",
        content={},
    )
    session.add(report)
    session.commit()
    session.refresh(report)

    resp = client.post(
        f"/api/v1/notebooks/{notebook_id}/reports/{report.id}/cancel",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_cancel_completed_report_returns_409(
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("cancel3@example.com")
    session.add(user)
    session.commit()
    headers = auth_headers(user, settings)
    notebook_id = _create_notebook(client, headers)

    report = NotebookReport(
        notebook_id=UUID(notebook_id),
        user_id=user.id,
        report_type="briefing",
        status="completed",
        content={"executive_summary": "done"},
    )
    session.add(report)
    session.commit()
    session.refresh(report)

    resp = client.post(
        f"/api/v1/notebooks/{notebook_id}/reports/{report.id}/cancel",
        headers=headers,
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Cancel prevents LLM call from executing
# ---------------------------------------------------------------------------


async def test_cancel_prevents_generation(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user("cancel4@example.com")
    session.add(user)
    session.commit()

    notebook = Notebook(user_id=user.id, name="NB", description="", tags=[])
    session.add(notebook)
    session.commit()

    with Session(_shared_engine) as shared_session:
        report = NotebookReport(
            notebook_id=notebook.id,
            user_id=user.id,
            report_type="briefing",
            status="cancelled",
            content={},
        )
        shared_session.add(report)
        shared_session.commit()
        shared_session.refresh(report)
        report_id = report.id

    called = False

    async def should_not_be_called(context: str, instructions: str | None = None):
        nonlocal called
        called = True
        from app.notebooks.schemas import BriefingDocReport

        return BriefingDocReport(
            executive_summary="x", key_takeaways=[], strategic_implications=[]
        )

    monkeypatch.setattr(
        "app.notebooks.report_service.generate_briefing_doc", should_not_be_called
    )

    await run_report_generation(
        report_id=report_id,
        report_type="briefing",
        context="ctx",
        instructions=None,
        detail_level=None,
        _engine=_shared_engine,
    )

    assert not called, "LLM should not be called for a cancelled report"

    with Session(_shared_engine) as check:
        result = check.get(NotebookReport, report_id)
        assert result.status == "cancelled"
        assert result.content == {}


# ---------------------------------------------------------------------------
# Report status is constrained
# ---------------------------------------------------------------------------


def test_report_status_is_constrained(session: Session) -> None:
    user = make_user("status@example.com")
    session.add(user)
    session.commit()

    notebook = Notebook(user_id=user.id, name="NB", description="", tags=[])
    session.add(notebook)
    session.commit()

    session.add(
        NotebookReport(
            notebook_id=notebook.id,
            user_id=user.id,
            report_type="briefing",
            status="invalid_status",
            content={},
        )
    )
    with pytest.raises(Exception):  # noqa: B017
        session.commit()
    session.rollback()


# ---------------------------------------------------------------------------
# List endpoint includes status field
# ---------------------------------------------------------------------------


def test_list_reports_includes_status(
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("list1@example.com")
    session.add(user)
    session.commit()
    headers = auth_headers(user, settings)
    notebook_id = _create_notebook(client, headers)

    report = NotebookReport(
        notebook_id=UUID(notebook_id),
        user_id=user.id,
        report_type="briefing",
        status="completed",
        content={"executive_summary": "ok"},
    )
    session.add(report)
    session.commit()

    resp = client.get(
        f"/api/v1/notebooks/{notebook_id}/reports",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "completed"
    assert body[0]["error_message"] is None


# ---------------------------------------------------------------------------
# GET single report includes status
# ---------------------------------------------------------------------------


def test_get_report_includes_status(
    client: TestClient,
    settings: Settings,
    session: Session,
) -> None:
    user = make_user("get1@example.com")
    session.add(user)
    session.commit()
    headers = auth_headers(user, settings)
    notebook_id = _create_notebook(client, headers)

    report = NotebookReport(
        notebook_id=UUID(notebook_id),
        user_id=user.id,
        report_type="blog",
        status="failed",
        error_message="Rate limited",
        content={},
    )
    session.add(report)
    session.commit()
    session.refresh(report)

    resp = client.get(
        f"/api/v1/notebooks/{notebook_id}/reports/{report.id}",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["error_message"] == "Rate limited"


# ---------------------------------------------------------------------------
# Crash recovery: _recover_pending_reports re-queues stuck reports
# ---------------------------------------------------------------------------


async def test_crash_recovery_requeues_pending_reports(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.core.database as db_mod
    from app.main import _recover_pending_reports

    monkeypatch.setattr(db_mod, "engine", _shared_engine)

    user = make_user("recover@example.com")
    session.add(user)
    session.commit()

    notebook = Notebook(user_id=user.id, name="NB", description="", tags=[])
    session.add(notebook)
    session.commit()

    doc = NotebookDocument(
        notebook_id=notebook.id,
        user_id=user.id,
        s3_bucket="test",
        s3_key=f"key-{uuid4()}",
        filename="src.txt",
        status="indexed",
    )
    session.add(doc)
    session.commit()
    session.add(
        NotebookDocumentChunk(
            document_id=doc.id,
            chunk_index=0,
            content="Recovery context.",
            embedding=[0.0] * 1536,
        )
    )
    session.commit()

    report = NotebookReport(
        notebook_id=notebook.id,
        user_id=user.id,
        report_type="briefing",
        status="pending",
        additional_instructions="Focus on Q4",
        detail_level="detailed",
        content={},
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    report_id = report.id

    async def noop_gen(context: str, instructions: str | None = None):
        from app.notebooks.schemas import BriefingDocReport

        return BriefingDocReport(
            executive_summary="s", key_takeaways=[], strategic_implications=[]
        )

    monkeypatch.setattr("app.notebooks.report_service.generate_briefing_doc", noop_gen)

    captured_tasks: list = []

    def mock_create_task(coro):
        task = asyncio.ensure_future(coro)
        captured_tasks.append(task)
        return task

    monkeypatch.setattr("asyncio.create_task", mock_create_task)

    await _recover_pending_reports()

    assert len(captured_tasks) == 1

    # Let the background task run and verify the report is completed
    await asyncio.gather(*captured_tasks, return_exceptions=True)

    session.expire_all()
    result = session.get(NotebookReport, report_id)
    assert result is not None
    assert result.additional_instructions == "Focus on Q4"
    assert result.detail_level == "detailed"


async def test_crash_recovery_resets_generating_to_pending(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reports stuck in 'generating' should be reset to 'pending' on recovery."""
    import app.core.database as db_mod
    from app.main import _recover_pending_reports

    monkeypatch.setattr(db_mod, "engine", _shared_engine)

    user = make_user("recover2@example.com")
    session.add(user)
    session.commit()

    notebook = Notebook(user_id=user.id, name="NB", description="", tags=[])
    session.add(notebook)
    session.commit()

    doc = NotebookDocument(
        notebook_id=notebook.id,
        user_id=user.id,
        s3_bucket="test",
        s3_key=f"key-{uuid4()}",
        filename="src.txt",
        status="indexed",
    )
    session.add(doc)
    session.commit()
    session.add(
        NotebookDocumentChunk(
            document_id=doc.id,
            chunk_index=0,
            content="Context.",
            embedding=[0.0] * 1536,
        )
    )
    session.commit()

    report = NotebookReport(
        notebook_id=notebook.id,
        user_id=user.id,
        report_type="blog",
        status="generating",
        content={},
    )
    session.add(report)
    session.commit()
    session.refresh(report)

    async def noop_gen(context: str, instructions: str | None = None):
        from app.notebooks.schemas import BlogPostReport

        return BlogPostReport(title="t", hook="h", markdown_body="b")

    monkeypatch.setattr("app.notebooks.report_service.generate_blog_post", noop_gen)
    monkeypatch.setattr("asyncio.create_task", lambda coro: asyncio.ensure_future(coro))

    await _recover_pending_reports()

    session.expire_all()
    result = session.get(NotebookReport, report.id)
    assert result.status == "pending"
