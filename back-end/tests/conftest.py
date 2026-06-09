"""Shared pytest fixtures for the test suite.

Tests use an in-memory SQLite engine purely as a lightweight stand-in for
schema validation and ORM behaviour.  All production paths run against
PostgreSQL + pgvector; tests that exercise SQL emitted to the database (e.g.
the pgvector <=> operator) use monkeypatching instead of a real DB connection.
"""

from __future__ import annotations

import os
from collections.abc import Generator

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import Settings

# Shared in-memory engine with all tables created, used by tests that
# need to patch the router's engine for background-task execution.
_shared_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(_shared_test_engine)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        jwt_secret_key="test-secret-with-at-least-32-bytes",
        jwt_algorithm="HS256",
    )


@pytest.fixture
def session() -> Generator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def shared_test_engine():
    """Provide the shared test engine for patching router.background-task engines."""
    return _shared_test_engine
