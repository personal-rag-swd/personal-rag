"""Listeners that react to notebook domain events.

These listeners project document/report state changes onto the SSE transport
(``NotebookEventBus``) so the browser stays in sync — the behavior that
previously lived inline in ``publish_document_event`` / ``publish_report_event``.
"""

from __future__ import annotations

from app.core.event_bus import DomainEventBus, domain_event_bus
from app.notebooks.domain_events import DocumentEvent, ReportEvent
from app.notebooks.events import build_document_event, build_report_event, event_bus


async def project_document_event(event: DocumentEvent) -> None:
    """Fan a document state change out to the user's SSE connections."""
    document = event.document
    await event_bus.publish(document.user_id, build_document_event(document))


async def project_report_event(event: ReportEvent) -> None:
    """Fan a report state change out to the user's SSE connections."""
    report = event.report
    await event_bus.publish(report.user_id, build_report_event(report))


def register_notebook_event_listeners(bus: DomainEventBus = domain_event_bus) -> None:
    """Wire the notebook listeners onto ``bus`` (idempotent)."""
    bus.subscribe(DocumentEvent, project_document_event)
    bus.subscribe(ReportEvent, project_report_event)
