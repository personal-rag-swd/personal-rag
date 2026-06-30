from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from urllib.parse import urlparse, urlunparse
from uuid import UUID, uuid4

import pytest_asyncio
from beanie import init_beanie
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from pwdlib import PasswordHash
from pymongo import AsyncMongoClient
from scalar_fastapi import get_scalar_api_reference

import app.auth.service as _auth_service
from app.auth.models import PasswordResetRequest, PendingRegistration, RefreshToken
from app.auth.router import router as auth_router
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError

# Disable email sending in tests
_auth_service.send_registration_otp = lambda *a, **kw: None
_auth_service.send_password_reset_otp = lambda *a, **kw: None
from app.core.security import create_access_token
from app.event_listeners import register_default_event_listeners
from app.file.router import router as file_router
from app.notebooks.models import (
    Notebook,
    NotebookDocument,
    NotebookDocumentChunk,
    NotebookMessage,
    NotebookReport,
)
from app.notebooks.router import router as notebooks_router
from app.users.models import User
from app.users.router import router as users_router

password_hash = PasswordHash.recommended()

DOCUMENT_MODELS = [
    User,
    PendingRegistration,
    PasswordResetRequest,
    RefreshToken,
    Notebook,
    NotebookDocument,
    NotebookDocumentChunk,
    NotebookReport,
    NotebookMessage,
]


@pytest_asyncio.fixture(autouse=True)
async def _clean_db(app: FastAPI) -> None:
    for model in DOCUMENT_MODELS:
        await model.get_pymongo_collection().delete_many({})


def make_test_app() -> FastAPI:
    app = FastAPI(title="Aviary-Test", docs_url=None, redoc_url=None)

    @app.exception_handler(AppError)
    async def app_exception_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
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

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(file_router, prefix="/api/v1")
    app.include_router(notebooks_router, prefix="/api/v1")

    return app


@pytest_asyncio.fixture(name="settings")
async def fixture_settings() -> Settings:
    raw_url = os.environ.get(
        "DATABASE_URL",
        "mongodb://localhost:27017/personal-rag",
    )
    parsed = urlparse(raw_url)
    test_url = urlunparse(parsed._replace(path="/personal-rag-test"))

    return Settings(
        database_url=test_url,
        jwt_secret_key="test-secret-key",
        jwt_algorithm="HS256",
        access_token_expire_minutes=30,
        refresh_token_expire_days=30,
        otp_expire_minutes=10,
        otp_max_attempts=5,
        log_level="DEBUG",
        resend_api_key="",
        cookie_secure=False,
        notebook_chunk_size=100,
        notebook_chunk_overlap=20,
        embedding_dimension=1536,
        embedding_model="text-embedding-3-small",
        s3_bucket=os.environ.get("S3_BUCKET", "personal-rag-test"),
        s3_region="us-east-1",
        s3_endpoint_url=os.environ.get("S3_ENDPOINT_URL", "http://localhost:9000"),
        s3_public_endpoint_url=os.environ.get(
            "S3_PUBLIC_ENDPOINT_URL",
            os.environ.get("S3_ENDPOINT_URL", "http://localhost:9000"),
        ),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin"),
    )


@pytest_asyncio.fixture(name="app")
async def fixture_app(settings: Settings) -> AsyncGenerator[FastAPI]:
    client = AsyncMongoClient(
        settings.database_url,
        serverSelectionTimeoutMS=5000,
    )
    db = client.get_default_database()
    await init_beanie(database=db, document_models=DOCUMENT_MODELS)
    register_default_event_listeners()
    app = make_test_app()
    app.dependency_overrides[get_settings] = lambda: settings
    yield app
    await client.close()


@pytest_asyncio.fixture(name="client")
async def fixture_client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


def make_user(
    email: str | None = None,
    role: str | None = None,
) -> User:
    if email is None:
        email = f"{uuid4()}@example.com"
    return User(
        email=email,
        hashed_password=password_hash.hash("password123"),
        role=role or "user",
        is_active=True,
    )


async def create_user(
    email: str | None = None,
    role: str | None = None,
) -> User:
    user = make_user(email=email, role=role)
    await user.insert()
    return user


def auth_headers(user: User, settings: Settings) -> dict[str, str]:
    token = create_access_token(user, settings)
    return {"Authorization": f"Bearer {token}"}


async def create_notebook(
    user: User,
    name: str | None = None,
) -> Notebook:
    notebook = Notebook(
        user_id=user.id,
        name=name or "Test Notebook",
        description="A test notebook",
    )
    await notebook.insert()
    return notebook


async def create_indexed_chunk(
    notebook_id: UUID,
    user_id: UUID,
    content: str = "Test chunk content for retrieval",
    filename: str = "test.txt",
) -> tuple[NotebookDocument, NotebookDocumentChunk]:
    document = NotebookDocument(
        notebook_id=notebook_id,
        user_id=user_id,
        filename=filename,
        content_type="text/plain",
        size=len(content),
        status="indexed",
        content=content,
    )
    await document.insert()

    chunk = NotebookDocumentChunk(
        document_id=document.id,
        notebook_id=notebook_id,
        user_id=user_id,
        chunk_index=0,
        content=content,
        chunk_metadata={"source": filename},
        embedding=[],
    )
    await chunk.insert()
    return document, chunk
