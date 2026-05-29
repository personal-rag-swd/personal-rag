from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.core.config import get_database_url
from app.core.telemetry import setup_db_logging

engine = create_engine(get_database_url(), pool_pre_ping=True)
setup_db_logging(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
