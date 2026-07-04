from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AdminStatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_notebooks: int
    documents_by_status: dict[str, int]
    reports_by_status: dict[str, int]
    tokens_this_month: int
    active_subscriptions: int


class DailyUsagePoint(BaseModel):
    date: str
    tokens: int


class AdminUserRead(BaseModel):
    id: UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime
    subscription_status: str | None = None
    product_id: str | None = None
    tokens_used_this_period: int = 0


class AdminUserListResponse(BaseModel):
    items: list[AdminUserRead]
    total: int
    page: int
    page_size: int


class AdminUserUpdate(BaseModel):
    role: Literal["user", "admin"] | None = None
    is_active: bool | None = None


class AdminDocumentRead(BaseModel):
    id: UUID
    filename: str
    content_type: str | None
    size: int | None
    status: str
    error_message: str | None
    notebook_id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class AdminDocumentListResponse(BaseModel):
    items: list[AdminDocumentRead]
    total: int
    page: int
    page_size: int


class BillingSummaryResponse(BaseModel):
    by_status: dict[str, int] = Field(default_factory=dict)
    by_product: dict[str, int] = Field(default_factory=dict)
    total_customers: int
