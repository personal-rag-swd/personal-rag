from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.file.schemas import (
    PresignedUrlRequest,
    PresignedUrlResponse,
    UploadFailedRequest,
)
from app.file.service import generate_presigned_url_service, mark_upload_failed
from app.users.dependencies import get_current_user
from app.users.models import User

router = APIRouter(prefix="/file", tags=["File Management"])


@router.post("/presigned-url", response_model=PresignedUrlResponse)
async def get_presigned_url(
    request: PresignedUrlRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PresignedUrlResponse:
    return await generate_presigned_url_service(request, current_user, settings)


@router.post("/upload-failed")
async def report_upload_failed(
    request: UploadFailedRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return await mark_upload_failed(request, current_user.id)
