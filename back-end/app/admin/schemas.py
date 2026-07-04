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


class AdminDocumentUpdate(BaseModel):
    filename: str | None = Field(default=None, min_length=1, max_length=512)
    status: Literal["pending", "uploaded", "processing", "indexed", "failed"] | None = (
        None
    )


class AdminDocumentPreview(BaseModel):
    filename: str
    content_type: str | None
    size: int | None
    url: str | None = None
    content: str | None = None
    preview_type: Literal["text", "url"]


class AdminTransactionRead(BaseModel):
    id: UUID
    user_id: UUID
    notebook_id: UUID | None
    quantity: int
    polar_ingested: bool
    polar_ingested_at: datetime | None
    polar_ingest_error: str | None
    retry_count: int
    created_at: datetime


class AdminTransactionListResponse(BaseModel):
    items: list[AdminTransactionRead]
    total: int
    page: int
    page_size: int


class AdminOrderRead(BaseModel):
    id: str
    amount: int | None = None
    currency: str | None = None
    status: str | None = None
    customer_email: str | None = None
    product_id: str | None = None
    created_at: str | None = None


class AdminOrderListResponse(BaseModel):
    items: list[AdminOrderRead] = Field(default_factory=list)
    total: int = 0
    configured: bool = True


class BillingSummaryResponse(BaseModel):
    by_status: dict[str, int] = Field(default_factory=dict)
    by_product: dict[str, int] = Field(default_factory=dict)
    total_customers: int
