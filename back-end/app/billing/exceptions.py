from datetime import datetime

from fastapi import status

from app.core.exceptions import AppError

_WINDOW_MESSAGES = {
    "session": "Session token limit reached. Please try again later.",
    "weekly": "Weekly token limit reached. Please try again later.",
    "monthly": (
        "Monthly LLM token usage limit was exceeded. Upgrade your plan to continue."
    ),
}


class UsageQuotaExceededError(AppError):
    def __init__(
        self, window: str = "monthly", reset_at: datetime | None = None
    ) -> None:
        self.window = window
        self.reset_at = reset_at
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": _WINDOW_MESSAGES.get(window, _WINDOW_MESSAGES["monthly"]),
                "window": window,
                "reset_at": reset_at.isoformat() if reset_at else None,
            },
        )


class BillingNotConfiguredError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not configured on this server",
        )


class WebhookSignatureInvalidError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )


class NoActiveBillingCustomerError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No billing customer found for this account",
        )
