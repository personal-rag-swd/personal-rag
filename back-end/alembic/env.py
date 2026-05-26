from __future__ import annotations

import importlib
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, MetaData
from sqlmodel import SQLModel

from app.core.config import get_database_url as get_config_database_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Centralized naming convention for constraints/indexes so Alembic
# autogenerate produces stable, descriptive names.
naming_convention = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Use a MetaData with the naming convention and ensure SQLModel registers
# tables against it so Alembic sees the convention during autogenerate.
metadata = MetaData(naming_convention=naming_convention)
SQLModel.metadata = metadata


def import_models() -> None:
    """Import SQLModel modules so table metadata is registered for autogenerate."""
    for module_name in (
        "app.auth.models",
        "app.users.models",
    ):
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name is None or not module_name.startswith(exc.name):
                raise


import_models()
target_metadata = SQLModel.metadata


def get_database_url() -> str:
    database_url = get_config_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set to run Alembic migrations.")
    return database_url


config.set_main_option("sqlalchemy.url", get_database_url())


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
