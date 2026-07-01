from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from app.billing.exceptions import (
    UsageQuotaExceededError,
    WebhookSignatureInvalidError,
)
from app.billing.models import BillingCustomer, UsageAllowance, UsageEventLog
from app.billing.service import (
    check_quota_and_raise,
    create_checkout_session,
    create_customer_portal_session,
    emit_pending_usage_events_to_polar,
    get_or_create_polar_customer,
    record_usage_event,
    verify_webhook_signature,
)
from tests.billing.conftest import FakePolarClient
from tests.conftest import create_user

pytestmark = pytest.mark.anyio


class TestRecordUsageEvent:
    async def test_records_ledger_entry_and_bumps_allowance(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        await record_usage_event(
            user_id=user.id,
            quantity=100,
            idempotency_key=f"test:{uuid4()}",
        )
        allowance = await UsageAllowance.find_one({"user_id": user.id})
        assert allowance is not None
        assert allowance.llm_tokens_used == 100

    async def test_is_idempotent_on_duplicate_key(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        key = f"test:{uuid4()}"
        await record_usage_event(
            user_id=user.id,
            quantity=1,
            idempotency_key=key,
        )
        await record_usage_event(
            user_id=user.id,
            quantity=1,
            idempotency_key=key,
        )
        logs = await UsageEventLog.find({"idempotency_key": key}).to_list()
        assert len(logs) == 1
        allowance = await UsageAllowance.find_one({"user_id": user.id})
        assert allowance is not None
        assert allowance.llm_tokens_used == 1


class TestQuotaGating:
    async def test_blocks_when_free_tier_exceeded(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        await record_usage_event(
            user_id=user.id,
            quantity=settings.free_tier_llm_tokens_allowance,
            idempotency_key=f"test:{uuid4()}",
        )
        with pytest.raises(UsageQuotaExceededError):
            await check_quota_and_raise(user.id, 1, settings)

    async def test_allows_within_free_tier(self, app: Any, settings: Any) -> None:
        user = await create_user()
        await check_quota_and_raise(user.id, 1, settings)

    async def test_active_subscription_bypasses_gate(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        await BillingCustomer(
            user_id=user.id,
            polar_customer_id="cus_active",
            subscription_status="active",
        ).insert()
        await record_usage_event(
            user_id=user.id,
            quantity=settings.free_tier_llm_tokens_allowance + 5,
            idempotency_key=f"test:{uuid4()}",
        )
        await check_quota_and_raise(user.id, 1, settings)

    async def test_fails_open_on_internal_error(
        self, app: Any, settings: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A bug/outage inside billing's own quota check must never block
        chat or report generation for users still within their allowance -
        it should log and let the request through instead of raising.
        """
        user = await create_user()

        async def _boom(*args: object, **kwargs: object) -> None:
            raise RuntimeError("simulated Mongo outage")

        monkeypatch.setattr(BillingCustomer, "find_one", _boom)

        await check_quota_and_raise(user.id, 1, settings)


class TestPolarCustomerAndCheckout:
    async def test_get_or_create_polar_customer_is_idempotent(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        fake_client = FakePolarClient()
        first = await get_or_create_polar_customer(user, settings, client=fake_client)
        second = await get_or_create_polar_customer(user, settings, client=fake_client)
        assert first.id == second.id
        assert len(fake_client.created_customers) == 1

    async def test_create_checkout_session_returns_url(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        fake_client = FakePolarClient()
        url = await create_checkout_session(user, settings, client=fake_client)
        assert url == "https://sandbox.polar.sh/checkout/fake"
        assert len(fake_client.checkout_calls) == 1

    async def test_create_customer_portal_session_returns_url(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        fake_client = FakePolarClient()
        url = await create_customer_portal_session(user, settings, client=fake_client)
        assert url == "https://sandbox.polar.sh/portal/fake"


class TestUsageEmission:
    async def test_emits_pending_events_and_marks_ingested(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        await record_usage_event(
            user_id=user.id,
            quantity=42,
            idempotency_key=f"test:{uuid4()}",
        )
        fake_client = FakePolarClient()
        stats = await emit_pending_usage_events_to_polar(settings, client=fake_client)
        assert stats["ingested"] == 1
        assert len(fake_client.ingested_events) == 1
        remaining = await UsageEventLog.find({"polar_ingested": False}).to_list()
        assert remaining == []

    async def test_failed_ingestion_increments_retry_count(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        await record_usage_event(
            user_id=user.id,
            quantity=42,
            idempotency_key=f"test:{uuid4()}",
        )
        fake_client = FakePolarClient(fail_ingest=True)
        stats = await emit_pending_usage_events_to_polar(settings, client=fake_client)
        assert stats["failed"] == 1
        log = await UsageEventLog.find_one({"user_id": user.id})
        assert log is not None
        assert log.polar_ingested is False
        assert log.retry_count == 1


class TestWebhookSignatureVerification:
    def _sign(self, secret: str, webhook_id: str, timestamp: str, body: bytes) -> str:
        material = secret.removeprefix("whsec_")
        secret_bytes = base64.b64decode(material + "=" * (-len(material) % 4))
        signed_content = f"{webhook_id}.{timestamp}.{body.decode()}"
        signature = base64.b64encode(
            hmac.new(secret_bytes, signed_content.encode(), hashlib.sha256).digest()
        ).decode()
        return f"v1,{signature}"

    def test_valid_signature_passes(self) -> None:
        secret = "whsec_" + base64.b64encode(b"test-secret").decode()
        body = b'{"type": "subscription.created"}'
        webhook_id = "msg_1"
        timestamp = str(int(datetime.now(UTC).timestamp()))
        signature = self._sign(secret, webhook_id, timestamp, body)

        verify_webhook_signature(
            body,
            {
                "webhook-id": webhook_id,
                "webhook-timestamp": timestamp,
                "webhook-signature": signature,
            },
            secret,
        )

    def test_tampered_payload_rejected(self) -> None:
        secret = "whsec_" + base64.b64encode(b"test-secret").decode()
        body = b'{"type": "subscription.created"}'
        webhook_id = "msg_1"
        timestamp = str(int(datetime.now(UTC).timestamp()))
        signature = self._sign(secret, webhook_id, timestamp, body)

        with pytest.raises(WebhookSignatureInvalidError):
            verify_webhook_signature(
                b'{"type": "subscription.canceled"}',
                {
                    "webhook-id": webhook_id,
                    "webhook-timestamp": timestamp,
                    "webhook-signature": signature,
                },
                secret,
            )

    def test_valid_signature_passes_with_unpadded_secret(self) -> None:
        # Polar (like svix) issues webhook secrets as unpadded base64 -
        # regression coverage for the padding fix in verify_webhook_signature.
        raw_secret = base64.b64encode(b"x" * 32).decode().rstrip("=")
        secret = f"whsec_{raw_secret}"
        assert not raw_secret.endswith("=")

        body = b'{"type": "subscription.active"}'
        webhook_id = "msg_unpadded"
        timestamp = str(int(datetime.now(UTC).timestamp()))
        signature = self._sign(secret, webhook_id, timestamp, body)

        verify_webhook_signature(
            body,
            {
                "webhook-id": webhook_id,
                "webhook-timestamp": timestamp,
                "webhook-signature": signature,
            },
            secret,
        )

    def test_missing_headers_rejected(self) -> None:
        with pytest.raises(WebhookSignatureInvalidError):
            verify_webhook_signature(
                b"{}", {}, "whsec_" + base64.b64encode(b"x").decode()
            )
