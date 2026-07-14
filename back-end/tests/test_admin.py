from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.billing.models import BillingCustomer, UsageAllowance, UsageEventLog
from app.notebooks.models import (
    NotebookDocument,
    NotebookDocumentChunk,
    NotebookReport,
)
from app.users.models import User
from tests.conftest import auth_headers, create_notebook, create_user

pytestmark = pytest.mark.anyio


async def create_usage_event(
    user: User, quantity: int, created_at: datetime | None = None
) -> UsageEventLog:
    event = UsageEventLog(
        user_id=user.id,
        quantity=quantity,
        idempotency_key=str(uuid4()),
    )
    if created_at is not None:
        event.created_at = created_at
    await event.insert()
    return event


async def create_document(user: User, status: str = "pending") -> NotebookDocument:
    notebook = await create_notebook(user)
    document = NotebookDocument(
        notebook_id=notebook.id,
        user_id=user.id,
        filename=f"{uuid4()}.txt",
        content_type="text/plain",
        size=10,
        status=status,
        content="secret document body",
    )
    await document.insert()
    return document


async def create_billing_customer(
    user: User,
    subscription_status: str | None = "active",
    product_id: str | None = "test_pro_product",
) -> BillingCustomer:
    customer = BillingCustomer(
        user_id=user.id,
        polar_customer_id=str(uuid4()),
        subscription_status=subscription_status,
        product_id=product_id,
    )
    await customer.insert()
    return customer


class TestAdminAuth:
    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/admin/stats",
            "/api/v1/admin/usage/daily",
            "/api/v1/admin/users",
            "/api/v1/admin/documents",
            "/api/v1/admin/billing/summary",
        ],
    )
    async def test_auth_matrix(
        self, client: AsyncClient, settings: Any, path: str
    ) -> None:
        assert (await client.get(path)).status_code == 401

        user = await create_user(role="user")
        response = await client.get(path, headers=auth_headers(user, settings))
        assert response.status_code == 403

        admin = await create_user(role="admin")
        response = await client.get(path, headers=auth_headers(admin, settings))
        assert response.status_code == 200


class TestAdminStats:
    async def test_stats_counts(self, client: AsyncClient, settings: Any) -> None:
        admin = await create_user(role="admin")
        user = await create_user(role="user")
        inactive = await create_user(role="user")
        inactive.is_active = False
        await inactive.save()

        await create_notebook(user)
        await create_document(user, status="indexed")
        await create_document(user, status="failed")
        await create_document(user, status="failed")

        notebook = await create_notebook(user)
        await NotebookReport(
            notebook_id=notebook.id, user_id=user.id, report_type="summary"
        ).insert()

        await create_usage_event(user, 100)
        await create_usage_event(user, 250)
        await create_billing_customer(user, subscription_status="active")

        response = await client.get(
            "/api/v1/admin/stats", headers=auth_headers(admin, settings)
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_users"] == 3
        assert data["active_users"] == 2
        # create_document creates a notebook per document (3) + 2 explicit ones
        assert data["total_notebooks"] == 5
        assert data["documents_by_status"] == {"indexed": 1, "failed": 2}
        assert data["reports_by_status"] == {"pending": 1}
        assert data["tokens_this_month"] == 350
        assert data["active_subscriptions"] == 1


class TestAdminDailyUsage:
    async def test_daily_grouping(self, client: AsyncClient, settings: Any) -> None:
        admin = await create_user(role="admin")
        user = await create_user(role="user")

        now = datetime.now(UTC)
        yesterday = now - timedelta(days=1)
        await create_usage_event(user, 10, created_at=now)
        await create_usage_event(user, 20, created_at=now)
        await create_usage_event(user, 5, created_at=yesterday)
        # Outside the requested window
        await create_usage_event(user, 999, created_at=now - timedelta(days=40))

        response = await client.get(
            "/api/v1/admin/usage/daily?days=30",
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 200
        points = response.json()
        by_date = {point["date"]: point["tokens"] for point in points}
        assert by_date[now.strftime("%Y-%m-%d")] == 30
        assert by_date[yesterday.strftime("%Y-%m-%d")] == 5
        assert now.strftime("%Y-%m-%d") not in [
            p["date"] for p in points if p["tokens"] == 999
        ]
        assert [p["date"] for p in points] == sorted(p["date"] for p in points)

    async def test_days_clamped(self, client: AsyncClient, settings: Any) -> None:
        admin = await create_user(role="admin")
        headers = auth_headers(admin, settings)
        assert (
            await client.get("/api/v1/admin/usage/daily?days=0", headers=headers)
        ).status_code == 422
        assert (
            await client.get("/api/v1/admin/usage/daily?days=400", headers=headers)
        ).status_code == 422


class TestAdminUsers:
    async def test_pagination(self, client: AsyncClient, settings: Any) -> None:
        admin = await create_user(role="admin")
        for _ in range(5):
            await create_user(role="user")

        headers = auth_headers(admin, settings)
        response = await client.get(
            "/api/v1/admin/users?page=1&page_size=4", headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 6
        assert data["page"] == 1
        assert data["page_size"] == 4
        assert len(data["items"]) == 4

        response = await client.get(
            "/api/v1/admin/users?page=2&page_size=4", headers=headers
        )
        assert len(response.json()["items"]) == 2

    async def test_search(self, client: AsyncClient, settings: Any) -> None:
        admin = await create_user(role="admin")
        await create_user(email="findme@example.com")
        await create_user(email="other@example.com")

        response = await client.get(
            "/api/v1/admin/users?search=FINDME",
            headers=auth_headers(admin, settings),
        )
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["email"] == "findme@example.com"

    async def test_enrichment(self, client: AsyncClient, settings: Any) -> None:
        admin = await create_user(role="admin")
        user = await create_user(email="paying@example.com")
        await create_billing_customer(
            user, subscription_status="active", product_id="test_pro_product"
        )
        now = datetime.now(UTC)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        await UsageAllowance(
            user_id=user.id,
            period_start=period_start,
            period_end=period_start + timedelta(days=32),
            llm_tokens_used=1234,
        ).insert()

        response = await client.get(
            "/api/v1/admin/users?search=paying",
            headers=auth_headers(admin, settings),
        )
        row = response.json()["items"][0]
        assert row["subscription_status"] == "active"
        assert row["product_id"] == "test_pro_product"
        assert row["tokens_used_this_period"] == 1234


class TestAdminUserUpdate:
    async def test_role_change_persists(
        self, client: AsyncClient, settings: Any
    ) -> None:
        admin = await create_user(role="admin")
        user = await create_user(role="user")

        response = await client.patch(
            f"/api/v1/admin/users/{user.id}",
            json={"role": "admin"},
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 200
        assert response.json()["role"] == "admin"
        updated = await User.find_one({"_id": user.id})
        assert updated is not None
        assert updated.role == "admin"

    async def test_deactivate_persists(
        self, client: AsyncClient, settings: Any
    ) -> None:
        admin = await create_user(role="admin")
        user = await create_user(role="user")

        response = await client.patch(
            f"/api/v1/admin/users/{user.id}",
            json={"is_active": False},
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False
        updated = await User.find_one({"_id": user.id})
        assert updated is not None
        assert updated.is_active is False

    async def test_self_demotion_forbidden(
        self, client: AsyncClient, settings: Any
    ) -> None:
        admin = await create_user(role="admin")
        response = await client.patch(
            f"/api/v1/admin/users/{admin.id}",
            json={"role": "user"},
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 403

    async def test_self_deactivate_forbidden(
        self, client: AsyncClient, settings: Any
    ) -> None:
        admin = await create_user(role="admin")
        response = await client.patch(
            f"/api/v1/admin/users/{admin.id}",
            json={"is_active": False},
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 403

    async def test_unknown_user_404(self, client: AsyncClient, settings: Any) -> None:
        admin = await create_user(role="admin")
        response = await client.patch(
            f"/api/v1/admin/users/{uuid4()}",
            json={"role": "user"},
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 404

    async def test_bad_role_422(self, client: AsyncClient, settings: Any) -> None:
        admin = await create_user(role="admin")
        user = await create_user(role="user")
        response = await client.patch(
            f"/api/v1/admin/users/{user.id}",
            json={"role": "superuser"},
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 422

    async def test_non_admin_forbidden(
        self, client: AsyncClient, settings: Any
    ) -> None:
        user = await create_user(role="user")
        other = await create_user(role="user")
        response = await client.patch(
            f"/api/v1/admin/users/{other.id}",
            json={"role": "admin"},
            headers=auth_headers(user, settings),
        )
        assert response.status_code == 403


class TestAdminUserUsage:
    async def test_usage_summary(self, client: AsyncClient, settings: Any) -> None:
        admin = await create_user(role="admin")
        user = await create_user(role="user")
        response = await client.get(
            f"/api/v1/admin/users/{user.id}/usage",
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["llm_tokens_used"] == 0
        assert "tier" in data

    async def test_unknown_user_404(self, client: AsyncClient, settings: Any) -> None:
        admin = await create_user(role="admin")
        response = await client.get(
            f"/api/v1/admin/users/{uuid4()}/usage",
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 404


class TestAdminDocuments:
    async def test_status_filter_and_no_content_leak(
        self, client: AsyncClient, settings: Any
    ) -> None:
        admin = await create_user(role="admin")
        user = await create_user(role="user")
        await create_document(user, status="indexed")
        failed = await create_document(user, status="failed")

        response = await client.get(
            "/api/v1/admin/documents?status=failed",
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(failed.id)
        assert "content" not in data["items"][0]

    async def test_sorted_desc(self, client: AsyncClient, settings: Any) -> None:
        admin = await create_user(role="admin")
        user = await create_user(role="user")
        first = await create_document(user)
        second = await create_document(user)
        second.created_at = first.created_at + timedelta(minutes=1)
        await second.save()

        response = await client.get(
            "/api/v1/admin/documents", headers=auth_headers(admin, settings)
        )
        items = response.json()["items"]
        assert [item["id"] for item in items] == [str(second.id), str(first.id)]

    async def test_filename_search(self, client: AsyncClient, settings: Any) -> None:
        admin = await create_user(role="admin")
        user = await create_user(role="user")
        target = await create_document(user)
        target.filename = "annual-report.pdf"
        await target.save()
        other = await create_document(user)
        other.filename = "notes.txt"
        await other.save()

        response = await client.get(
            "/api/v1/admin/documents?search=annual",
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(target.id)


class TestAdminDocumentPreview:
    async def test_text_preview(self, client: AsyncClient, settings: Any) -> None:
        admin = await create_user(role="admin")
        user = await create_user(role="user")
        document = await create_document(user)

        response = await client.get(
            f"/api/v1/admin/documents/{document.id}/preview",
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["preview_type"] == "text"
        assert data["content"] == "secret document body"

    async def test_s3_text_file_rendered_as_text(
        self, client: AsyncClient, settings: Any, monkeypatch: Any
    ) -> None:
        # Markdown/plain-text uploads live in S3 (no inline `content`) and the
        # udoc-viewer cannot render them, so they must come back as text.
        from app.admin import service as admin_service

        async def fake_load_document_bytes(_document: Any, _settings: Any) -> bytes:
            return b"# Heading\n\nbody"

        monkeypatch.setattr(
            admin_service, "load_document_bytes", fake_load_document_bytes
        )
        admin = await create_user(role="admin")
        user = await create_user(role="user")
        notebook = await create_notebook(user)
        document = NotebookDocument(
            notebook_id=notebook.id,
            user_id=user.id,
            s3_bucket="bucket",
            s3_key="users/notes.md",
            filename="notes.md",
            content_type="text/markdown",
            size=15,
            status="indexed",
        )
        await document.insert()

        response = await client.get(
            f"/api/v1/admin/documents/{document.id}/preview",
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["preview_type"] == "text"
        assert data["content"] == "# Heading\n\nbody"
        assert data["url"] is None

    async def test_binary_file_rendered_as_url(
        self, client: AsyncClient, settings: Any, monkeypatch: Any
    ) -> None:
        # PDFs/docx/images go to the udoc-viewer via a presigned URL.
        from app.admin import service as admin_service

        async def fake_head_async(_store: Any, _key: str) -> dict[str, Any]:
            return {"size": 123}

        monkeypatch.setattr(admin_service.obstore, "head_async", fake_head_async)
        monkeypatch.setattr(
            admin_service,
            "generate_presigned_get_url",
            lambda _settings, *, key, expires_in: "http://minio/presigned.pdf",
        )
        admin = await create_user(role="admin")
        user = await create_user(role="user")
        notebook = await create_notebook(user)
        document = NotebookDocument(
            notebook_id=notebook.id,
            user_id=user.id,
            s3_bucket="bucket",
            s3_key="users/report.pdf",
            filename="report.pdf",
            content_type="application/pdf",
            size=123,
            status="indexed",
        )
        await document.insert()

        response = await client.get(
            f"/api/v1/admin/documents/{document.id}/preview",
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["preview_type"] == "url"
        assert data["url"] == "http://minio/presigned.pdf"

    async def test_missing_object_returns_404(
        self, client: AsyncClient, settings: Any, monkeypatch: Any
    ) -> None:
        # A DB row can outlive its S3 object (upload never finished, object
        # removed out-of-band). The preview must 404 rather than sign a URL to
        # a missing object that would 404 inside the viewer instead.
        from app.admin import service as admin_service

        async def fake_head_async(_store: Any, _key: str) -> dict[str, Any]:
            raise FileNotFoundError

        monkeypatch.setattr(admin_service.obstore, "head_async", fake_head_async)
        admin = await create_user(role="admin")
        user = await create_user(role="user")
        notebook = await create_notebook(user)
        document = NotebookDocument(
            notebook_id=notebook.id,
            user_id=user.id,
            s3_bucket="bucket",
            s3_key="users/missing.pdf",
            filename="missing.pdf",
            content_type="application/pdf",
            size=123,
            status="uploaded",
        )
        await document.insert()

        response = await client.get(
            f"/api/v1/admin/documents/{document.id}/preview",
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 404

    async def test_unknown_document_404(
        self, client: AsyncClient, settings: Any
    ) -> None:
        admin = await create_user(role="admin")
        response = await client.get(
            f"/api/v1/admin/documents/{uuid4()}/preview",
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 404


class TestAdminDocumentUpdate:
    async def test_update_persists(self, client: AsyncClient, settings: Any) -> None:
        admin = await create_user(role="admin")
        user = await create_user(role="user")
        document = await create_document(user, status="failed")

        response = await client.patch(
            f"/api/v1/admin/documents/{document.id}",
            json={"filename": "renamed.txt", "status": "indexed"},
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "renamed.txt"
        assert data["status"] == "indexed"

        refreshed = await NotebookDocument.find_one({"_id": document.id})
        assert refreshed is not None
        assert refreshed.filename == "renamed.txt"
        assert refreshed.status == "indexed"

    async def test_bad_status_422(self, client: AsyncClient, settings: Any) -> None:
        admin = await create_user(role="admin")
        user = await create_user(role="user")
        document = await create_document(user)
        response = await client.patch(
            f"/api/v1/admin/documents/{document.id}",
            json={"status": "bogus"},
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 422

    async def test_unknown_document_404(
        self, client: AsyncClient, settings: Any
    ) -> None:
        admin = await create_user(role="admin")
        response = await client.patch(
            f"/api/v1/admin/documents/{uuid4()}",
            json={"filename": "x.txt"},
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 404


class TestAdminDocumentDelete:
    async def test_delete_removes_document_and_chunks(
        self, client: AsyncClient, settings: Any
    ) -> None:
        admin = await create_user(role="admin")
        user = await create_user(role="user")
        document = await create_document(user)
        chunk = NotebookDocumentChunk(
            notebook_id=document.notebook_id,
            document_id=document.id,
            user_id=user.id,
            content="chunk text",
            chunk_index=0,
            embedding=[0.0] * 1536,
        )
        await chunk.insert()

        response = await client.delete(
            f"/api/v1/admin/documents/{document.id}",
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 204
        assert await NotebookDocument.find_one({"_id": document.id}) is None
        assert (
            await NotebookDocumentChunk.find({"document_id": document.id}).count() == 0
        )

    async def test_unknown_document_404(
        self, client: AsyncClient, settings: Any
    ) -> None:
        admin = await create_user(role="admin")
        response = await client.delete(
            f"/api/v1/admin/documents/{uuid4()}",
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 404


class TestAdminTransactions:
    async def test_lists_events_desc(self, client: AsyncClient, settings: Any) -> None:
        admin = await create_user(role="admin")
        user = await create_user(role="user")
        now = datetime.now(UTC)
        older = await create_usage_event(user, 100, now - timedelta(hours=1))
        newer = await create_usage_event(user, 250, now)

        response = await client.get(
            "/api/v1/admin/transactions",
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert [item["id"] for item in data["items"]] == [
            str(newer.id),
            str(older.id),
        ]
        assert data["items"][0]["quantity"] == 250

    async def test_filter_by_user(self, client: AsyncClient, settings: Any) -> None:
        admin = await create_user(role="admin")
        user = await create_user(role="user")
        other = await create_user(role="user")
        await create_usage_event(user, 10)
        await create_usage_event(other, 20)

        response = await client.get(
            f"/api/v1/admin/transactions?user_id={user.id}",
            headers=auth_headers(admin, settings),
        )
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["user_id"] == str(user.id)


class TestAdminOrders:
    async def test_not_configured(
        self, client: AsyncClient, settings: Any, monkeypatch: Any
    ) -> None:
        monkeypatch.setattr(settings, "polar_api_key", "")
        admin = await create_user(role="admin")
        response = await client.get(
            "/api/v1/admin/orders", headers=auth_headers(admin, settings)
        )
        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is False
        assert data["items"] == []

    async def test_maps_polar_orders(
        self, client: AsyncClient, settings: Any, monkeypatch: Any
    ) -> None:
        monkeypatch.setattr(settings, "polar_api_key", "test-key")

        class FakePolarClient:
            async def list_orders(
                self, *, page: int, limit: int, organization_id: str | None
            ) -> dict[str, Any]:
                return {
                    "items": [
                        {
                            "id": "ord_123",
                            "net_amount": 1999,
                            "currency": "usd",
                            "status": "paid",
                            "product_id": "prod_1",
                            "created_at": "2026-07-01T00:00:00Z",
                            "customer": {"email": "buyer@example.com"},
                        }
                    ],
                    "pagination": {"total_count": 1},
                }

        monkeypatch.setattr(
            "app.admin.service.get_polar_client", lambda _settings: FakePolarClient()
        )
        admin = await create_user(role="admin")
        response = await client.get(
            "/api/v1/admin/orders", headers=auth_headers(admin, settings)
        )
        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is True
        assert data["total"] == 1
        order = data["items"][0]
        assert order["id"] == "ord_123"
        assert order["amount"] == 1999
        assert order["customer_email"] == "buyer@example.com"


class TestAdminBillingSummary:
    async def test_grouping(self, client: AsyncClient, settings: Any) -> None:
        admin = await create_user(role="admin")
        users = [await create_user() for _ in range(4)]
        await create_billing_customer(users[0], "active", "test_pro_product")
        await create_billing_customer(users[1], "active", "test_max_product")
        await create_billing_customer(users[2], "canceled", "test_pro_product")
        await create_billing_customer(users[3], None, None)

        response = await client.get(
            "/api/v1/admin/billing/summary",
            headers=auth_headers(admin, settings),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_customers"] == 4
        assert data["by_status"] == {"active": 2, "canceled": 1}
        assert data["by_product"] == {"test_pro_product": 2, "test_max_product": 1}
