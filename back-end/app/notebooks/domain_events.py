"""Domain events emitted as notebook documents and reports change state.

Each event carries the Beanie document it concerns so listeners — notably the
SSE projection in ``app.notebooks.listeners`` — can build their payload without
an extra database read. The event classes mirror the status transitions that
previously called ``publish_document_event`` / ``publish_report_event`` inline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.event_bus import DomainEvent

if TYPE_CHECKING:
    from app.notebooks.models import NotebookDocument, NotebookReport


@dataclass(frozen=True, eq=False)
class DocumentEvent(DomainEvent):
    """Base class for notebook-document lifecycle events."""

    document: NotebookDocument


@dataclass(frozen=True, eq=False)
class DocumentRegistered(DocumentEvent):
    """A document row was created (status ``pending``)."""


@dataclass(frozen=True, eq=False)
class DocumentUploaded(DocumentEvent):
    """The object became visible in storage / was reset for retry (``uploaded``)."""


@dataclass(frozen=True, eq=False)
class DocumentProcessing(DocumentEvent):
    """A document was claimed for ingestion (status ``processing``)."""


@dataclass(frozen=True, eq=False)
class DocumentIndexed(DocumentEvent):
    """Ingestion finished and the document is searchable (status ``indexed``)."""


@dataclass(frozen=True, eq=False)
class DocumentFailed(DocumentEvent):
    """Ingestion or upload failed (status ``failed``)."""


@dataclass(frozen=True, eq=False)
class ReportEvent(DomainEvent):
    """Base class for notebook-report lifecycle events."""

    report: NotebookReport


@dataclass(frozen=True, eq=False)
class ReportGenerating(ReportEvent):
    """Report generation started (status ``generating``)."""


@dataclass(frozen=True, eq=False)
class ReportCompleted(ReportEvent):
    """Report generation finished successfully (status ``completed``)."""


@dataclass(frozen=True, eq=False)
class ReportFailed(ReportEvent):
    """Report generation failed (status ``failed``)."""


@dataclass(frozen=True, eq=False)
class ReportCancelled(ReportEvent):
    """Report generation was cancelled by the user (status ``cancelled``)."""
