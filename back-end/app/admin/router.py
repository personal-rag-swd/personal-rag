from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.admin import service
from app.admin.schemas import (
    AdminDocumentListResponse,
    AdminDocumentPreview,
    AdminDocumentRead,
    AdminDocumentUpdate,
    AdminOrderListResponse,
    AdminStatsResponse,
    AdminTransactionListResponse,
    AdminUserListResponse,
    AdminUserRead,
    AdminUserUpdate,
    BillingSummaryResponse,
    DailyUsagePoint,
)
from app.billing.schemas import UsageSummaryResponse
from app.billing.service import get_usage_summary
from app.core.config import Settings, get_settings
from app.users.dependencies import get_current_user, require_role
from app.users.exceptions import ForbiddenError
from app.users.models import User

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_role("admin"))],
)


@router.get("/stats", response_model=AdminStatsResponse)
async def read_stats() -> AdminStatsResponse:
    return await service.get_admin_stats()


@router.get("/usage/daily", response_model=list[DailyUsagePoint])
async def read_daily_usage(
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> list[DailyUsagePoint]:
    return await service.get_daily_usage(days)


@router.get("/users", response_model=AdminUserListResponse)
async def read_users(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: str | None = None,
) -> AdminUserListResponse:
    return await service.list_users(page, page_size, search)


@router.patch("/users/{user_id}", response_model=AdminUserRead)
async def update_user(
    user_id: UUID,
    body: AdminUserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> AdminUserRead:
    # Live DB check: the router-level guard only inspects the JWT claim, which
    # can be stale for the token's lifetime after a demotion.
    if current_user.role != "admin":
        raise ForbiddenError()
    return await service.update_user(user_id, body, current_user)


@router.get("/users/{user_id}/usage", response_model=UsageSummaryResponse)
async def read_user_usage(
    user_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> UsageSummaryResponse:
    user = await service.get_user_or_404(user_id)
    return await get_usage_summary(user.id, settings)


@router.get("/documents", response_model=AdminDocumentListResponse)
async def read_documents(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: str | None = None,
    search: str | None = None,
) -> AdminDocumentListResponse:
    return await service.list_documents(page, page_size, status, search)


@router.get("/documents/{document_id}/preview", response_model=AdminDocumentPreview)
async def read_document_preview(
    document_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminDocumentPreview:
    return await service.get_document_preview(document_id, settings)


@router.patch("/documents/{document_id}", response_model=AdminDocumentRead)
async def update_document(
    document_id: UUID,
    body: AdminDocumentUpdate,
) -> AdminDocumentRead:
    return await service.update_document(document_id, body)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: UUID) -> Response:
    await service.delete_document(document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/transactions", response_model=AdminTransactionListResponse)
async def read_transactions(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    user_id: UUID | None = None,
) -> AdminTransactionListResponse:
    return await service.list_transactions(page, page_size, user_id)


@router.get("/orders", response_model=AdminOrderListResponse)
async def read_orders(
    settings: Annotated[Settings, Depends(get_settings)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AdminOrderListResponse:
    return await service.list_orders(page, page_size, settings)


@router.get("/billing/summary", response_model=BillingSummaryResponse)
async def read_billing_summary() -> BillingSummaryResponse:
    return await service.get_billing_summary()
