from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from standardwebhooks.webhooks import Webhook

from app.billing.models import BillingCustomer, ProcessedWebhookEvent
from tests.conftest import create_user

pytestmark = pytest.mark.anyio


def _sign(secret: str, webhook_id: str, timestamp: str, body: bytes) -> str:
    # Mirror how Polar signs deliveries: the SDK base64-encodes the whole
    # secret (whsec_ prefix included) before handing it to the Standard
    # Webhooks signer. ``Webhook.sign`` returns the full ``v1,<sig>`` value.
    webhook = Webhook(base64.b64encode(secret.encode()).decode())
    return webhook.sign(
        webhook_id,
        datetime.fromtimestamp(int(timestamp), tz=UTC),
        body.decode(),
    )


def _webhook_headers(secret: str, body: bytes, *, webhook_id: str) -> dict[str, str]:
    timestamp = str(int(datetime.now(UTC).timestamp()))
    return {
        "webhook-id": webhook_id,
        "webhook-timestamp": timestamp,
        "webhook-signature": _sign(secret, webhook_id, timestamp, body),
    }


class TestPolarWebhook:
    async def test_invalid_signature_rejected(
        self, client: AsyncClient, settings: Any
    ) -> None:
        settings.polar_webhook_secret = "whsec_" + base64.b64encode(b"secret").decode()
        body = json.dumps({"type": "subscription.created", "data": {}}).encode()
        response = await client.post(
            "/api/v1/billing/webhooks/polar",
            content=body,
            headers={
                "webhook-id": "msg_1",
                "webhook-timestamp": str(int(datetime.now(UTC).timestamp())),
                "webhook-signature": "v1,not-a-real-signature",
            },
        )
        assert response.status_code == 401

    async def test_valid_signature_updates_subscription(
        self, client: AsyncClient, settings: Any
    ) -> None:
        secret = "whsec_" + base64.b64encode(b"secret").decode()
        settings.polar_webhook_secret = secret

        user = await create_user()
        customer = await BillingCustomer(
            user_id=user.id, polar_customer_id="cus_webhook_test"
        ).insert()

        body = json.dumps(
            {
                "type": "subscription.active",
                "data": {
                    "id": "sub_1",
                    "status": "active",
                    "customer_id": "cus_webhook_test",
                },
            }
        ).encode()
        headers = _webhook_headers(secret, body, webhook_id="msg_valid_1")

        response = await client.post(
            "/api/v1/billing/webhooks/polar", content=body, headers=headers
        )
        assert response.status_code == 200

        updated = await BillingCustomer.find_one({"_id": customer.id})
        assert updated is not None
        assert updated.subscription_status == "active"
        assert updated.subscription_id == "sub_1"

    async def test_valid_signature_captures_product_id_for_tier_resolution(
        self, client: AsyncClient, settings: Any
    ) -> None:
        secret = "whsec_" + base64.b64encode(b"secret").decode()
        settings.polar_webhook_secret = secret

        user = await create_user()
        customer = await BillingCustomer(
            user_id=user.id, polar_customer_id="cus_product_test"
        ).insert()

        body = json.dumps(
            {
                "type": "subscription.active",
                "data": {
                    "id": "sub_2",
                    "status": "active",
                    "customer_id": "cus_product_test",
                    "product_id": settings.polar_max_product_id,
                },
            }
        ).encode()
        headers = _webhook_headers(secret, body, webhook_id="msg_product_1")

        response = await client.post(
            "/api/v1/billing/webhooks/polar", content=body, headers=headers
        )
        assert response.status_code == 200

        updated = await BillingCustomer.find_one({"_id": customer.id})
        assert updated is not None
        assert updated.product_id == settings.polar_max_product_id

    async def test_duplicate_webhook_id_is_a_no_op(
        self, client: AsyncClient, settings: Any
    ) -> None:
        secret = "whsec_" + base64.b64encode(b"secret").decode()
        settings.polar_webhook_secret = secret

        user = await create_user()
        await BillingCustomer(
            user_id=user.id, polar_customer_id="cus_dup_test"
        ).insert()

        body = json.dumps(
            {
                "type": "subscription.canceled",
                "data": {"customer_id": "cus_dup_test"},
            }
        ).encode()
        headers = _webhook_headers(secret, body, webhook_id="msg_dup_1")

        first = await client.post(
            "/api/v1/billing/webhooks/polar", content=body, headers=headers
        )
        second = await client.post(
            "/api/v1/billing/webhooks/polar", content=body, headers=headers
        )
        assert first.status_code == 200
        assert second.status_code == 200

        processed = await ProcessedWebhookEvent.find(
            {"webhook_id": "msg_dup_1"}
        ).to_list()
        assert len(processed) == 1
