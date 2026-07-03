from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CheckoutRequest(BaseModel):
    tier: Literal["pro", "max"]


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
    tier: str | None
    session_tokens_used: int
    session_tokens_allowance: int
    session_reset_at: datetime
    weekly_tokens_used: int
    weekly_tokens_allowance: int
    weekly_reset_at: datetime


class SubscriptionStatusResponse(BaseModel):
    subscription_status: str | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    tier: str | None
