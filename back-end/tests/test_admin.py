from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.billing.models import BillingCustomer, UsageAllowance, UsageEventLog
from app.notebooks.models import NotebookDocument, NotebookReport
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
