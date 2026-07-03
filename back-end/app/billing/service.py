from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from polar_sdk.webhooks import (
    WebhookUnknownTypeError,
    WebhookVerificationError,
    validate_event,
)
from pydantic import ValidationError

from app.billing.exceptions import (
    NoActiveBillingCustomerError,
    UsageQuotaExceededError,
    WebhookSignatureInvalidError,
)
from app.billing.models import (
    BillingCustomer,
    ProcessedWebhookEvent,
    UsageAllowance,
    UsageEventLog,
    UsageWindowCounter,
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


WindowType = Literal["session", "weekly"]

_WINDOW_DURATIONS: dict[WindowType, Any] = {
    "session": lambda settings: timedelta(hours=settings.session_window_hours),
    "weekly": lambda settings: timedelta(days=settings.weekly_window_days),
}


def _window_allowance_for_tier(
    window_type: WindowType, tier: str | None, settings: Settings
) -> int:
    limits: dict[WindowType, dict[str | None, int]] = {
        "session": {
            None: settings.free_tier_session_tokens_allowance,
            _TIER_PRO: settings.pro_tier_session_tokens_allowance,
            _TIER_MAX: settings.max_tier_session_tokens_allowance,
        },
        "weekly": {
            None: settings.free_tier_weekly_tokens_allowance,
            _TIER_PRO: settings.pro_tier_weekly_tokens_allowance,
            _TIER_MAX: settings.max_tier_weekly_tokens_allowance,
        },
    }
    return limits[window_type][tier]


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
        # PyMongo decodes BSON datetimes as naive (UTC) - normalize before
        # returning so callers serializing these fields (e.g. UsageSummaryResponse)
        # don't emit an offset-less timestamp the frontend would misread as local time.
        if allowance.period_start.tzinfo is None:
            allowance.period_start = allowance.period_start.replace(tzinfo=UTC)
        if allowance.period_end.tzinfo is None:
            allowance.period_end = allowance.period_end.replace(tzinfo=UTC)
        return allowance
    allowance = UsageAllowance(
        user_id=user_id, period_start=period_start, period_end=period_end
    )
    await allowance.insert()
    return allowance


async def get_or_create_window_counter(
    user_id: UUID, window_type: WindowType, settings: Settings
) -> UsageWindowCounter:
    """Return the user's current rolling window counter, rolling it over if
    the previous window's ``window_end`` has passed.

    Windows are not calendar-aligned: a new window starts the first time
    usage is checked/recorded after the previous one expired.
    """
    now = datetime.now(UTC)
    existing = await UsageWindowCounter.find_one(
        {"user_id": user_id, "window_type": window_type},
        sort=[("window_start", -1)],
    )
    if existing is not None:
        # PyMongo decodes BSON datetimes as naive (UTC) - normalize before
        # comparing against (or returning alongside) an aware `now`, which
        # would otherwise raise TypeError on every read after the first
        # (naive vs. aware compare) or serialize reset_at without a UTC
        # offset, causing the frontend to parse it as local time.
        if existing.window_start.tzinfo is None:
            existing.window_start = existing.window_start.replace(tzinfo=UTC)
        if existing.window_end.tzinfo is None:
            existing.window_end = existing.window_end.replace(tzinfo=UTC)
        if existing.window_end > now:
            return existing

    duration = _WINDOW_DURATIONS[window_type](settings)
    counter = UsageWindowCounter(
        user_id=user_id,
        window_type=window_type,
        window_start=now,
        window_end=now + duration,
    )
    await counter.insert()
    return counter


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


async def change_subscription_plan(
    user: User,
    settings: Settings,
    tier: str,
    *,
    client: PolarClientProtocol | None = None,
) -> BillingCustomer:
    """Switch an already-subscribed user to a different tier in place.

    Polar refuses to checkout a second product while a subscription is
    active, so switching tiers must go through the subscription update
    endpoint instead of ``create_checkout_session``. Requires an existing
    active subscription; use ``create_checkout_session`` for a first-time
    subscribe.
    """
    billing_customer = await BillingCustomer.find_one({"user_id": user.id})
    if (
        billing_customer is None
        or billing_customer.subscription_id is None
        or billing_customer.subscription_status not in _ACTIVE_SUBSCRIPTION_STATUSES
    ):
        raise NoActiveBillingCustomerError()

    resolved_client = client or get_polar_client(settings)
    await resolved_client.update_subscription_product(
        subscription_id=billing_customer.subscription_id,
        product_id=_product_id_for_tier(tier, settings),
    )

    # Reflect the change immediately rather than waiting on the Polar
    # webhook, which arrives asynchronously; the webhook handler is
    # idempotent and will simply confirm this once it lands.
    billing_customer.product_id = _product_id_for_tier(tier, settings)
    billing_customer.updated_at = datetime.now(UTC)
    await billing_customer.save()
    return billing_customer


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
    exceeded_window: str | None = None
    exceeded_reset_at: datetime | None = None
    try:
        billing_customer = await BillingCustomer.find_one({"user_id": user_id})
        tier, allowance_limit = _resolve_effective_allowance(billing_customer, settings)

        for window_type in ("session", "weekly"):
            counter = await get_or_create_window_counter(user_id, window_type, settings)
            window_limit = _window_allowance_for_tier(window_type, tier, settings)
            if counter.llm_tokens_used + quantity > window_limit:
                exceeded_window = window_type
                exceeded_reset_at = counter.window_end
                break

        if exceeded_window is None:
            allowance = await get_or_create_usage_allowance(user_id)
            if allowance.llm_tokens_used + quantity > allowance_limit:
                exceeded_window = "monthly"
                exceeded_reset_at = allowance.period_end
    except Exception:
        logger.exception(
            "Failed to check usage quota for user_id=%s; allowing request through",
            user_id,
        )
        return

    if exceeded_window is not None:
        raise UsageQuotaExceededError(
            window=exceeded_window, reset_at=exceeded_reset_at
        )


async def record_usage_event(
    *,
    user_id: UUID,
    quantity: int,
    idempotency_key: str,
    settings: Settings,
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

        for window_type in ("session", "weekly"):
            counter = await get_or_create_window_counter(user_id, window_type, settings)
            counter.llm_tokens_used += quantity
            counter.updated_at = datetime.now(UTC)
            await counter.save()
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
    session_counter = await get_or_create_window_counter(user_id, "session", settings)
    weekly_counter = await get_or_create_window_counter(user_id, "weekly", settings)
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
        session_tokens_used=session_counter.llm_tokens_used,
        session_tokens_allowance=_window_allowance_for_tier("session", tier, settings),
        session_reset_at=session_counter.window_end,
        weekly_tokens_used=weekly_counter.llm_tokens_used,
        weekly_tokens_allowance=_window_allowance_for_tier("weekly", tier, settings),
        weekly_reset_at=weekly_counter.window_end,
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
    """Verify a Polar webhook signature using the official Polar SDK.

    Delegates to ``polar_sdk.webhooks.validate_event``, which implements the
    Standard Webhooks scheme exactly as Polar signs its deliveries (including
    the non-obvious secret key derivation and the timestamp-tolerance check).

    Raises ``WebhookSignatureInvalidError`` on a missing/malformed header, a
    stale timestamp, or a signature mismatch.
    """
    try:
        validate_event(payload_bytes, headers, secret)
    except WebhookVerificationError as exc:
        logger.warning("Polar webhook rejected: %s", exc)
        raise WebhookSignatureInvalidError() from exc
    except (WebhookUnknownTypeError, ValidationError):
        # The signature is verified before the payload is parsed, so an unknown
        # event type or a schema the pinned SDK does not model is NOT a
        # signature failure. Downstream handling works off the raw JSON dict,
        # so let these through as successfully verified.
        return
    except ValueError as exc:
        # A malformed signature header (non-base64, or missing the "v1," version
        # prefix) makes the SDK raise a raw decode/parse error before it can
        # report a mismatch. Pydantic's ValidationError is also a ValueError but
        # is handled above, so anything reaching here is a bad signature header.
        logger.warning("Polar webhook rejected: malformed signature header (%s)", exc)
        raise WebhookSignatureInvalidError() from exc


def _apply_subscription_fields(
    billing_customer: BillingCustomer, subscription: dict[str, Any]
) -> None:
    """Copy a Polar subscription object's fields onto a ``BillingCustomer``.

    Works for both the ``subscription.*`` event payloads (where ``data`` *is*
    the subscription) and the ``active_subscriptions`` entries inside a
    ``customer.state_changed`` payload - the field names match.
    """
    billing_customer.subscription_id = subscription.get("id")
    billing_customer.subscription_status = subscription.get("status")
    billing_customer.product_id = subscription.get("product_id") or (
        subscription.get("product") or {}
    ).get("id")
    billing_customer.current_period_start = _parse_polar_datetime(
        subscription.get("current_period_start")
    )
    billing_customer.current_period_end = _parse_polar_datetime(
        subscription.get("current_period_end")
    )
    billing_customer.updated_at = datetime.now(UTC)


async def _handle_customer_state_changed(data: dict[str, Any]) -> None:
    """Reconcile a customer's tier from a ``customer.state_changed`` event.

    Polar recommends this event as the canonical source of subscription state:
    its ``data`` is the customer object (id at ``data["id"]``, not
    ``customer_id``), carrying the full ``active_subscriptions`` list. We mirror
    the first active/trialing subscription onto the customer, and downgrade to
    ``canceled`` when there are none.
    """
    polar_customer_id = data.get("id")
    if not polar_customer_id:
        logger.warning(
            "Polar webhook customer.state_changed missing customer id; skipping"
        )
        return

    billing_customer = await BillingCustomer.find_one(
        {"polar_customer_id": polar_customer_id}
    )
    if billing_customer is None:
        logger.warning(
            "Polar webhook customer.state_changed for unknown customer %s; skipping",
            polar_customer_id,
        )
        return

    active_subscriptions = data.get("active_subscriptions") or []
    active_subscription = next(
        (
            sub
            for sub in active_subscriptions
            if sub.get("status") in _ACTIVE_SUBSCRIPTION_STATUSES
        ),
        None,
    )
    if active_subscription is not None:
        _apply_subscription_fields(billing_customer, active_subscription)
    else:
        billing_customer.subscription_status = "canceled"
        billing_customer.updated_at = datetime.now(UTC)
    await billing_customer.save()


async def handle_webhook_event(payload: dict[str, Any]) -> None:
    event_type = payload.get("type", "")
    data = payload.get("data", {}) or {}

    if event_type == "customer.state_changed":
        await _handle_customer_state_changed(data)
        return

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
        _apply_subscription_fields(billing_customer, data)
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
