from typing import Any

from fastapi import status


class TransientProviderError(RuntimeError):
    """A retryable upstream provider failure (rate limit, 5xx, network).

    Raised by the provider layers (e.g. embeddings) so callers can distinguish
    "try again later" from a permanently failing input without knowing each
    provider SDK's exception hierarchy.
    """


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        detail: str | dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
        super().__init__(detail)


class CouldNotValidateCredentialsError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
