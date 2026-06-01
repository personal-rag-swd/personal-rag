from datetime import UTC, datetime
from pydantic_ai.capabilities.process_history import ProcessHistory
from pydantic_ai.messages import ModelMessage, ModelRequest
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.run import AgentRunResult
from pydantic_ai.ui.ag_ui import AGUIAdapter
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.database import get_session
from app.notebooks.agent import (
    chat_provider_is_configured,
    generate_blog_post,
    generate_briefing_doc,
    generate_custom_report,
    generate_study_guide,
    get_notebook_chat_agent,
)
from app.notebooks.memory import (
    append_notebook_chat_history,
    extract_notebook_chat_transcript,
    load_notebook_chat_history,
)
from app.notebooks.models import (
    Notebook,
    NotebookDocument,
    NotebookDocumentChunk,
    NotebookReport,
)
from app.notebooks.prompt import build_context_block
from app.notebooks.schemas import (
    BlogPostReport,
    BriefingDocReport,
    CustomReport,
    NotebookChatHistoryMessage,
    NotebookCreate,
    NotebookDocumentRead,
    NotebookPopulateRead,
    NotebookRead,
    NotebookReportRead,
    ReportGenerateRequest,
    StudyGuideReport,
    NotebookUpdate,
)
from app.notebooks.service import (
    create_notebook,
    delete_notebook,
    delete_notebook_document,
    get_notebook,
    list_notebook_documents,
    list_notebooks,
    populate_notebook_metrics,
    touch_notebook,
    update_notebook,
)
from app.notebooks.tools import search_notebook_chunks
from app.users.dependencies import get_current_user
from app.users.models import User

# Maximum characters of source text fed to the LLM for report generation.
# ~120 k chars ≈ 30 k tokens, safely within most context windows.
_REPORT_CONTEXT_CHAR_LIMIT = 120_000





router = APIRouter(prefix="/notebooks", tags=["Notebooks"])

