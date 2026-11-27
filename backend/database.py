"""
Async SQLAlchemy engine, session factory and the get_db() dependency.
Nothing else in the app creates engines or sessions.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings


# ---------------------------------------------------------------------------
# Declarative base for all ORM models
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """Base for the ORM models; kept here rather than in models/ to avoid an import cycle with alembic/env.py."""
    pass


# ---------------------------------------------------------------------------
# Async engine — one per application lifetime
# ---------------------------------------------------------------------------
async_engine = create_async_engine(
    settings.async_database_url,
    connect_args=settings.db_connect_args,
    echo=False,  # set True locally to log SQL statements
    pool_size=5,              # Core connection pool size
    max_overflow=10,          # Extra connections under peak load
    pool_pre_ping=True,       # Detect and discard stale connections before each use
)

# ---------------------------------------------------------------------------
# Session factory — produces AsyncSession instances
# ---------------------------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,   # Keep objects usable after commit without re-querying
)


# ---------------------------------------------------------------------------
# FastAPI dependency — yields session, commits or rolls back
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a session per request; commit on success, roll back on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
