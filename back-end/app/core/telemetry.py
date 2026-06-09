import logging

import logfire
from sqlalchemy.engine import Engine

from app.core.config import Settings

logger = logging.getLogger("app.telemetry")


def setup_telemetry(settings: Settings) -> None:
    """Configure Logfire telemetry and instrumentation globally."""
    if not settings.logfire_token:
        return

    try:
        logfire.configure(
            token=settings.logfire_token,
            service_name="personal-rag-backend",
        )
        logfire.instrument_pydantic_ai()
        logger.info("Logfire telemetry initialized successfully for Pydantic AI.")
    except Exception:
        logger.exception("Failed to initialize Logfire telemetry")


def setup_db_logging(engine: Engine) -> None:
    """Instrument the SQLAlchemy engine with Logfire."""
    try:
        logfire.instrument_sqlalchemy(engine=engine)
        logger.info("SQLAlchemy engine instrumented successfully with Logfire.")
    except Exception:
        logger.exception("Failed to instrument SQLAlchemy engine")
