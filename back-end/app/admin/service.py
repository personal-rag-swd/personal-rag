import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from beanie import Document

from app.admin.exceptions import SelfModificationError, UserNotFoundError
from app.admin.schemas import (
    AdminDocumentListResponse,
    AdminDocumentRead,
    AdminStatsResponse,
    AdminUserListResponse,
    AdminUserRead,
    AdminUserUpdate,
    BillingSummaryResponse,
    DailyUsagePoint,
)
from app.billing.models import BillingCustomer, UsageAllowance, UsageEventLog
from app.notebooks.models import Notebook, NotebookDocument, NotebookReport
from app.users.models import User


def _current_period_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def _count_by_field(model: type[Document], field: str) -> dict[str, int]:
    rows = await model.aggregate(
        [{"$group": {"_id": f"${field}", "count": {"$sum": 1}}}]
    ).to_list()
    return {str(row["_id"]): row["count"] for row in rows if row["_id"] is not None}


async def get_admin_stats() -> AdminStatsResponse:
    now = datetime.now(UTC)
    token_rows = await UsageEventLog.aggregate(
        [
            {"$match": {"created_at": {"$gte": _current_period_start(now)}}},
            {"$group": {"_id": None, "tokens": {"$sum": "$quantity"}}},
        ]
    ).to_list()
    return AdminStatsResponse(
        total_users=await User.count(),
        active_users=await User.find({"is_active": True}).count(),
        total_notebooks=await Notebook.count(),
        documents_by_status=await _count_by_field(NotebookDocument, "status"),
        reports_by_status=await _count_by_field(NotebookReport, "status"),
        tokens_this_month=token_rows[0]["tokens"] if token_rows else 0,
        active_subscriptions=await BillingCustomer.find(
            {"subscription_status": {"$in": ["active", "trialing"]}}
        ).count(),
    )


async def get_daily_usage(days: int) -> list[DailyUsagePoint]:
    since = datetime.now(UTC) - timedelta(days=days)
    rows = await UsageEventLog.aggregate(
        [
            {"$match": {"created_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}
                    },
                    "tokens": {"$sum": "$quantity"},
                }
            },
            {"$sort": {"_id": 1}},
        ]
    ).to_list()
    return [DailyUsagePoint(date=row["_id"], tokens=row["tokens"]) for row in rows]


async def list_users(
    page: int, page_size: int, search: str | None
) -> AdminUserListResponse:
    query: dict[str, object] = {}
    if search:
        query["email"] = {"$regex": re.escape(search), "$options": "i"}

    total = await User.find(query).count()
    users = (
        await User.find(query)
        .sort("-created_at")
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )

    user_ids = [user.id for user in users]
    customers = await BillingCustomer.find({"user_id": {"$in": user_ids}}).to_list()
    customers_by_user = {customer.user_id: customer for customer in customers}
    allowances = await UsageAllowance.find(
        {
            "user_id": {"$in": user_ids},
            "period_start": _current_period_start(datetime.now(UTC)),
        }
    ).to_list()
    tokens_by_user = {
        allowance.user_id: allowance.llm_tokens_used for allowance in allowances
    }

    items = [
        _to_admin_user_read(user, customers_by_user.get(user.id), tokens_by_user)
        for user in users
    ]
    return AdminUserListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


def _to_admin_user_read(
    user: User,
    customer: BillingCustomer | None,
    tokens_by_user: dict[UUID, int],
) -> AdminUserRead:
    return AdminUserRead(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        subscription_status=customer.subscription_status if customer else None,
        product_id=customer.product_id if customer else None,
        tokens_used_this_period=tokens_by_user.get(user.id, 0),
    )


async def update_user(
    user_id: UUID, update: AdminUserUpdate, current_user: User
) -> AdminUserRead:
    user = await User.find_one({"_id": user_id})
    if user is None:
        raise UserNotFoundError()

    if user_id == current_user.id and (
        update.role == "user" or update.is_active is False
    ):
        raise SelfModificationError()

    if update.role is not None:
        user.role = update.role
    if update.is_active is not None:
        user.is_active = update.is_active
    user.updated_at = datetime.now(UTC)
    await user.save()

    customer = await BillingCustomer.find_one({"user_id": user.id})
    allowance = await UsageAllowance.find_one(
        {
            "user_id": user.id,
            "period_start": _current_period_start(datetime.now(UTC)),
        }
    )
    tokens_by_user = {user.id: allowance.llm_tokens_used} if allowance else {}
    return _to_admin_user_read(user, customer, tokens_by_user)


async def get_user_or_404(user_id: UUID) -> User:
    user = await User.find_one({"_id": user_id})
    if user is None:
        raise UserNotFoundError()
    return user


async def list_documents(
    page: int, page_size: int, status: str | None
) -> AdminDocumentListResponse:
    query: dict[str, object] = {}
    if status:
        query["status"] = status

    total = await NotebookDocument.find(query).count()
    documents = (
        await NotebookDocument.find(query)
        .sort("-created_at")
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )
    items = [
        AdminDocumentRead(
            id=document.id,
            filename=document.filename,
            content_type=document.content_type,
            size=document.size,
            status=document.status,
            error_message=document.error_message,
            notebook_id=document.notebook_id,
            user_id=document.user_id,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
        for document in documents
    ]
    return AdminDocumentListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


async def get_billing_summary() -> BillingSummaryResponse:
    return BillingSummaryResponse(
        by_status=await _count_by_field(BillingCustomer, "subscription_status"),
        by_product=await _count_by_field(BillingCustomer, "product_id"),
        total_customers=await BillingCustomer.count(),
    )
