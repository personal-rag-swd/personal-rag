from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.billing.exceptions import (
    UsageQuotaExceededError,
    WebhookSignatureInvalidError,
)
from app.billing.models import (
    BillingCustomer,
    ProcessedWebhookEvent,
    UsageAllowance,
    UsageEventLog,
)
from app.billing.polar_client import (
    PolarAPIError,
    PolarClientProtocol,
    get_polar_client,
)
from app.billing.schemas import (
    SubscriptionStatusResponse,
    UsageSummaryResponse,
)
from app.core.config import Settings
from app.users.models import User

logger = logging.getLogger(__name__)

_ACTIVE_SUBSCRIPTION_STATUSES = {"active", "trialing"}
_WEBHOOK_TIMESTAMP_TOLERANCE = timedelta(minutes=5)
_METER_EVENT_NAME = "llm_usage"

_TIER_PRO = "pro"
_TIER_MAX = "max"


def _product_id_for_tier(tier: str, settings: Settings) -> str:
    return {
        _TIER_PRO: settings.polar_pro_product_id,
        _TIER_MAX: settings.polar_max_product_id,
    }[tier]


def _allowance_for_tier(tier: str, settings: Settings) -> int:
    return {
        _TIER_PRO: settings.pro_tier_llm_tokens_allowance,
        _TIER_MAX: settings.max_tier_llm_tokens_allowance,
    }[tier]


def _tier_for_product_id(product_id: str | None, settings: Settings) -> str | None:
    if product_id and product_id == settings.polar_pro_product_id:
        return _TIER_PRO
    if product_id and product_id == settings.polar_max_product_id:
        return _TIER_MAX
    return None


def _resolve_effective_allowance(
    billing_customer: BillingCustomer | None, settings: Settings
) -> tuple[str | None, int]:
    """Return ``(tier, allowance_limit)`` for the user's current subscription.

    Falls back to the free-tier allowance (tier=None) whenever there's no
    active subscription, or the subscription's product_id doesn't match a
    known tier - "used up is used up" must degrade to the smaller cap, never
    to unlimited.
    """
    if (
        billing_customer is not None
        and billing_customer.subscription_status in _ACTIVE_SUBSCRIPTION_STATUSES
    ):
        tier = _tier_for_product_id(billing_customer.product_id, settings)
        if tier is not None:
            return tier, _allowance_for_tier(tier, settings)
        logger.warning(
            "Active subscription for user_id=%s has unrecognized "
            "product_id=%s; falling back to free-tier allowance",
            billing_customer.user_id,
            billing_customer.product_id,
        )
    return None, settings.free_tier_llm_tokens_allowance


def _parse_polar_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _current_period(now: datetime) -> tuple[datetime, datetime]:
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (
        start.replace(year=start.year + 1, month=1)
        if start.month == 12
        else start.replace(month=start.month + 1)
    )
    return start, end


async def get_or_create_usage_allowance(user_id: UUID) -> UsageAllowance:
    period_start, period_end = _current_period(datetime.now(UTC))
    allowance = await UsageAllowance.find_one(
        {"user_id": user_id, "period_start": period_start},
    )
    if allowance is not None:
        return allowance
    allowance = UsageAllowance(
        user_id=user_id, period_start=period_start, period_end=period_end
    )
    await allowance.insert()
    return allowance


async def get_or_create_polar_customer(
    user: User, settings: Settings, *, client: PolarClientProtocol | None = None
) -> BillingCustomer:
    existing = await BillingCustomer.find_one({"user_id": user.id})
    if existing is not None:
        return existing

    resolved_client = client or get_polar_client(settings)
    response = await resolved_client.create_customer(
        email=user.email, external_id=str(user.id)
    )
    customer = BillingCustomer(
        user_id=user.id,
        polar_customer_id=response["id"],
    )
    await customer.insert()
    return customer


async def create_checkout_session(
    user: User,
    settings: Settings,
    tier: str,
    *,
    client: PolarClientProtocol | None = None,
) -> str:
    resolved_client = client or get_polar_client(settings)
    await get_or_create_polar_customer(user, settings, client=resolved_client)
    response = await resolved_client.create_checkout_session(
        product_id=_product_id_for_tier(tier, settings),
        customer_external_id=str(user.id),
        success_url=settings.polar_success_url,
    )
    return response["url"]


async def create_customer_portal_session(
    user: User, settings: Settings, *, client: PolarClientProtocol | None = None
) -> str:
    resolved_client = client or get_polar_client(settings)
    customer = await get_or_create_polar_customer(
        user, settings, client=resolved_client
    )
    response = await resolved_client.create_customer_session(
        customer_id=customer.polar_customer_id
    )
    return response["customer_portal_url"]


