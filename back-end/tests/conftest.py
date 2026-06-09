"""Shared pytest fixtures for the backend test suite.

The backend tests run against a real PostgreSQL + pgvector database provisioned
by Docker. Alembic migrations define the schema under test, and each test starts
from an empty set of tables instead of a SQLite metadata clone.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Generator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from alembic import command

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5433/personal_rag_test",
)

from app.core.config import Settings, get_database_url, get_settings
from app.core.database import get_session
from app.core.security import create_access_token
from app.main import app
from app.notebooks.models import NotebookDocument, NotebookDocumentChunk
from app.users.models import User

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _build_alembic_config(database_url: str) -> Config:
    alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    return alembic_config


def _reset_database_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
        connection.exec_driver_sql("CREATE SCHEMA public")
        connection.exec_driver_sql("GRANT ALL ON SCHEMA public TO CURRENT_USER")
        connection.exec_driver_sql("GRANT ALL ON SCHEMA public TO public")


def _truncate_public_tables(engine: Engine) -> None:
    with engine.begin() as connection:
        table_names = connection.execute(
            text(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename != 'alembic_version'
                ORDER BY tablename
                """
            )
        ).scalars()
        tables = [f'"{table_name}"' for table_name in table_names]
        if tables:
            connection.exec_driver_sql(
                f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"
            )


@pytest.fixture(scope="session")
def database_url() -> str:
    return get_database_url()


@pytest.fixture(scope="session")
def shared_test_engine(database_url: str) -> Generator[Engine]:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated_database(shared_test_engine: Engine) -> Generator[None]:
    get_settings.cache_clear()
    _reset_database_schema(shared_test_engine)
    command.upgrade(_build_alembic_config(get_database_url()), "head")
    return


@pytest.fixture(autouse=True)
def clean_database(migrated_database: None, shared_test_engine: Engine) -> None:
    _truncate_public_tables(shared_test_engine)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None]:
    """Keep dependency overrides isolated to a single test."""
    app.dependency_overrides = {}
    yield
    app.dependency_overrides = {}


@pytest.fixture
def settings(database_url: str) -> Settings:
    return Settings(
        database_url=database_url,
        jwt_secret_key="test-secret-with-at-least-32-bytes",
        jwt_algorithm="HS256",
    )


@pytest.fixture
def session(shared_test_engine: Engine, migrated_database: None) -> Generator[Session]:
    with Session(shared_test_engine) as session:
        yield session


@pytest.fixture
def client(settings: Settings, session: Session) -> Generator[TestClient]:
    def override_get_settings() -> Settings:
        return settings

    def override_get_session() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def user_factory() -> Callable[[str, str], User]:
    def _create_user(email: str, role: str = "user") -> User:
        return User(
            id=uuid4(),
            email=email,
            hashed_password="hashed-password",
            role=role,
        )

    return _create_user


@pytest.fixture
def auth_headers(settings: Settings) -> Callable[[User], dict[str, str]]:
    def _auth_headers(user: User) -> dict[str, str]:
        token = create_access_token(user, settings)
        return {"Authorization": f"Bearer {token}"}

    return _auth_headers


@pytest.fixture
def indexed_chunk_factory(
    session: Session,
) -> Callable[[str, object, object], NotebookDocumentChunk]:
    def _create_indexed_chunk(
        filename: str,
        notebook_id: object,
        user_id: object,
    ) -> NotebookDocumentChunk:
        document = NotebookDocument(
            notebook_id=notebook_id,
            user_id=user_id,
            s3_bucket="test-bucket",
            s3_key=f"users/{user_id}/{uuid4()}/{filename}",
            filename=filename,
            status="indexed",
        )
        session.add(document)
        session.commit()
        session.refresh(document)

        chunk = NotebookDocumentChunk(
            document_id=document.id,
            chunk_index=0,
            content="Indexed source content about the project.",
            embedding=[0.0] * 1536,
        )
        session.add(chunk)
        session.commit()
        session.refresh(chunk)
        return chunk

    return _create_indexed_chunk
