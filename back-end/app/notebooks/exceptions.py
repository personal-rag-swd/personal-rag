from fastapi import status

from app.core.exceptions import AppError


class TransientIngestionError(RuntimeError):
    """A retryable ingestion error that should trigger message requeue."""


class NotebookNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found",
        )


class DocumentNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )


class ReportNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )


class ChunkNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chunk not found",
        )


class LLMNotConfiguredError(AppError):
    def __init__(self, provider: str) -> None:
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service is not configured. Set the API key for the '{provider}' chat provider.",
        )


class NoIndexedDocumentsError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No indexed documents found in this notebook. Upload and wait for indexing to complete.",
        )


class CustomReportMissingInstructionsError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="additional_instructions is required for report_type 'custom'.",
        )


class CannotCancelReportError(AppError):
    def __init__(self, current_status: str) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel report with status '{current_status}'.",
        )


class ChunkNotAnImageError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chunk is not an image",
        )


class ImageNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )
