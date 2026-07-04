from fastapi import status

from app.core.exceptions import AppError


class UserNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )


class SelfModificationError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins cannot demote or deactivate themselves",
        )


class DocumentNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )


class DocumentContentUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document content is unavailable",
        )
