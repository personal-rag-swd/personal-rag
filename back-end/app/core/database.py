import asyncio
import logging

from pymongo import AsyncMongoClient

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def init_db() -> AsyncMongoClient:
    settings = get_settings()
    logger.info("Connecting to MongoDB at %s", settings.database_url)
    client = AsyncMongoClient(
        settings.database_url,
        serverSelectionTimeoutMS=5000,
        # BSON stores datetimes as naive UTC. Without tz_aware, PyMongo returns
        # them as naive datetimes, which then serialize to ISO strings with no
        # offset and get misread as local time by clients (e.g. a just-created
        # note showing "7 hours ago" in a UTC+7 timezone). tz_aware=True keeps
        # every datetime read back from Mongo UTC-aware end to end.
        tz_aware=True,
    )

    # Compose can mark MongoDB healthy slightly before the backend starts.
    # Retry the initial ping so startup is resilient to that timing gap.
    last_error: Exception | None = None
    for attempt in range(1, 31):
        try:
            await client.admin.command("ping")
        except Exception as exc:  # pragma: no cover - startup only
            last_error = exc
            logger.warning(
                "MongoDB ping failed on attempt %d/30: %s", attempt, exc
            )
            if attempt < 30:
                await asyncio.sleep(2)
        else:
            logger.info("MongoDB connection established")
            return client
    raise RuntimeError("Unable to connect to MongoDB during startup") from last_error
