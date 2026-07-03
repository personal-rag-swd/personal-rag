"""Polar customer/checkout/portal provisioning.

Every function accepts an optional ``client`` so tests can inject a fake Polar
client (dependency inversion — the module never hard-depends on live Polar).
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.billing.exceptions import NoActiveBillingCustomerError
from app.billing.models import BillingCustomer
from app.billing.polar_client import PolarClientProtocol, get_polar_client
from app.billing.service.allowances import (
    ACTIVE_SUBSCRIPTION_STATUSES,
    product_id_for_tier,
)
from app.core.config import Settings
from app.users.models import User


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
        product_id=product_id_for_tier(tier, settings),
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
        or billing_customer.subscription_status not in ACTIVE_SUBSCRIPTION_STATUSES
    ):
        raise NoActiveBillingCustomerError()

    resolved_client = client or get_polar_client(settings)
    await resolved_client.update_subscription_product(
        subscription_id=billing_customer.subscription_id,
        product_id=product_id_for_tier(tier, settings),
    )

    # Reflect the change immediately rather than waiting on the Polar
    # webhook, which arrives asynchronously; the webhook handler is
    # idempotent and will simply confirm this once it lands.
    billing_customer.product_id = product_id_for_tier(tier, settings)
    billing_customer.updated_at = datetime.now(UTC)
    await billing_customer.save()
    return billing_customer
