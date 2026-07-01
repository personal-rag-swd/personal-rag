"""Periodic background task that batches local usage events to Polar.

Mirrors ``notebooks.rag.ingestion_service.process_unprocessed_notebook_documents``:
a simple asyncio polling loop started/cancelled from the FastAPI ``lifespan``,
so usage reporting survives process restarts without needing new infra
(RabbitMQ, a scheduler, etc.) for this volume of events.
"""

from __future__ import annotations

import asyncio
import logging

from app.billing.service import emit_pending_usage_events_to_polar
from app.core.config import Settings

logger = logging.getLogger(__name__)


async def run_usage_emission_task(settings: Settings) -> None:
    if not settings.polar_api_key:
        logger.info("Polar API key not configured; usage emission task disabled")
        return

    while True:
        try:
            stats = await emit_pending_usage_events_to_polar(settings)
            if stats["checked"]:
                logger.info("Usage emission batch: %s", stats)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Usage emission batch failed")
        await asyncio.sleep(settings.polar_usage_emit_interval_seconds)
