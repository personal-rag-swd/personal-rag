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
    )
    # Ping to verify connection
    await client.admin.command("ping")
    logger.info("MongoDB connection established")
    return client
