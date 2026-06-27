import logging

import logfire

from app.core.config import Settings

logger = logging.getLogger("app.telemetry")


def setup_telemetry(settings: Settings) -> None:
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
