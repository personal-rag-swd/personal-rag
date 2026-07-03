from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from app.billing.exceptions import (
    NoActiveBillingCustomerError,
    UsageQuotaExceededError,
    WebhookSignatureInvalidError,
)
from app.billing.models import (
    BillingCustomer,
    UsageAllowance,
    UsageEventLog,
    UsageWindowCounter,
)
from app.billing.service import (
    change_subscription_plan,
    check_quota_and_raise,
    create_checkout_session,
    create_customer_portal_session,
    emit_pending_usage_events_to_polar,
    get_or_create_polar_customer,
    get_or_create_window_counter,
    get_usage_summary,
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
            settings=settings,
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
            settings=settings,
        )
        await record_usage_event(
            user_id=user.id,
            quantity=1,
            idempotency_key=key,
            settings=settings,
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
            settings=settings,
        )
        with pytest.raises(UsageQuotaExceededError):
            await check_quota_and_raise(user.id, 1, settings)

    async def test_allows_within_free_tier(self, app: Any, settings: Any) -> None:
        user = await create_user()
        await check_quota_and_raise(user.id, 1, settings)

    async def test_pro_tier_allows_usage_above_free_tier_cap(
        self, app: Any, settings: Any
    ) -> None:
        """A Pro subscriber isn't blocked by the free-tier cap, but does
        have their own (much larger) tier cap - subscribing isn't unlimited.
        """
        user = await create_user()
        await BillingCustomer(
            user_id=user.id,
            polar_customer_id="cus_pro",
            subscription_status="active",
            product_id=settings.polar_pro_product_id,
        ).insert()
        await record_usage_event(
            user_id=user.id,
            quantity=settings.free_tier_llm_tokens_allowance + 5,
            idempotency_key=f"test:{uuid4()}",
            settings=settings,
        )
        await check_quota_and_raise(user.id, 1, settings)

    async def test_pro_tier_blocks_once_its_own_cap_is_exceeded(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        await BillingCustomer(
            user_id=user.id,
            polar_customer_id="cus_pro",
            subscription_status="active",
            product_id=settings.polar_pro_product_id,
        ).insert()
        await record_usage_event(
            user_id=user.id,
            quantity=settings.pro_tier_llm_tokens_allowance,
            idempotency_key=f"test:{uuid4()}",
            settings=settings,
        )
        with pytest.raises(UsageQuotaExceededError):
            await check_quota_and_raise(user.id, 1, settings)

    async def test_max_tier_uses_its_own_larger_cap(
        self, app: Any, settings: Any
    ) -> None:
        """A Max subscriber isn't blocked by Pro's (smaller) session cap."""
        user = await create_user()
        await BillingCustomer(
            user_id=user.id,
            polar_customer_id="cus_max",
            subscription_status="active",
            product_id=settings.polar_max_product_id,
        ).insert()
        await record_usage_event(
            user_id=user.id,
            quantity=settings.pro_tier_session_tokens_allowance + 5,
            idempotency_key=f"test:{uuid4()}",
            settings=settings,
        )
        await check_quota_and_raise(user.id, 1, settings)

    async def test_unrecognized_product_id_falls_back_to_free_tier(
        self, app: Any, settings: Any
    ) -> None:
        """If an active subscription's product_id doesn't match a known
        tier (misconfiguration), the gate must fail toward the smaller
        free-tier cap, never toward unlimited.
        """
        user = await create_user()
        await BillingCustomer(
            user_id=user.id,
            polar_customer_id="cus_unknown",
            subscription_status="active",
            product_id="prod_does_not_match_any_tier",
        ).insert()
        await record_usage_event(
            user_id=user.id,
            quantity=settings.free_tier_llm_tokens_allowance,
            idempotency_key=f"test:{uuid4()}",
            settings=settings,
        )
        with pytest.raises(UsageQuotaExceededError):
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


class TestUsageWindows:
    async def test_creates_window_counter_on_first_use(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        counter = await get_or_create_window_counter(user.id, "session", settings)
        assert counter.llm_tokens_used == 0
        assert counter.window_end > counter.window_start

    async def test_reuses_counter_within_window(self, app: Any, settings: Any) -> None:
        user = await create_user()
        first = await get_or_create_window_counter(user.id, "session", settings)
        second = await get_or_create_window_counter(user.id, "session", settings)
        assert first.id == second.id

    async def test_rolls_over_after_window_expires(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        expired = UsageWindowCounter(
            user_id=user.id,
            window_type="session",
            window_start=datetime.now(UTC) - timedelta(hours=10),
            window_end=datetime.now(UTC) - timedelta(hours=5),
            llm_tokens_used=999,
        )
        await expired.insert()
        fresh = await get_or_create_window_counter(user.id, "session", settings)
        assert fresh.id != expired.id
        assert fresh.llm_tokens_used == 0

    async def test_session_cap_blocks_before_monthly_cap(
        self, app: Any, settings: Any
    ) -> None:
        """The session window is far tighter than the monthly cap, so it
        should be the one that trips first."""
        user = await create_user()
        await record_usage_event(
            user_id=user.id,
            quantity=settings.free_tier_session_tokens_allowance,
            idempotency_key=f"test:{uuid4()}",
            settings=settings,
        )
        with pytest.raises(UsageQuotaExceededError) as exc_info:
            await check_quota_and_raise(user.id, 1, settings)
        assert exc_info.value.window == "session"

    async def test_record_usage_event_increments_all_windows(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        await record_usage_event(
            user_id=user.id,
            quantity=10,
            idempotency_key=f"test:{uuid4()}",
            settings=settings,
        )
        session_counter = await UsageWindowCounter.find_one(
            {"user_id": user.id, "window_type": "session"}
        )
        weekly_counter = await UsageWindowCounter.find_one(
            {"user_id": user.id, "window_type": "weekly"}
        )
        assert session_counter is not None
        assert session_counter.llm_tokens_used == 10
        assert weekly_counter is not None
        assert weekly_counter.llm_tokens_used == 10

    async def test_usage_summary_includes_window_fields(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        await record_usage_event(
            user_id=user.id,
            quantity=10,
            idempotency_key=f"test:{uuid4()}",
            settings=settings,
        )
        summary = await get_usage_summary(user.id, settings)
        assert summary.session_tokens_used == 10
        assert summary.session_tokens_allowance == (
            settings.free_tier_session_tokens_allowance
        )
        assert summary.weekly_tokens_used == 10
        assert summary.weekly_tokens_allowance == (
            settings.free_tier_weekly_tokens_allowance
        )


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
        url = await create_checkout_session(user, settings, "pro", client=fake_client)
        assert url == "https://sandbox.polar.sh/checkout/fake"
        assert len(fake_client.checkout_calls) == 1
        assert fake_client.checkout_calls[0]["product_id"] == (
            settings.polar_pro_product_id
        )

    async def test_create_checkout_session_resolves_correct_product_per_tier(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        fake_client = FakePolarClient()
        await create_checkout_session(user, settings, "max", client=fake_client)
        assert fake_client.checkout_calls[0]["product_id"] == (
            settings.polar_max_product_id
        )

    async def test_create_customer_portal_session_returns_url(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        fake_client = FakePolarClient()
        url = await create_customer_portal_session(user, settings, client=fake_client)
        assert url == "https://sandbox.polar.sh/portal/fake"


class TestChangeSubscriptionPlan:
    async def test_updates_existing_subscription_instead_of_checkout(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        await BillingCustomer(
            user_id=user.id,
            polar_customer_id="cus_change",
            subscription_id="sub_change_1",
            subscription_status="active",
            product_id=settings.polar_pro_product_id,
        ).insert()
        fake_client = FakePolarClient()

        updated = await change_subscription_plan(
            user, settings, "max", client=fake_client
        )

        assert updated.product_id == settings.polar_max_product_id
        assert len(fake_client.subscription_update_calls) == 1
        assert fake_client.subscription_update_calls[0] == {
            "subscription_id": "sub_change_1",
            "product_id": settings.polar_max_product_id,
        }
        assert fake_client.checkout_calls == []

    async def test_raises_when_no_active_subscription(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        fake_client = FakePolarClient()
        with pytest.raises(NoActiveBillingCustomerError):
            await change_subscription_plan(user, settings, "pro", client=fake_client)

    async def test_raises_when_subscription_canceled(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        await BillingCustomer(
            user_id=user.id,
            polar_customer_id="cus_canceled",
            subscription_id="sub_canceled_1",
            subscription_status="canceled",
            product_id=settings.polar_pro_product_id,
        ).insert()
        fake_client = FakePolarClient()
        with pytest.raises(NoActiveBillingCustomerError):
            await change_subscription_plan(user, settings, "max", client=fake_client)


class TestUsageEmission:
    async def test_emits_pending_events_and_marks_ingested(
        self, app: Any, settings: Any
    ) -> None:
        user = await create_user()
        await record_usage_event(
            user_id=user.id,
            quantity=42,
            idempotency_key=f"test:{uuid4()}",
            settings=settings,
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
            settings=settings,
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
