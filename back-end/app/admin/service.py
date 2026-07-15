import logging
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import obstore
from beanie import Document

from app.admin.exceptions import (
    DocumentContentUnavailableError,
    DocumentNotFoundError,
    SelfModificationError,
    UserNotFoundError,
)
from app.admin.schemas import (
    AdminDocumentListResponse,
    AdminDocumentPreview,
    AdminDocumentRead,
    AdminDocumentUpdate,
    AdminOrderListResponse,
    AdminOrderRead,
    AdminStatsResponse,
    AdminTransactionListResponse,
    AdminTransactionRead,
    AdminUserListResponse,
    AdminUserRead,
    AdminUserUpdate,
    BillingSummaryResponse,
    DailyUsagePoint,
)
from app.billing.models import BillingCustomer, UsageAllowance, UsageEventLog
from app.billing.polar_client import PolarAPIError, get_polar_client
from app.core.config import Settings
from app.core.s3 import generate_presigned_get_url, get_s3_store
from app.notebooks.models import (
    Notebook,
    NotebookDocument,
    NotebookDocumentChunk,
    NotebookReport,
)
from app.users.models import User

logger = logging.getLogger(__name__)


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


def _to_admin_document_read(document: NotebookDocument) -> AdminDocumentRead:
    return AdminDocumentRead(
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


async def list_documents(
    page: int, page_size: int, status: str | None, search: str | None = None
) -> AdminDocumentListResponse:
    query: dict[str, object] = {}
    if status:
        query["status"] = status
    if search:
        query["filename"] = {"$regex": re.escape(search), "$options": "i"}

    total = await NotebookDocument.find(query).count()
    documents = (
        await NotebookDocument.find(query)
        .sort("-created_at")
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )
    items = [_to_admin_document_read(document) for document in documents]
    return AdminDocumentListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


async def get_document_or_404(document_id: UUID) -> NotebookDocument:
    document = await NotebookDocument.find_one({"_id": document_id})
    if document is None:
        raise DocumentNotFoundError()
    return document


async def update_document(
    document_id: UUID, update: AdminDocumentUpdate
) -> AdminDocumentRead:
    document = await get_document_or_404(document_id)
    if update.filename is not None:
        document.filename = update.filename
    if update.status is not None:
        document.status = update.status
    document.updated_at = datetime.now(UTC)
    await document.save()
    return _to_admin_document_read(document)


async def delete_document(document_id: UUID) -> None:
    document = await get_document_or_404(document_id)
    await NotebookDocumentChunk.find({"document_id": document.id}).delete()

    note_reports = await NotebookReport.find(
        {"notebook_id": document.notebook_id, "report_type": "note"},
    ).to_list()
    for report in note_reports:
        if isinstance(report.content, dict) and report.content.get(
            "document_id"
        ) == str(document.id):
            await report.delete()

    await document.delete()


async def get_document_preview(
    document_id: UUID, settings: Settings
) -> AdminDocumentPreview:
    document = await get_document_or_404(document_id)

    # In-app notes have no object-storage URL. The client turns this content
    # into a short-lived Blob URL so every supported format uses one viewer.
    if document.content is not None:
        return AdminDocumentPreview(
            filename=document.filename,
            content_type=document.content_type,
            size=document.size,
            content=document.content,
            preview_type="text",
        )
    if not document.s3_key:
        raise DocumentContentUnavailableError()
    # Confirm the object still exists before handing back a presigned URL: the
    # DB row can outlive its S3 object (upload never completed, object removed
    # out-of-band), and a URL to a missing object 404s inside the viewer rather
    # than surfacing as a clean error. Head-check here so the client gets a 404
    # it can render as "content unavailable" instead of a broken preview.
    try:
        await obstore.head_async(get_s3_store(settings), document.s3_key)
    except FileNotFoundError as exc:
        raise DocumentContentUnavailableError() from exc
    url = generate_presigned_get_url(settings, key=document.s3_key, expires_in=3600)
    return AdminDocumentPreview(
        filename=document.filename,
        content_type=document.content_type,
        size=document.size,
        url=url,
        preview_type="url",
    )


async def list_transactions(
    page: int, page_size: int, user_id: UUID | None
) -> AdminTransactionListResponse:
    query: dict[str, object] = {}
    if user_id is not None:
        query["user_id"] = user_id

    total = await UsageEventLog.find(query).count()
    events = (
        await UsageEventLog.find(query)
        .sort("-created_at")
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )
    items = [
        AdminTransactionRead(
            id=event.id,
            user_id=event.user_id,
            notebook_id=event.notebook_id,
            quantity=event.quantity,
            polar_ingested=event.polar_ingested,
            polar_ingested_at=event.polar_ingested_at,
            polar_ingest_error=event.polar_ingest_error,
            retry_count=event.retry_count,
            created_at=event.created_at,
        )
        for event in events
    ]
    return AdminTransactionListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _to_admin_order_read(order: dict[str, object]) -> AdminOrderRead:
    customer = order.get("customer")
    customer_email = (
        _as_str(customer.get("email")) if isinstance(customer, dict) else None
    )
    amount = order.get("net_amount")
    if amount is None:
        amount = order.get("total_amount")
    if amount is None:
        amount = order.get("amount")
    return AdminOrderRead(
        id=str(order.get("id", "")),
        amount=amount if isinstance(amount, int) else None,
        currency=_as_str(order.get("currency")),
        status=_as_str(order.get("status")),
        customer_email=customer_email,
        product_id=_as_str(order.get("product_id")),
        created_at=_as_str(order.get("created_at")),
    )


async def list_orders(
    page: int, page_size: int, settings: Settings
) -> AdminOrderListResponse:
    if not settings.polar_api_key:
        return AdminOrderListResponse(configured=False)
    try:
        payload = await get_polar_client(settings).list_orders(
            page=page,
            limit=page_size,
            organization_id=settings.polar_organization_id or None,
        )
    except PolarAPIError:
        logger.warning("Failed to fetch Polar orders for admin dashboard")
        return AdminOrderListResponse(configured=True)

    raw_items = payload.get("items", [])
    items = [
        _to_admin_order_read(order) for order in raw_items if isinstance(order, dict)
    ]
    pagination = payload.get("pagination", {})
    total = (
        pagination.get("total_count", len(items))
        if isinstance(pagination, dict)
        else len(items)
    )
    return AdminOrderListResponse(
        items=items,
        total=total if isinstance(total, int) else len(items),
        configured=True,
    )


async def get_billing_summary() -> BillingSummaryResponse:
    return BillingSummaryResponse(
        by_status=await _count_by_field(BillingCustomer, "subscription_status"),
        by_product=await _count_by_field(BillingCustomer, "product_id"),
        total_customers=await BillingCustomer.count(),
    )
