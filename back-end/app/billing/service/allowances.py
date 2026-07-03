"""Tier/allowance configuration: the pure mapping from a user's subscription
state to their effective token caps. No I/O beyond reading ``Settings``.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Literal

from app.billing.models import BillingCustomer
from app.core.config import Settings

logger = logging.getLogger(__name__)

ACTIVE_SUBSCRIPTION_STATUSES = {"active", "trialing"}

_TIER_PRO = "pro"
_TIER_MAX = "max"

WindowType = Literal["session", "weekly"]

_WINDOW_DURATIONS: dict[WindowType, Any] = {
    "session": lambda settings: timedelta(hours=settings.session_window_hours),
    "weekly": lambda settings: timedelta(days=settings.weekly_window_days),
}


def product_id_for_tier(tier: str, settings: Settings) -> str:
    return {
        _TIER_PRO: settings.polar_pro_product_id,
        _TIER_MAX: settings.polar_max_product_id,
    }[tier]


def _allowance_for_tier(tier: str, settings: Settings) -> int:
    return {
        _TIER_PRO: settings.pro_tier_llm_tokens_allowance,
        _TIER_MAX: settings.max_tier_llm_tokens_allowance,
    }[tier]


def window_allowance_for_tier(
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


def tier_for_product_id(product_id: str | None, settings: Settings) -> str | None:
    if product_id and product_id == settings.polar_pro_product_id:
        return _TIER_PRO
    if product_id and product_id == settings.polar_max_product_id:
        return _TIER_MAX
    return None


def window_duration(window_type: WindowType, settings: Settings) -> timedelta:
    return _WINDOW_DURATIONS[window_type](settings)


def resolve_effective_allowance(
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
        and billing_customer.subscription_status in ACTIVE_SUBSCRIPTION_STATUSES
    ):
        tier = tier_for_product_id(billing_customer.product_id, settings)
        if tier is not None:
            return tier, _allowance_for_tier(tier, settings)
        logger.warning(
            "Active subscription for user_id=%s has unrecognized "
            "product_id=%s; falling back to free-tier allowance",
            billing_customer.user_id,
            billing_customer.product_id,
        )
    return None, settings.free_tier_llm_tokens_allowance
