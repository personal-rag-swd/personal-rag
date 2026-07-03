"""Usage metering: monthly allowance + rolling window counters, quota checks,
and ledger recording. These are the billing hot paths called from chat/report
generation, so quota-check and record both fail open (never block the feature).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.billing.exceptions import UsageQuotaExceededError
from app.billing.models import (
    BillingCustomer,
    UsageAllowance,
    UsageEventLog,
    UsageWindowCounter,
)
from app.billing.service.allowances import (
    WindowType,
    resolve_effective_allowance,
    window_allowance_for_tier,
    window_duration,
)
from app.core.config import Settings

logger = logging.getLogger(__name__)


def _ensure_aware(value: datetime) -> datetime:
    """Re-attach UTC to a naive datetime.

    PyMongo decodes BSON datetimes as naive (implicitly UTC). Comparing or
    serializing them alongside timezone-aware values would raise or emit an
    offset-less timestamp the frontend misreads as local time, so every stored
    datetime is normalized on read.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


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
        allowance.period_start = _ensure_aware(allowance.period_start)
        allowance.period_end = _ensure_aware(allowance.period_end)
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
        existing.window_start = _ensure_aware(existing.window_start)
        existing.window_end = _ensure_aware(existing.window_end)
        if existing.window_end > now:
            return existing

    counter = UsageWindowCounter(
        user_id=user_id,
        window_type=window_type,
        window_start=now,
        window_end=now + window_duration(window_type, settings),
    )
    await counter.insert()
    return counter


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
        tier, allowance_limit = resolve_effective_allowance(billing_customer, settings)

        for window_type in ("session", "weekly"):
            counter = await get_or_create_window_counter(user_id, window_type, settings)
            window_limit = window_allowance_for_tier(window_type, tier, settings)
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
