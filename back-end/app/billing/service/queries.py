"""Read-model queries assembling billing state into API response schemas."""

from __future__ import annotations

from uuid import UUID

from app.billing.models import BillingCustomer
from app.billing.schemas import (
    SubscriptionStatusResponse,
    UsageSummaryResponse,
)
from app.billing.service.allowances import (
    ACTIVE_SUBSCRIPTION_STATUSES,
    resolve_effective_allowance,
    window_allowance_for_tier,
)
from app.billing.service.usage import (
    get_or_create_usage_allowance,
    get_or_create_window_counter,
)
from app.core.config import Settings


async def get_usage_summary(user_id: UUID, settings: Settings) -> UsageSummaryResponse:
    billing_customer = await BillingCustomer.find_one({"user_id": user_id})
    allowance = await get_or_create_usage_allowance(user_id)
    session_counter = await get_or_create_window_counter(user_id, "session", settings)
    weekly_counter = await get_or_create_window_counter(user_id, "weekly", settings)
    is_active = (
        billing_customer is not None
        and billing_customer.subscription_status in ACTIVE_SUBSCRIPTION_STATUSES
    )
    tier, allowance_limit = resolve_effective_allowance(billing_customer, settings)
    return UsageSummaryResponse(
        period_start=allowance.period_start,
        period_end=allowance.period_end,
        llm_tokens_used=allowance.llm_tokens_used,
        llm_tokens_allowance=allowance_limit,
        is_subscription_active=is_active,
        tier=tier,
        session_tokens_used=session_counter.llm_tokens_used,
        session_tokens_allowance=window_allowance_for_tier("session", tier, settings),
        session_reset_at=session_counter.window_end,
        weekly_tokens_used=weekly_counter.llm_tokens_used,
        weekly_tokens_allowance=window_allowance_for_tier("weekly", tier, settings),
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
    tier, _allowance_limit = resolve_effective_allowance(billing_customer, settings)
    return SubscriptionStatusResponse(
        subscription_status=billing_customer.subscription_status,
        current_period_start=billing_customer.current_period_start,
        current_period_end=billing_customer.current_period_end,
        tier=tier,
    )