async def check_quota_and_raise(
    user_id: UUID, quantity: int, settings: Settings
) -> None:
    """Raise ``UsageQuotaExceededError`` if this action would exceed the
    user's effective LLM token allowance (free tier, or their subscribed
    tier's cap if they have an active Polar subscription).

    Every tier - free, pro, max - is a hard cap: once exhausted, further
    chat/report actions are blocked until the next period or an upgrade.
    There is no "unlimited" tier.

    Fails open: an unexpected error while checking quota (e.g. a Mongo
    hiccup) is logged and swallowed rather than propagated, so a billing-side
    problem can never block chat or report generation for users who are
    still within their allowance.
    """
    try:
        billing_customer = await BillingCustomer.find_one({"user_id": user_id})
        _tier, allowance_limit = _resolve_effective_allowance(
            billing_customer, settings
        )

        allowance = await get_or_create_usage_allowance(user_id)
        exceeded = allowance.llm_tokens_used + quantity > allowance_limit
    except Exception:
        logger.exception(
            "Failed to check usage quota for user_id=%s; allowing request through",
            user_id,
        )
        return

    if exceeded:
        raise UsageQuotaExceededError()


async def record_usage_event(
    *,
    user_id: UUID,
    quantity: int,
    idempotency_key: str,
    notebook_id: UUID | None = None,
    event_metadata: dict[str, Any] | None = None,
) -> UsageEventLog | None:
    """Write a usage ledger entry and bump the allowance counter.

    Never raises: called from the chat/report hot paths, where a billing
    hiccup must not break the underlying feature.
    """
    try:
        existing = await UsageEventLog.find_one({"idempotency_key": idempotency_key})
        if existing is not None:
            return existing

        log = UsageEventLog(
            user_id=user_id,
            notebook_id=notebook_id,
            quantity=quantity,
            event_metadata=event_metadata or {},
            idempotency_key=idempotency_key,
        )
        await log.insert()

        allowance = await get_or_create_usage_allowance(user_id)
        allowance.llm_tokens_used += quantity
        allowance.updated_at = datetime.now(UTC)
        await allowance.save()
    except Exception:
        logger.exception(
            "Failed to record usage event (user_id=%s)",
            user_id,
        )
        return None
    return log


async def emit_pending_usage_events_to_polar(
    settings: Settings, *, client: PolarClientProtocol | None = None
) -> dict[str, int]:
    resolved_client = client or get_polar_client(settings)
    stats = {"checked": 0, "ingested": 0, "failed": 0}

    pending = (
        await UsageEventLog.find({"polar_ingested": False})
        .limit(settings.polar_usage_emit_batch_size)
        .to_list()
    )
    if not pending:
        return stats

    stats["checked"] = len(pending)
    events = [
        {
            "name": _METER_EVENT_NAME,
            "external_customer_id": str(log.user_id),
            "metadata": {"quantity": log.quantity, **log.event_metadata},
        }
        for log in pending
    ]

    try:
        await resolved_client.ingest_events(events)
    except PolarAPIError:
        logger.warning(
            "Polar usage event ingestion failed for %d event(s); will retry",
            len(pending),
        )
        for log in pending:
            log.retry_count += 1
            log.polar_ingest_error = "Polar events ingest request failed"
            if log.retry_count > settings.polar_usage_emit_max_retries:
                logger.exception(
                    "Usage event %s exceeded max retries; leaving unsent for "
                    "manual attention",
                    log.id,
                )
            await log.save()
        stats["failed"] = len(pending)
        return stats

    now = datetime.now(UTC)
    for log in pending:
        log.polar_ingested = True
        log.polar_ingested_at = now
        log.polar_ingest_error = None
        await log.save()
    stats["ingested"] = len(pending)
    return stats


async def get_usage_summary(user_id: UUID, settings: Settings) -> UsageSummaryResponse:
    billing_customer = await BillingCustomer.find_one({"user_id": user_id})
    allowance = await get_or_create_usage_allowance(user_id)
    is_active = (
        billing_customer is not None
        and billing_customer.subscription_status in _ACTIVE_SUBSCRIPTION_STATUSES
    )
    tier, allowance_limit = _resolve_effective_allowance(billing_customer, settings)
    return UsageSummaryResponse(
        period_start=allowance.period_start,
        period_end=allowance.period_end,
        llm_tokens_used=allowance.llm_tokens_used,
        llm_tokens_allowance=allowance_limit,
        is_subscription_active=is_active,
        tier=tier,
    )


