from fastapi import status

from app.core.exceptions import AppError


class ForbiddenError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ForbiddenError",
        )
