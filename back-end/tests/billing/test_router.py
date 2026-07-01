from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.billing.models import BillingCustomer
from app.billing.service import record_usage_event
from tests.conftest import auth_headers, create_user

pytestmark = pytest.mark.anyio


class TestBillingRouter:
    async def test_checkout_requires_billing_configured(
        self, client: AsyncClient, settings: Any
    ) -> None:
        user = await create_user()
        headers = auth_headers(user, settings)
        response = await client.post(
            "/api/v1/billing/checkout", headers=headers, json={"tier": "pro"}
        )
        assert response.status_code == 503

    async def test_portal_requires_billing_configured(
        self, client: AsyncClient, settings: Any
    ) -> None:
        user = await create_user()
        headers = auth_headers(user, settings)
        response = await client.get("/api/v1/billing/portal", headers=headers)
        assert response.status_code == 503

    async def test_usage_summary_defaults_to_free_tier(
        self, client: AsyncClient, settings: Any
    ) -> None:
        user = await create_user()
        headers = auth_headers(user, settings)
        response = await client.get("/api/v1/billing/usage", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["llm_tokens_used"] == 0
        assert data["is_subscription_active"] is False
        assert data["llm_tokens_allowance"] == settings.free_tier_llm_tokens_allowance

    async def test_usage_summary_reflects_recorded_usage(
        self, client: AsyncClient, settings: Any
    ) -> None:
        user = await create_user()
        headers = auth_headers(user, settings)
        await record_usage_event(
            user_id=user.id,
            quantity=250,
            idempotency_key="test:router:usage",
        )
        response = await client.get("/api/v1/billing/usage", headers=headers)
        assert response.json()["llm_tokens_used"] == 250

    async def test_subscription_status_no_customer(
        self, client: AsyncClient, settings: Any
    ) -> None:
        user = await create_user()
        headers = auth_headers(user, settings)
        response = await client.get("/api/v1/billing/subscription", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["subscription_status"] is None

    async def test_subscription_status_with_active_customer(
        self, client: AsyncClient, settings: Any
    ) -> None:
        user = await create_user()
        headers = auth_headers(user, settings)
        await BillingCustomer(
            user_id=user.id,
            polar_customer_id="cus_test",
            subscription_status="active",
        ).insert()
        response = await client.get("/api/v1/billing/subscription", headers=headers)
        assert response.json()["subscription_status"] == "active"

    async def test_billing_endpoints_require_auth(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/billing/usage")
        assert response.status_code == 401
