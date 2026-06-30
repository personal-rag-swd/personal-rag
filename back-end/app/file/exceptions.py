from fastapi import status

from app.core.exceptions import AppError


class InvalidOperationError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Operation must be either 'upload' or 'download'",
        )


class InvalidFilenameCharactersError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid characters or directory traversal detected",
        )


class EmptyFilenameError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename cannot be empty after sanitization",
        )


class UnsupportedNotebookSourceContentTypeError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported notebook source content type",
        )


class ForbiddenResourceError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ForbiddenError: You do not have access to this resource",
        )


class PresignedUrlGenerationFailedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate presigned URL",
        )
