"""In-process pub/sub that fans notebook state changes out to SSE streams.

The bus has two layers:

* :class:`NotebookEventBus` — transport. One queue per active SSE connection
  (a user may have several open tabs), keyed by ``user_id``. Publishers call
  :meth:`NotebookEventBus.publish`; the SSE handler drains a queue via the
  :meth:`NotebookEventBus.subscribe` context manager.
* ``build_*`` helpers — envelope construction. They turn Beanie documents into
  the exact wire dicts the frontend parses (see ``NotebookDocumentEvent`` in
  ``front-end/src/features/notebooks/types.ts``); the event ``type`` strings
  here must stay in lockstep with that union.

Delivery is deliberately fire-and-forget: a subscriber that falls behind has
its oldest buffered event dropped rather than applying back-pressure to the
ingestion or report pipelines that publish. Dropped events are tolerable
because the SSE handler replays a full snapshot on every (re)connect.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from app.notebooks.schemas import NotebookDocumentRead, NotebookReportRead

logger = logging.getLogger(__name__)

# Events buffered per subscriber before the oldest is dropped. Sized to absorb a
# brief browser stall without unbounded memory growth; see module docstring.
SUBSCRIBER_QUEUE_MAXSIZE = 256

NotebookEventType = Literal[
    "snapshot",
    "document_update",
    "report_snapshot",
    "report_update",
]

# Wire-format envelope sent to the browser. Kept as a plain dict (not a Pydantic
# model) because it is JSON-encoded verbatim and the frontend owns the schema.
NotebookEvent = dict[str, Any]


def _envelope(
    event_type: NotebookEventType, notebook_id: UUID, **payload: Any
) -> NotebookEvent:
    return {
        "type": event_type,
        "notebook_id": str(notebook_id),
        **payload,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def build_document_event(
    document: Any, event_type: NotebookEventType = "document_update"
) -> NotebookEvent:
    serialized = NotebookDocumentRead.model_validate(document).model_dump(mode="json")
    return _envelope(event_type, document.notebook_id, document=serialized)


def build_report_event(
    report: Any, event_type: NotebookEventType = "report_update"
) -> NotebookEvent:
    serialized = NotebookReportRead.model_validate(report).model_dump(mode="json")
    return _envelope(event_type, report.notebook_id, report=serialized)


def build_document_snapshots(documents: Iterable[Any]) -> list[NotebookEvent]:
    """Group a user's documents by notebook into one ``snapshot`` event each."""
    by_notebook: dict[UUID, list[Any]] = defaultdict(list)
    for document in documents:
        by_notebook[document.notebook_id].append(document)
    return [
        _envelope(
            "snapshot",
            notebook_id,
            documents=[
                NotebookDocumentRead.model_validate(doc).model_dump(mode="json")
                for doc in docs
            ],
        )
        for notebook_id, docs in by_notebook.items()
    ]


def build_report_snapshots(reports: Iterable[Any]) -> list[NotebookEvent]:
    """Group a user's reports by notebook into one ``report_snapshot`` event each."""
    by_notebook: dict[UUID, list[Any]] = defaultdict(list)
    for report in reports:
        by_notebook[report.notebook_id].append(report)
    return [
        _envelope(
            "report_snapshot",
            notebook_id,
            reports=[
                NotebookReportRead.model_validate(report).model_dump(mode="json")
                for report in notebook_reports
            ],
        )
        for notebook_id, notebook_reports in by_notebook.items()
    ]


class NotebookEventBus:
    """Per-user fan-out of notebook events to active SSE connections."""

    def __init__(self, *, queue_maxsize: int = SUBSCRIBER_QUEUE_MAXSIZE) -> None:
        self._queue_maxsize = queue_maxsize
        self._subscribers: dict[UUID, list[asyncio.Queue[NotebookEvent]]] = defaultdict(
            list
        )

    @asynccontextmanager
    async def subscribe(
        self, user_id: UUID
    ) -> AsyncIterator[asyncio.Queue[NotebookEvent]]:
        """Yield a queue receiving ``user_id``'s events; unsubscribed on exit."""
        queue: asyncio.Queue[NotebookEvent] = asyncio.Queue(maxsize=self._queue_maxsize)
        self._subscribers[user_id].append(queue)
        try:
            yield queue
        finally:
            self._unsubscribe(user_id, queue)

    def _unsubscribe(self, user_id: UUID, queue: asyncio.Queue[NotebookEvent]) -> None:
        subscribers = self._subscribers.get(user_id)
        if not subscribers:
            return
        if queue in subscribers:
            subscribers.remove(queue)
        if not subscribers:
            # Drop the key so the map doesn't grow once-per-user-ever.
            del self._subscribers[user_id]

    async def publish(self, user_id: UUID, event: NotebookEvent) -> None:
        # Iterate a snapshot of the subscriber list: cheap insurance against a
        # concurrent (un)subscribe mutating it mid-fan-out.
        for queue in tuple(self._subscribers.get(user_id, ())):
            self._offer(queue, event)

    def _offer(self, queue: asyncio.Queue[NotebookEvent], event: NotebookEvent) -> None:
        """Enqueue without blocking, evicting the oldest event if the queue is full."""
        while True:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    dropped = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                logger.warning(
                    "Dropped stale '%s' event for a slow SSE subscriber",
                    dropped.get("type"),
                )
            else:
                return


event_bus = NotebookEventBus()

# Backwards-compatible aliases for the bus's former name.
DocumentEventBus = NotebookEventBus
EventBus = NotebookEventBus


async def publish_document_event(
    document: Any, event_type: NotebookEventType = "document_update"
) -> None:
    await event_bus.publish(
        document.user_id, build_document_event(document, event_type)
    )


async def publish_report_event(
    report: Any, event_type: NotebookEventType = "report_update"
) -> None:
    await event_bus.publish(report.user_id, build_report_event(report, event_type))
