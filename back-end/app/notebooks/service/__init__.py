"""Notebook service layer.

Split into cohesive modules by responsibility while preserving the historical
``app.notebooks.service`` import surface. Callers should keep importing names
from ``app.notebooks.service`` rather than the submodules directly.
"""

from app.notebooks.service.chat import (
    NotebookChatContext,
    persist_notebook_chat_result,
    prepare_notebook_chat,
)
from app.notebooks.service.chunks import (
    build_chunk_image_url,
    get_chunks_by_document_id,
    get_chunks_by_filename,
    get_single_chunk,
)
from app.notebooks.service.documents import (
    delete_notebook_document,
    get_notebook_document,
    get_owned_document,
    list_notebook_documents,
    load_document_bytes,
    resolve_scoped_document_ids,
)
from app.notebooks.service.notebooks import (
    create_notebook,
    delete_notebook,
    get_notebook,
    get_user_event_snapshot,
    list_notebooks,
    populate_notebook_metrics,
    touch_notebook,
    update_notebook,
)
from app.notebooks.service.notes import create_note
from app.notebooks.service.recovery import recover_pending_reports
from app.notebooks.service.reports import (
    PendingReportPlan,
    build_report_context,
    cancel_report,
    create_pending_report,
    delete_report,
    get_notebook_report,
    get_report,
    list_reports,
    run_report_generation,
)

__all__ = [
    "NotebookChatContext",
    "PendingReportPlan",
    "build_chunk_image_url",
    "build_report_context",
    "cancel_report",
    "create_note",
    "create_notebook",
    "create_pending_report",
    "delete_notebook",
    "delete_notebook_document",
    "delete_report",
    "get_chunks_by_document_id",
    "get_chunks_by_filename",
    "get_notebook",
    "get_notebook_document",
    "get_notebook_report",
    "get_owned_document",
    "get_report",
    "get_single_chunk",
    "get_user_event_snapshot",
    "list_notebook_documents",
    "list_notebooks",
    "list_reports",
    "load_document_bytes",
    "persist_notebook_chat_result",
    "populate_notebook_metrics",
    "prepare_notebook_chat",
    "recover_pending_reports",
    "resolve_scoped_document_ids",
    "run_report_generation",
    "touch_notebook",
    "update_notebook",
]
