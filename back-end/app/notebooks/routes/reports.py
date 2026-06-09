from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Response,
    status,
)
from sqlmodel import Session

from app.core.database import get_session
from app.notebooks.report_service import (
    build_report_context,
    cancel_report,
    create_pending_report,
    delete_report,
    ensure_report_generation_available,
    get_report,
    list_reports,
    run_report_generation,
    validate_report_request,
)
from app.notebooks.schemas import NotebookReportRead, ReportGenerateRequest
from app.notebooks.service import get_notebook
from app.users.dependencies import get_current_user
from app.users.models import User

router = APIRouter()


@router.post(
    "/{notebook_id}/reports",
    response_model=NotebookReportRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a notebook report",
)
async def generate_notebook_report(
    notebook_id: UUID,
    payload: ReportGenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> NotebookReportRead:
    notebook = get_notebook(session, notebook_id, current_user)

    try:
        ensure_report_generation_available()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    context = build_report_context(session, notebook, current_user)
    if not context:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No indexed documents found in this notebook. Upload and wait for indexing to complete.",
        )

    try:
        instructions = validate_report_request(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    try:
        report = create_pending_report(
            session, notebook, current_user, payload, instructions
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    session_engine = session.get_bind()
    background_tasks.add_task(
        run_report_generation,
        report_id=report.id,
        report_type=payload.report_type,
        context=context,
        instructions=instructions,
        detail_level=payload.detail_level,
        _engine=session_engine,
    )
    return report


@router.post(
    "/{notebook_id}/reports/{report_id}/cancel",
    response_model=NotebookReportRead,
)
def cancel_notebook_report(
    notebook_id: UUID,
    report_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> NotebookReportRead:
    notebook = get_notebook(session, notebook_id, current_user)
    try:
        return cancel_report(session, notebook, current_user, report_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{notebook_id}/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_notebook_report(
    notebook_id: UUID,
    report_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    notebook = get_notebook(session, notebook_id, current_user)
    try:
        delete_report(session, notebook, current_user, report_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{notebook_id}/reports", response_model=list[NotebookReportRead])
def list_notebook_reports(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[NotebookReportRead]:
    notebook = get_notebook(session, notebook_id, current_user)
    return list_reports(session, notebook, current_user)


@router.get("/{notebook_id}/reports/{report_id}", response_model=NotebookReportRead)
def get_notebook_report(
    notebook_id: UUID,
    report_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> NotebookReportRead:
    notebook = get_notebook(session, notebook_id, current_user)
    try:
        return get_report(session, notebook, current_user, report_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
