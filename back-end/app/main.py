import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.core.telemetry import setup_telemetry

# Configure logging and telemetry early
settings = get_settings()
setup_telemetry(settings)

# Standard logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(name)s - %(message)s",
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference

from app.auth.router import router as auth_router
from app.file.router import router as file_router
from app.notebooks.router import router as notebooks_router
from app.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    
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
    yield


app = FastAPI(title="Personal RAG", docs_url=None, redoc_url=None, lifespan=lifespan)

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
