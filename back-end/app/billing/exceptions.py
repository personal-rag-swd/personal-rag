from fastapi import status

from app.core.exceptions import AppError


class UsageQuotaExceededError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                "Free-tier LLM token usage limit was exceeded. "
                "Upgrade your plan to continue."
            ),
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