@router.get("/", response_model=list[NotebookRead])
def read_notebooks(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list:
    return list_notebooks(session, current_user)


@router.post("/", response_model=NotebookRead, status_code=status.HTTP_201_CREATED)
def create_notebook_route(
    payload: NotebookCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    return create_notebook(session, payload, current_user)


@router.get("/{notebook_id}", response_model=NotebookRead)
def read_notebook(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    return get_notebook(session, notebook_id, current_user)


@router.patch("/{notebook_id}", response_model=NotebookRead)
def update_notebook_route(
    notebook_id: UUID,
    payload: NotebookUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    return update_notebook(session, notebook_id, payload, current_user)


@router.post("/{notebook_id}/touch", response_model=NotebookRead)
def touch_notebook_route(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    return touch_notebook(session, notebook_id, current_user)


@router.get("/{notebook_id}/populate", response_model=NotebookPopulateRead)
def populate_notebook_route(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    return populate_notebook_metrics(session, notebook_id, current_user)


@router.get("/{notebook_id}/documents", response_model=list[NotebookDocumentRead])
def read_notebook_documents(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list:
    return list_notebook_documents(session, notebook_id, current_user)


@router.delete(
    "/{notebook_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_notebook_document_route(
    notebook_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    delete_notebook_document(session, notebook_id, document_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{notebook_id}/chat")
async def chat_notebook_route(
    notebook_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    notebook = get_notebook(session, notebook_id, current_user)
    message_history = load_notebook_chat_history(session, notebook)

    settings = get_settings()

    def _context_retriever(query: str) -> str:
        chunks = search_notebook_chunks(
            session,
            notebook=notebook,
            current_user=current_user,
            query=query,
            settings=settings,
            top_k=6,
        )
        return build_context_block(chunks)

    async def persist_chat_history(result: AgentRunResult[object]) -> None:
        append_notebook_chat_history(session, notebook, result.new_messages())

    async def keep_recent(messages: list[ModelMessage]) -> list[ModelMessage]:
        system_prompts = []
        other_messages = []
        for msg in messages:
            is_system = False
            if isinstance(msg, ModelRequest):
                part_names = {type(part).__name__ for part in msg.parts}
                if "SystemPromptPart" in part_names:
                    is_system = True
                elif msg.instructions and not (part_names & {"UserPromptPart", "ToolReturnPart", "RetryPromptPart"}):
                    is_system = True

            if is_system:
                system_prompts.append(msg)
            else:
                other_messages.append(msg)

        # Keep the last 15 other messages
        recent_limit = 15
        recent_others = (
            other_messages[-recent_limit:] if len(other_messages) > recent_limit else other_messages
        )

        # Combine system prompts and recent others while maintaining their original relative chronological order
        keep_set = {id(msg) for msg in system_prompts} | {id(msg) for msg in recent_others}
        return [msg for msg in messages if id(msg) in keep_set]

    return await AGUIAdapter.dispatch_request(
        request,
        agent=get_notebook_chat_agent(_context_retriever),
        message_history=message_history,
        conversation_id=str(notebook.id),
        on_complete=persist_chat_history,
        capabilities=[ProcessHistory(keep_recent)]
    )


@router.get("/{notebook_id}/chat/history", response_model=list[NotebookChatHistoryMessage])
def read_notebook_chat_history(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    include_reasoning: bool = False,
) -> list[dict[str, object]]:
    notebook = get_notebook(session, notebook_id, current_user)
    return extract_notebook_chat_transcript(session, notebook, include_reasoning=include_reasoning)


@router.get("/{notebook_id}/documents/chunks", response_model=list[dict[str, object]])
def read_document_chunks(
    notebook_id: UUID,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list:
    notebook = get_notebook(session, notebook_id, current_user)
    document = session.exec(
        select(NotebookDocument).where(
            NotebookDocument.notebook_id == notebook.id,
            NotebookDocument.filename == filename,
            NotebookDocument.user_id == current_user.id,
        )
    ).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    chunks = session.exec(
        select(NotebookDocumentChunk)
        .where(NotebookDocumentChunk.document_id == document.id)
        .order_by(NotebookDocumentChunk.chunk_index.asc())
    ).all()

    return [
        {
            "id": str(c.id),
            "document_id": str(c.document_id),
            "chunk_index": c.chunk_index,
            "content": c.content,
            "metadata": c.chunk_metadata,
        }
        for c in chunks
    ]


@router.get("/{notebook_id}/documents/{document_id}/chunks", response_model=list[dict[str, object]])
def read_document_chunks_by_id(
    notebook_id: UUID,
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[dict[str, object]]:
    notebook = get_notebook(session, notebook_id, current_user)
    document = session.exec(
        select(NotebookDocument).where(
            NotebookDocument.id == document_id,
            NotebookDocument.notebook_id == notebook.id,
            NotebookDocument.user_id == current_user.id,
        )
    ).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    chunks = session.exec(
        select(NotebookDocumentChunk)
        .where(NotebookDocumentChunk.document_id == document.id)
        .where(NotebookDocumentChunk.notebook_id == notebook.id)
        .where(NotebookDocumentChunk.user_id == current_user.id)
        .order_by(NotebookDocumentChunk.chunk_index.asc())
    ).all()

    return [
        {
            "id": str(c.id),
            "document_id": str(c.document_id),
            "chunk_index": c.chunk_index,
            "content": c.content,
            "metadata": c.chunk_metadata,
        }
        for c in chunks
    ]


@router.get("/{notebook_id}/chunks", response_model=dict[str, object])
def read_notebook_chunk(
    notebook_id: UUID,
    filename: str,
    chunk_index: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    notebook = get_notebook(session, notebook_id, current_user)
    chunk = session.exec(
        select(NotebookDocumentChunk)
        .join(NotebookDocument, NotebookDocument.id == NotebookDocumentChunk.document_id)
        .where(NotebookDocument.filename == filename)
        .where(NotebookDocumentChunk.chunk_index == chunk_index)
        .where(NotebookDocumentChunk.notebook_id == notebook.id)
        .where(NotebookDocumentChunk.user_id == current_user.id)
    ).first()
    if not chunk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found")

    return {
        "content": chunk.content,
        "filename": filename,
        "chunk_index": chunk_index,
    }


@router.get("/{notebook_id}/documents/{document_id}/chunks/{chunk_index}", response_model=dict[str, object])
def read_notebook_chunk_by_document_id(
    notebook_id: UUID,
    document_id: UUID,
    chunk_index: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    notebook = get_notebook(session, notebook_id, current_user)
    chunk = session.exec(
        select(NotebookDocumentChunk)
        .where(NotebookDocumentChunk.document_id == document_id)
        .where(NotebookDocumentChunk.chunk_index == chunk_index)
        .where(NotebookDocumentChunk.notebook_id == notebook.id)
        .where(NotebookDocumentChunk.user_id == current_user.id)
    ).first()
    if not chunk:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found")

    document = session.exec(
        select(NotebookDocument).where(
            NotebookDocument.id == document_id,
            NotebookDocument.notebook_id == notebook.id,
            NotebookDocument.user_id == current_user.id,
        )
    ).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return {
        "id": str(chunk.id),
        "document_id": str(chunk.document_id),
        "filename": document.filename,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "metadata": chunk.chunk_metadata,
    }


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notebook_route(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    delete_notebook(session, notebook_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _build_report_context(session: Session, notebook: Notebook, current_user: User) -> str:
    """Return all indexed chunk text for a notebook, up to the char limit."""
    chunks = session.exec(
        select(NotebookDocumentChunk, NotebookDocument.filename)
        .join(NotebookDocument, NotebookDocument.id == NotebookDocumentChunk.document_id)
        .where(NotebookDocumentChunk.notebook_id == notebook.id)
        .where(NotebookDocumentChunk.user_id == current_user.id)
        .where(NotebookDocument.status == "indexed")
        .order_by(NotebookDocument.filename, NotebookDocumentChunk.chunk_index)
    ).all()

    if not chunks:
        return ""

    parts: list[str] = []
    total = 0
    for chunk, filename in chunks:
        header = f"[file={filename} chunk={chunk.chunk_index}]"
        block = f"{header}\n{chunk.content}"
        if total + len(block) > _REPORT_CONTEXT_CHAR_LIMIT:
            break
        parts.append(block)
        total += len(block)

    return "\n\n".join(parts)


@router.post(
    "/{notebook_id}/reports",
    response_model=NotebookReportRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_notebook_report(
    notebook_id: UUID,
    payload: ReportGenerateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    notebook = get_notebook(session, notebook_id, current_user)

    if not chat_provider_is_configured():
        provider = get_settings().chat_provider.strip().lower()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service is not configured. Set the API key for the '{provider}' chat provider.",
        )

    context = _build_report_context(session, notebook, current_user)
    if not context:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No indexed documents found in this notebook. Upload and wait for indexing to complete.",
        )

    instructions = (payload.additional_instructions or "").strip() or None
    if payload.report_type == "custom" and not instructions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="additional_instructions is required for report_type 'custom'.",
        )

    report_content: BriefingDocReport | StudyGuideReport | BlogPostReport | CustomReport
    try:
        match payload.report_type:
            case "briefing":
                report_content = await generate_briefing_doc(context, instructions)
            case "study_guide":
                report_content = await generate_study_guide(context, instructions)
            case "blog":
                report_content = await generate_blog_post(context, instructions)
            case "custom":
                report_content = await generate_custom_report(context, instructions)
    except ModelHTTPError as exc:
        # Surface provider failures (rate limits, upstream errors) cleanly instead
        # of an opaque 500. Free-tier Gemini in particular returns 429 when the
        # daily request quota is exhausted.
        if exc.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="The AI provider rate limit was exceeded. Please wait a moment and try again.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI provider failed to generate the report. Please try again.",
        ) from exc

    now = datetime.now(UTC)
    report = NotebookReport(
        notebook_id=notebook.id,
        user_id=current_user.id,
        report_type=payload.report_type,
        content=report_content.model_dump(),
        created_at=now,
        updated_at=now,
    )
    try:
        session.add(report)
        session.commit()
        session.refresh(report)
    except SQLAlchemyError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error") from exc

    return report


@router.get("/{notebook_id}/reports", response_model=list[NotebookReportRead])
def list_notebook_reports(
    notebook_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list:
    notebook = get_notebook(session, notebook_id, current_user)
    return list(
        session.exec(
            select(NotebookReport)
            .where(NotebookReport.notebook_id == notebook.id)
            .where(NotebookReport.user_id == current_user.id)
            .order_by(NotebookReport.created_at.desc())
        ).all()
    )


@router.get("/{notebook_id}/reports/{report_id}", response_model=NotebookReportRead)
def get_notebook_report(
    notebook_id: UUID,
    report_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> object:
    notebook = get_notebook(session, notebook_id, current_user)
    report = session.exec(
        select(NotebookReport).where(
            NotebookReport.id == report_id,
            NotebookReport.notebook_id == notebook.id,
            NotebookReport.user_id == current_user.id,
        )
    ).first()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report
