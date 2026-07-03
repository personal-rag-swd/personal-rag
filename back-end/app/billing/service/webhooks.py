"""Inbound Polar webhooks: signature verification and subscription-state
reconciliation onto ``BillingCustomer`` rows.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from datetime import UTC, datetime
from typing import Any

from polar_sdk.webhooks import (
    WebhookUnknownTypeError,
    WebhookVerificationError,
    validate_event,
)
from pydantic import ValidationError

from app.billing.exceptions import WebhookSignatureInvalidError
from app.billing.models import BillingCustomer, ProcessedWebhookEvent
from app.billing.service.allowances import ACTIVE_SUBSCRIPTION_STATUSES

logger = logging.getLogger(__name__)
WEBHOOK_TOLERANCE_SECONDS = 300


def _parse_polar_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


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
        if _verify_standard_webhook_signature_fallback(
            payload_bytes, headers, secret
        ):
            logger.info(
                "Polar webhook verified via Standard Webhooks fallback after SDK rejection"
            )
            return
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


def _verify_standard_webhook_signature_fallback(
    payload_bytes: bytes, headers: dict[str, str], secret: str
) -> bool:
    """Fallback signature check decoupled from Polar SDK payload parsing.

    ``polar_sdk.validate_event`` currently couples signature verification with
    event-schema parsing. When the pinned SDK lags newer payload shapes such as
    ``customer.state_changed``, valid deliveries can be rejected before the app
    sees the raw JSON. This fallback verifies the Standard Webhooks MAC only.
    """
    webhook_id = headers.get("webhook-id", "")
    webhook_timestamp = headers.get("webhook-timestamp", "")
    signature_header = headers.get("webhook-signature", "")
    if not webhook_id or not webhook_timestamp or not signature_header or not secret:
        return False

    try:
        timestamp = int(webhook_timestamp)
    except ValueError:
        return False

    now = int(datetime.now(UTC).timestamp())
    if abs(now - timestamp) > WEBHOOK_TOLERANCE_SECONDS:
        return False

    try:
        payload_text = payload_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return False

    signed_content = f"{webhook_id}.{webhook_timestamp}.{payload_text}".encode(
        "utf-8"
    )
    expected_signature = base64.b64encode(
        hmac.new(secret.encode("utf-8"), signed_content, hashlib.sha256).digest()
    ).decode("ascii")

    candidate_signatures = [
        part.split(",", 1)[1]
        for part in signature_header.split()
        if part.startswith("v1,") and "," in part
    ]
    return any(
        hmac.compare_digest(signature, expected_signature)
        for signature in candidate_signatures
    )


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
            if sub.get("status") in ACTIVE_SUBSCRIPTION_STATUSES
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
