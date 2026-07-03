"""Outbound sync: emit locally-recorded usage events to Polar's meter.

Runs as a background worker (see ``billing/tasks.py``). Failed batches bump a
retry counter and are left unsent rather than dropped, so metering is
eventually-consistent with Polar without losing ledger entries.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.billing.models import UsageEventLog
from app.billing.polar_client import (
    PolarAPIError,
    PolarClientProtocol,
    get_polar_client,
)
from app.core.config import Settings

logger = logging.getLogger(__name__)

_METER_EVENT_NAME = "llm_usage"


async def emit_pending_usage_events_to_polar(
    settings: Settings, *, client: PolarClientProtocol | None = None
) -> dict[str, int]:
    resolved_client = client or get_polar_client(settings)
    stats = {"checked": 0, "ingested": 0, "failed": 0}

    pending = (
        await UsageEventLog.find({"polar_ingested": False})
        .limit(settings.polar_usage_emit_batch_size)
        .to_list()
    )
    if not pending:
        return stats

    stats["checked"] = len(pending)
    events = [
        {
            "name": _METER_EVENT_NAME,
            "external_customer_id": str(log.user_id),
            "metadata": {"quantity": log.quantity, **log.event_metadata},
        }
        for log in pending
    ]

    try:
        await resolved_client.ingest_events(events)
    except PolarAPIError:
        logger.warning(
            "Polar usage event ingestion failed for %d event(s); will retry",
            len(pending),
        )
        for log in pending:
            log.retry_count += 1
            log.polar_ingest_error = "Polar events ingest request failed"
            if log.retry_count > settings.polar_usage_emit_max_retries:
                logger.exception(
                    "Usage event %s exceeded max retries; leaving unsent for "
                    "manual attention",
                    log.id,
                )
            await log.save()
        stats["failed"] = len(pending)
        return stats

    now = datetime.now(UTC)
    for log in pending:
        log.polar_ingested = True
        log.polar_ingested_at = now
        log.polar_ingest_error = None
        await log.save()
    stats["ingested"] = len(pending)
    return stats
