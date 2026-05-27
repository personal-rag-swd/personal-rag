import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference

from app.auth.router import router as auth_router
from app.core.config import get_settings
from app.file.router import router as file_router
from app.notebooks.router import router as notebooks_router
from app.users.router import router as users_router

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(name)s - %(message)s",
)

app = FastAPI(title="Personal RAG", docs_url=None, redoc_url=None)
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
