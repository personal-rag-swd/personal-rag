from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.config import Settings, get_settings
from app.users.dependencies import get_current_user
from app.users.models import User
from app.file.schemas import PresignedUrlRequest, PresignedUrlResponse, FileCallbackPayload
from app.file.service import generate_presigned_url_service, handle_file_callback_service

router = APIRouter(prefix="/file", tags=["File Management"])


@router.post("/presigned-url", response_model=PresignedUrlResponse)
def get_presigned_url(
    request: PresignedUrlRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PresignedUrlResponse:
    return generate_presigned_url_service(request, current_user, settings)


@router.post("/callback")
async def file_callback(request: Request) -> dict:
    payload_dict = None
    try:
        payload_dict = await request.json()
    except Exception:
        pass

    # Robust parsing of empty/arbitrary payload into the Pydantic schema
    payload = FileCallbackPayload.model_validate(payload_dict or {})

    return handle_file_callback_service(
        payload=payload,
        headers=dict(request.headers),
        query_params=dict(request.query_params),
    )

