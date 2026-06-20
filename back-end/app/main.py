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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference

from app.auth.models import PendingRegistration, RefreshToken
from app.auth.router import router as auth_router
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
from app.notebooks.service import run_report_generation
from app.users.models import User
from app.users.router import router as users_router

_recovered_tasks: set[asyncio.Task[None]] = set()


async def _recover_pending_reports() -> None:
    logger = logging.getLogger("app.startup")

    try:
        stuck_reports = await NotebookReport.find(
            {"status": {"$in": ["pending", "generating"]}}
        ).to_list()

        if not stuck_reports:
            return

        logger.info(
            "Recovering %d pending/generating report(s) after restart",
            len(stuck_reports),
        )

        for report in stuck_reports:
            if report.status == "generating":
                report.status = "pending"
                await report.save()

            notebook = await Notebook.find_one({"_id": report.notebook_id})
            user = await User.find_one({"_id": report.user_id})
            if notebook is None or user is None:
                logger.warning(
                    "Skipping report %s: notebook or user not found",
                    report.id,
                )
                report.status = "failed"
                report.error_message = (
                    "Recovery failed: associated notebook or user no longer exists."
                )
                await report.save()
                continue

            from app.notebooks.service import build_report_context

            context = await build_report_context(notebook, user)
            if not context:
                logger.warning(
                    "Skipping report %s: no indexed documents available for context",
                    report.id,
                )
                report.status = "failed"
                report.error_message = "Recovery failed: no indexed documents found."
                await report.save()
                continue

            task = asyncio.create_task(
                run_report_generation(
                    report_id=report.id,
                    report_type=report.report_type,
                    context=context,
                    instructions=report.additional_instructions,
                    detail_level=report.detail_level,
                )
            )
            _recovered_tasks.add(task)
            task.add_done_callback(_recovered_tasks.discard)
            logger.info("Re-queued report %s (type=%s)", report.id, report.report_type)
    except Exception:
        logger.exception("Failed to recover pending reports")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    mongo_client = await init_db()

    document_models = [
        User,
        PendingRegistration,
        RefreshToken,
        Notebook,
        NotebookMessage,
        NotebookDocument,
        NotebookDocumentChunk,
        NotebookReport,
    ]

    # Use the default database from the connection string
    db = mongo_client.get_default_database()
    await init_beanie(database=db, document_models=document_models)

    logger = logging.getLogger("app.startup")
    logger.info("============================================================")
    logger.info("Application starting up with MongoDB")
    logger.info("  Chat Provider:      %s", settings.chat_provider.strip().upper())
    logger.info("  Chat Model:         %s", settings.chat_model)
    logger.info("============================================================")

    consumer_task: asyncio.Task[None] | None = None
    if settings.rabbitmq_consumer_enabled:
        consumer_task = asyncio.create_task(run_notebook_document_consumer(settings))

    await _recover_pending_reports()

    try:
        yield
    finally:
        if consumer_task is not None:
            consumer_task.cancel()
            with suppress(asyncio.CancelledError):
                await consumer_task
        mongo_client.close()


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
