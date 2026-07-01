import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.billing.exceptions import (
    BillingNotConfiguredError,
    WebhookSignatureInvalidError,
)
from app.billing.schemas import (
    CheckoutSessionResponse,
    CustomerPortalResponse,
    SubscriptionStatusResponse,
    UsageSummaryResponse,
)
from app.billing.service import (
    create_checkout_session,
    create_customer_portal_session,
    get_subscription_status,
    get_usage_summary,
    handle_webhook_event,
    is_webhook_already_processed,
    mark_webhook_processed,
    verify_webhook_signature,
)
from app.core.config import Settings, get_settings
from app.users.dependencies import get_current_user
from app.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing"])


def _require_billing_configured(settings: Settings) -> None:
    if not settings.polar_api_key or not settings.polar_product_id:
        raise BillingNotConfiguredError()


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def checkout(
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CheckoutSessionResponse:
    _require_billing_configured(settings)
    url = await create_checkout_session(current_user, settings)
    return CheckoutSessionResponse(url=url)


@router.get("/portal", response_model=CustomerPortalResponse)
async def portal(
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CustomerPortalResponse:
    _require_billing_configured(settings)
    url = await create_customer_portal_session(current_user, settings)
    return CustomerPortalResponse(url=url)


@router.get("/usage", response_model=UsageSummaryResponse)
async def usage(
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UsageSummaryResponse:
    return await get_usage_summary(current_user.id, settings)


@router.get("/subscription", response_model=SubscriptionStatusResponse)
async def subscription(
    current_user: Annotated[User, Depends(get_current_user)],
) -> SubscriptionStatusResponse:
    return await get_subscription_status(current_user.id)


@router.post("/webhooks/polar", status_code=status.HTTP_200_OK)
async def polar_webhook(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    body = await request.body()
    try:
        verify_webhook_signature(
            body, dict(request.headers), settings.polar_webhook_secret
        )
    except WebhookSignatureInvalidError:
        logger.warning("Rejected Polar webhook with invalid signature")
        raise

    webhook_id = request.headers.get("webhook-id", "")
    if webhook_id and await is_webhook_already_processed(webhook_id):
        return Response(status_code=status.HTTP_200_OK)

    payload = await request.json()
    await handle_webhook_event(payload)
    if webhook_id:
        await mark_webhook_processed(webhook_id, payload.get("type", ""))
    return Response(status_code=status.HTTP_200_OK)
