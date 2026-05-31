from __future__ import annotations

import asyncio
import logging

from sqlmodel import Session

from app.core.config import Settings
from app.core.database import engine
from app.notebooks.tools.ingestion import process_unprocessed_notebook_documents

logger = logging.getLogger(__name__)


def _process_notebook_document_batch(settings: Settings) -> dict[str, int]:
    with Session(engine) as session:
        return process_unprocessed_notebook_documents(
            session,
            settings,
            limit=settings.file_ingestion_worker_batch_size,
        )


async def run_notebook_document_worker(settings: Settings) -> None:
    """Continuously poll object storage-backed notebook uploads for ingestion."""
    logger.info("Notebook document ingestion worker started")
    while True:
        try:
            stats = await asyncio.to_thread(
                _process_notebook_document_batch,
                settings,
            )
            if stats["checked"]:
                logger.info("Notebook document ingestion worker tick: %s", stats)
        except asyncio.CancelledError:
            logger.info("Notebook document ingestion worker stopped")
            raise
        except Exception:
            logger.exception("Notebook document ingestion worker tick failed")

        await asyncio.sleep(settings.file_ingestion_worker_interval_seconds)
