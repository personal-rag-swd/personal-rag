import logging
import time
from datetime import datetime
import logfire
from sqlalchemy import event
from sqlalchemy.engine import Engine
from app.core.config import Settings


logger = logging.getLogger("app.telemetry")
db_logger = logging.getLogger("app.db")


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
    except Exception as e:
        logger.error(f"Failed to initialize Logfire telemetry: {e}")


def setup_db_logging(engine: Engine) -> None:
    """Register SQLAlchemy event listeners to log database queries in a clean, beautiful format."""
    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        context._query_start_time = time.time()

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total_time = (time.time() - context._query_start_time) * 1000
        
        # Format query for visualization
        clean_statement = "\n│ ".join(
            line.strip() for line in statement.splitlines() if line.strip()
        )
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        db_logger.info(
            f"\n┌─── [SQL QUERY] ──────────────────────────────────────────────────\n"
            f"│ Timestamp: {current_time}\n"
            f"│ Duration:  {total_time:.2f}ms\n"
            f"│ Query:     {clean_statement}\n"
            f"│ Params:    {parameters}\n"
            f"└──────────────────────────────────────────────────────────────────"
        )


