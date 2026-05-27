from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.users.dependencies import get_current_user
from app.users.models import User
from app.file.schemas import PresignedUrlRequest, PresignedUrlResponse
from app.file.service import generate_presigned_url_service

router = APIRouter(prefix="/file", tags=["File Management"])


@router.post("/presigned-url", response_model=PresignedUrlResponse)
def get_presigned_url(
    request: PresignedUrlRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PresignedUrlResponse:
    return generate_presigned_url_service(request, current_user, settings)
