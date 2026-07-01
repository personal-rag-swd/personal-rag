from datetime import datetime

from pydantic import BaseModel


class CheckoutSessionResponse(BaseModel):
    url: str


class CustomerPortalResponse(BaseModel):
    url: str


class UsageSummaryResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    llm_tokens_used: int
    llm_tokens_allowance: int
    is_subscription_active: bool


class SubscriptionStatusResponse(BaseModel):
    subscription_status: str | None
    current_period_start: datetime | None
    current_period_end: datetime | None
