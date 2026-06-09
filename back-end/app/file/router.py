from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.file.schemas import (
    PresignedUrlRequest,
    PresignedUrlResponse,
    UploadFailedRequest,
)
from app.file.service import generate_presigned_url_service
from app.notebooks.tools import mark_document_upload_failed
from app.users.dependencies import get_current_user
from app.users.models import User

router = APIRouter(prefix="/file", tags=["File Management"])


@router.post("/presigned-url", response_model=PresignedUrlResponse)
def get_presigned_url(
    request: PresignedUrlRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_session)],
) -> PresignedUrlResponse:
    return generate_presigned_url_service(request, current_user, settings, session)


@router.post("/upload-failed")
def report_upload_failed(
    request: UploadFailedRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    marked = mark_document_upload_failed(
        session,
        key=request.key,
        user_id=current_user.id,
        error_message=request.error_message,
    )
    return {"status": "ok", "updated": marked}
