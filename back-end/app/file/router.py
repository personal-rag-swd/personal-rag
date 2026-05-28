from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlmodel import Session

from app.core.database import engine, get_session
from app.core.config import Settings, get_settings
from app.users.dependencies import get_current_user
from app.users.models import User
from app.file.schemas import PresignedUrlRequest, PresignedUrlResponse, FileCallbackPayload, UploadFailedRequest
from app.file.service import generate_presigned_url_service, handle_file_callback_service
from app.notebooks.tools import ingest_document_by_id, mark_document_upload_failed

router = APIRouter(prefix="/file", tags=["File Management"])


@router.post("/presigned-url", response_model=PresignedUrlResponse)
def get_presigned_url(
    request: PresignedUrlRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_session)],
) -> PresignedUrlResponse:
    return generate_presigned_url_service(request, current_user, settings, session)


def _run_document_ingestion(document_id: str, settings: Settings) -> None:
    with Session(engine) as session:
        ingest_document_by_id(session, UUID(document_id), settings)


@router.post("/callback")
async def file_callback(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    payload_dict = None
    try:
        payload_dict = await request.json()
    except Exception:
        pass

    # Robust parsing of empty/arbitrary payload into the Pydantic schema
    payload = FileCallbackPayload.model_validate(payload_dict or {})

    with Session(engine) as session:
        result = handle_file_callback_service(
            payload=payload,
            headers=dict(request.headers),
            query_params=dict(request.query_params),
            session=session,
        )
    document_id = result.get("details", {}).get("document_id")
    if document_id:
        background_tasks.add_task(_run_document_ingestion, document_id, settings)
    return result


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
