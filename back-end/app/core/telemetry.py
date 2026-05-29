import logging
import logfire
from fastapi import FastAPI
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
        logfire.instrument_pydantic()
        logfire.instrument_sqlalchemy()
        logger.info("Logfire telemetry initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Logfire telemetry: {e}")


def instrument_app(app: FastAPI, settings: Settings) -> None:
    """Instrument the FastAPI application instance with Logfire."""
    if settings.logfire_token:
        try:
            logfire.instrument_fastapi(app)
            logger.info("FastAPI application instrumented with Logfire.")
        except Exception as e:
            logger.error(f"Failed to instrument FastAPI application: {e}")