async def get_subscription_status(
    user_id: UUID, settings: Settings
) -> SubscriptionStatusResponse:
    billing_customer = await BillingCustomer.find_one({"user_id": user_id})
    if billing_customer is None:
        return SubscriptionStatusResponse(
            subscription_status=None,
            current_period_start=None,
            current_period_end=None,
            tier=None,
        )
    tier, _allowance_limit = _resolve_effective_allowance(billing_customer, settings)
    return SubscriptionStatusResponse(
        subscription_status=billing_customer.subscription_status,
        current_period_start=billing_customer.current_period_start,
        current_period_end=billing_customer.current_period_end,
        tier=tier,
    )


def verify_webhook_signature(
    payload_bytes: bytes, headers: dict[str, str], secret: str
) -> None:
    """Verify a Polar webhook using the Standard Webhooks (svix-compatible) scheme.

    Raises ``WebhookSignatureInvalidError`` on a missing/malformed header, a
    stale timestamp, or a signature mismatch.
    """
    webhook_id = headers.get("webhook-id")
    webhook_timestamp = headers.get("webhook-timestamp")
    webhook_signature = headers.get("webhook-signature")
    if not webhook_id or not webhook_timestamp or not webhook_signature:
        raise WebhookSignatureInvalidError()

    try:
        timestamp = datetime.fromtimestamp(int(webhook_timestamp), tz=UTC)
    except (ValueError, OSError) as exc:
        raise WebhookSignatureInvalidError() from exc
    if abs(datetime.now(UTC) - timestamp) > _WEBHOOK_TIMESTAMP_TOLERANCE:
        raise WebhookSignatureInvalidError()

    secret_material = secret.removeprefix("whsec_")
    # Polar (like svix) issues this as unpadded base64; re-pad before decoding.
    secret_material += "=" * (-len(secret_material) % 4)
    try:
        secret_bytes = base64.b64decode(secret_material)
    except (ValueError, TypeError) as exc:
        raise WebhookSignatureInvalidError() from exc

    signed_content = f"{webhook_id}.{webhook_timestamp}.{payload_bytes.decode()}"
    expected_signature = base64.b64encode(
        hmac.new(secret_bytes, signed_content.encode(), hashlib.sha256).digest()
    ).decode()

    provided_signatures = [
        part.split(",", 1)[1] for part in webhook_signature.split() if "," in part
    ]
    if not any(
        hmac.compare_digest(expected_signature, provided)
        for provided in provided_signatures
    ):
        raise WebhookSignatureInvalidError()


async def handle_webhook_event(payload: dict[str, Any]) -> None:
    event_type = payload.get("type", "")
    data = payload.get("data", {}) or {}
    polar_customer_id = data.get("customer_id") or (data.get("customer") or {}).get(
        "id"
    )
    if not polar_customer_id:
        logger.warning("Polar webhook %s missing customer id; skipping", event_type)
        return

    billing_customer = await BillingCustomer.find_one(
        {"polar_customer_id": polar_customer_id}
    )
    if billing_customer is None:
        logger.warning(
            "Polar webhook %s for unknown customer %s; skipping",
            event_type,
            polar_customer_id,
        )
        return

    if event_type in {
        "subscription.created",
        "subscription.active",
        "subscription.updated",
    }:
        billing_customer.subscription_id = data.get("id")
        billing_customer.subscription_status = data.get("status")
        billing_customer.product_id = data.get("product_id") or (
            data.get("product") or {}
        ).get("id")
        billing_customer.current_period_start = _parse_polar_datetime(
            data.get("current_period_start")
        )
        billing_customer.current_period_end = _parse_polar_datetime(
            data.get("current_period_end")
        )
        billing_customer.updated_at = datetime.now(UTC)
        await billing_customer.save()
    elif event_type in {"subscription.canceled", "subscription.revoked"}:
        billing_customer.subscription_status = "canceled"
        billing_customer.updated_at = datetime.now(UTC)
        await billing_customer.save()
    else:
        logger.info("Unhandled Polar webhook event type: %s", event_type)


async def is_webhook_already_processed(webhook_id: str) -> bool:
    existing = await ProcessedWebhookEvent.find_one({"webhook_id": webhook_id})
    return existing is not None


async def mark_webhook_processed(webhook_id: str, event_type: str) -> None:
    await ProcessedWebhookEvent(webhook_id=webhook_id, event_type=event_type).insert()
