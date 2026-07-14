import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from beanie import init_beanie

from app.core.config import get_settings
from app.core.database import init_db
from app.core.telemetry import setup_telemetry

# Configure logging and telemetry early
settings = get_settings()
setup_telemetry(settings)

log_level_name = settings.log_level.strip().upper()
log_level_value = logging.getLevelNamesMapping().get(log_level_name, logging.INFO)

logging.basicConfig(
    level=log_level_value,
    format="%(levelname)s:     %(name)s - %(message)s",
    force=True,
)

# Suppress MongoDB driver's noisy heartbeat / topology logs
for name in (
    "pymongo.server",
    "pymongo.topology",
    "pymongo.heartbeat",
    "pymongo.monitor",
):
    logging.getLogger(name).setLevel(logging.WARNING)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from scalar_fastapi import get_scalar_api_reference

from app.admin.router import router as admin_router
from app.auth.models import PasswordResetRequest, PendingRegistration, RefreshToken
from app.auth.router import router as auth_router
from app.billing.models import (
    BillingCustomer,
    ProcessedWebhookEvent,
    UsageAllowance,
    UsageEventLog,
    UsageWindowCounter,
)
from app.billing.router import router as billing_router
from app.billing.tasks import run_usage_emission_task
from app.core.exceptions import AppError
from app.event_listeners import register_default_event_listeners
from app.file.router import router as file_router
from app.notebooks.consumer import run_notebook_document_consumer
from app.notebooks.models import (
    Notebook,
    NotebookDocument,
    NotebookDocumentChunk,
    NotebookMessage,
    NotebookReport,
)
from app.notebooks.router import router as notebooks_router
from app.notebooks.service import recover_pending_reports
from app.users.models import User
from app.users.router import router as users_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    mongo_client = await init_db()

    document_models = [
        User,
        PendingRegistration,
        PasswordResetRequest,
        RefreshToken,
        Notebook,
        NotebookMessage,
        NotebookDocument,
        NotebookDocumentChunk,
        NotebookReport,
        BillingCustomer,
        UsageEventLog,
        UsageAllowance,
        UsageWindowCounter,
        ProcessedWebhookEvent,
    ]

    # Use the default database from the connection string
    db = mongo_client.get_default_database()
    await init_beanie(database=db, document_models=document_models)

    logger = logging.getLogger("app.startup")
    logger.info("============================================================")
    logger.info("Application starting up with MongoDB")
    logger.info("  Chat Provider:      OPENROUTER")
    logger.info("  Chat Model:         %s", settings.chat_model)
    logger.info("============================================================")

    register_default_event_listeners()

    consumer_task: asyncio.Task[None] | None = None
    if settings.rabbitmq_consumer_enabled:
        consumer_task = asyncio.create_task(run_notebook_document_consumer(settings))

    usage_emission_task = asyncio.create_task(run_usage_emission_task(settings))

    await recover_pending_reports()

    try:
        yield
    finally:
        usage_emission_task.cancel()
        with suppress(asyncio.CancelledError):
            await usage_emission_task
        if consumer_task is not None:
            consumer_task.cancel()
            with suppress(asyncio.CancelledError):
                await consumer_task
        await mongo_client.close()


app = FastAPI(title="Aviary", docs_url=None, redoc_url=None, lifespan=lifespan)

API_V1_PREFIX = "/api/v1"


@app.exception_handler(AppError)
async def app_exception_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/docs", include_in_schema=False)
async def scalar_html() -> object:
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )


@app.get("/ping")
async def ping() -> dict[str, str]:
    return {"ping": "pong"}


app.include_router(auth_router, prefix=API_V1_PREFIX)
app.include_router(users_router, prefix=API_V1_PREFIX)
app.include_router(file_router, prefix=API_V1_PREFIX)
app.include_router(notebooks_router, prefix=API_V1_PREFIX)
app.include_router(billing_router, prefix=API_V1_PREFIX)
app.include_router(admin_router, prefix=API_V1_PREFIX)
