import logging
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.core.config import get_settings, validate_rag_embedding_dimension
from app.core.telemetry import setup_telemetry

# Configure logging and telemetry early
settings = get_settings()
setup_telemetry(settings)

log_level_name = settings.log_level.strip().upper()
log_level_value = getattr(logging, log_level_name, logging.INFO)

# Standard logging configuration
logging.basicConfig(
    level=log_level_value,
    format="%(levelname)s:     %(name)s - %(message)s",
    force=True,
)

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from scalar_fastapi import get_scalar_api_reference  # noqa: E402

from app.auth.router import router as auth_router  # noqa: E402
from app.file.router import router as file_router  # noqa: E402
from app.notebooks.router import router as notebooks_router  # noqa: E402
from app.notebooks.consumer import run_notebook_document_consumer  # noqa: E402
from app.users.router import router as users_router  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    validate_rag_embedding_dimension(settings)
    
    # Resolve Chat Model & Provider
    chat_prov = settings.chat_provider.strip().lower()
    chat_model = settings.chat_model
    
    # Resolve Embedding Model & Provider
    embed_prov = settings.embedding_provider.strip().lower()
    if embed_prov == "auto":
        embed_prov = "gemini" if settings.embedding_api_key else "openai_compatible"
    embed_model = settings.embedding_model
    
    logger = logging.getLogger("app.startup")
    logger.info("============================================================")
    logger.info("Application starting up with the following configuration:")
    logger.info(f"  Chat Provider:      {chat_prov.upper()}")
    logger.info(f"  Chat Model:         {chat_model}")
    logger.info(f"  Embedding Provider: {embed_prov.upper()}")
    logger.info(f"  Embedding Model:    {embed_model}")
    logger.info("============================================================")
    consumer_task: asyncio.Task[None] | None = None
    if settings.rabbitmq_consumer_enabled:
        consumer_task = asyncio.create_task(run_notebook_document_consumer(settings))
    try:
        yield
    finally:
        if consumer_task is not None:
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="Aviary", docs_url=None, redoc_url=None, lifespan=lifespan)

API_V1_PREFIX = "/api/v1"


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/docs", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )


@app.get("/ping")
async def ping():
    return {"ping": "pong"}

app.include_router(auth_router, prefix=API_V1_PREFIX)
app.include_router(users_router, prefix=API_V1_PREFIX)
app.include_router(file_router, prefix=API_V1_PREFIX)
app.include_router(notebooks_router, prefix=API_V1_PREFIX)
