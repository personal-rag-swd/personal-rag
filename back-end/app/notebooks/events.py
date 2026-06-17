from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from app.notebooks.schemas import NotebookDocumentRead, NotebookReportRead

logger = logging.getLogger(__name__)


class DocumentEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[UUID, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, user_id: UUID) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers[user_id].append(q)
        return q

    def unsubscribe(self, user_id: UUID, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(user_id, [])
        if q in subs:
            subs.remove(q)

    async def publish(self, user_id: UUID, event: dict) -> None:
        for q in self._subscribers.get(user_id, []):
            await q.put(event)


EventBus = DocumentEventBus
event_bus = DocumentEventBus()


async def publish_document_event(document, event_type: str = "document_update") -> None:
    serialized = NotebookDocumentRead.model_validate(document).model_dump(mode="json")
    await event_bus.publish(
        document.user_id,
        {
            "type": event_type,
            "notebook_id": str(document.notebook_id),
            "document": serialized,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


async def publish_report_event(report, event_type: str = "report_update") -> None:
    serialized = NotebookReportRead.model_validate(report).model_dump(mode="json")
    await event_bus.publish(
        report.user_id,
        {
            "type": event_type,
            "notebook_id": str(report.notebook_id),
            "report": serialized,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
