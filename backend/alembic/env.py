"""
Alembic environment for the async engine. Unlike the generated default, it
imports all ORM models for autogenerate and takes the database URL from
backend.config.settings.
"""
import asyncio
import os
import sys
from logging.config import fileConfig

# ---------------------------------------------------------------------------
# Alembic runs from backend/, so put the repository root on sys.path for
# `from backend.xxx import ...` to resolve.
# ---------------------------------------------------------------------------
_here = os.path.dirname(os.path.abspath(__file__))           # .../backend/alembic/
_backend_dir = os.path.dirname(_here)                         # .../backend/
_project_root = os.path.dirname(_backend_dir)                 # repository root
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from backend.database import Base

# Imported for its side effect of registering the tables on Base.metadata.
import backend.models  # noqa: F401

from backend.config import settings

config = context.config

# The URL is read from settings in run_migrations_* below rather than set with
# set_main_option, because configparser chokes on "%" in passwords.

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate support
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline migrations (generates SQL without connecting)
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — outputs SQL without a live connection."""
    url = settings.async_database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migrations (connects to database and applies changes)
# ---------------------------------------------------------------------------
def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects and applies to live database."""
    connectable = create_async_engine(
        settings.async_database_url,
        connect_args=settings.db_connect_args,
        poolclass=pool.NullPool,  # NullPool for migrations — no persistent connections
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
