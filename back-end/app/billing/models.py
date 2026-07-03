from datetime import UTC, datetime
from typing import Any, ClassVar, Literal
from uuid import UUID, uuid4

from beanie import Document
from pydantic import Field


class BillingCustomer(Document):
    id: UUID = Field(default_factory=uuid4)  # type: ignore
    user_id: UUID
    polar_customer_id: str
    subscription_id: str | None = None
    subscription_status: str | None = None
    product_id: str | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "billing_customers"
        use_state_management = True
        indexes: ClassVar[list[list[tuple[str, int]]]] = [
            [("user_id", 1)],
            [("polar_customer_id", 1)],
        ]

    @property
    def is_subscription_active(self) -> bool:
        return self.subscription_status in {"active", "trialing"}


class UsageEventLog(Document):
    """A billable LLM-token-usage event (chat turn or report generation)."""

    id: UUID = Field(default_factory=uuid4)  # type: ignore
    user_id: UUID
    notebook_id: UUID | None = None
    quantity: int
    event_metadata: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str
    polar_ingested: bool = False
    polar_ingested_at: datetime | None = None
    polar_ingest_error: str | None = None
    retry_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "billing_usage_event_logs"
        use_state_management = True
        indexes: ClassVar[list[list[tuple[str, int]]]] = [
            [("user_id", 1)],
            [("idempotency_key", 1)],
            [("polar_ingested", 1)],
        ]


class UsageAllowance(Document):
    """Per-user, per-calendar-month free-tier usage counters used for gating.

    Independent of Polar's own subscription billing period: this tracks the
    *free* allowance only, so it must have a period even when the user has no
    active subscription (and therefore no Polar-provided period).
    """

    id: UUID = Field(default_factory=uuid4)  # type: ignore
    user_id: UUID
    period_start: datetime
    period_end: datetime
    llm_tokens_used: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "billing_usage_allowances"
        use_state_management = True
        indexes: ClassVar[list[list[tuple[str, int]]]] = [
            [("user_id", 1), ("period_start", 1)],
        ]


class UsageWindowCounter(Document):
    """Per-user, rolling-window usage counter ("session" 5h / "weekly" 7d).

    Unlike ``UsageAllowance``, windows are not calendar-aligned: a new window
    only starts the first time usage is recorded after the previous one's
    ``window_end`` has passed.
    """

    id: UUID = Field(default_factory=uuid4)  # type: ignore
    user_id: UUID
    window_type: Literal["session", "weekly"]
    window_start: datetime
    window_end: datetime
    llm_tokens_used: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "billing_usage_window_counters"
        use_state_management = True
        indexes: ClassVar[list[list[tuple[str, int]]]] = [
            [("user_id", 1), ("window_type", 1)],
        ]


class ProcessedWebhookEvent(Document):
    """Records a Polar webhook delivery id so retried deliveries are a no-op."""

    id: UUID = Field(default_factory=uuid4)  # type: ignore
    webhook_id: str
    event_type: str
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "billing_processed_webhook_events"
        use_state_management = True
        indexes: ClassVar[list[list[tuple[str, int]]]] = [
            [("webhook_id", 1)],
        ]
