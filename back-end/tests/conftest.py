from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import PendingRegistration, RefreshToken, User
from main import app

_ = (PendingRegistration, RefreshToken, User)


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        database_url="sqlite://",
        jwt_secret_key="test-secret-test-secret-test-secret",
        resend_api_key="test-key",
        resend_from_email="auth@example.com",
    )


@pytest.fixture()
def client(session: Session, settings: Settings) -> Generator[TestClient, None, None]:
    def override_session() -> Generator[Session, None, None]:
        yield session

    def override_settings() -> Settings:
        return settings

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = override_settings
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
