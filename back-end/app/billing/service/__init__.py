"""Billing service layer.

Split into cohesive modules by responsibility while preserving the historical
``app.billing.service`` import surface. Callers should keep importing names from
``app.billing.service`` rather than the submodules directly.
"""

from app.billing.service.emission import emit_pending_usage_events_to_polar
from app.billing.service.provisioning import (
    change_subscription_plan,
    create_checkout_session,
    create_customer_portal_session,
    get_or_create_polar_customer,
)
from app.billing.service.queries import (
    get_subscription_status,
    get_usage_summary,
)
from app.billing.service.usage import (
    check_quota_and_raise,
    get_or_create_usage_allowance,
    get_or_create_window_counter,
    record_usage_event,
)
from app.billing.service.webhooks import (
    handle_webhook_event,
    is_webhook_already_processed,
    mark_webhook_processed,
    verify_webhook_signature,
)

__all__ = [
    "change_subscription_plan",
    "check_quota_and_raise",
    "create_checkout_session",
    "create_customer_portal_session",
    "emit_pending_usage_events_to_polar",
    "get_or_create_polar_customer",
    "get_or_create_usage_allowance",
    "get_or_create_window_counter",
    "get_subscription_status",
    "get_usage_summary",
    "handle_webhook_event",
    "is_webhook_already_processed",
    "mark_webhook_processed",
    "record_usage_event",
    "verify_webhook_signature",
]
