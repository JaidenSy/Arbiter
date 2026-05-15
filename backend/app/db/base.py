"""
Arbiter — SQLAlchemy async engine and session factory.

This module owns the single async engine and the session factory used
throughout the application.  All models must import ``Base`` from here
(not from individual model files) to ensure they are registered on the
same metadata object.

Usage:
    from app.db.base import Base, async_session_factory

    # In a dependency:
    async with async_session_factory() as session:
        result = await session.execute(...)
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """
    Shared declarative base for all SQLAlchemy ORM models.

    All model classes must inherit from this Base so their tables are
    registered on the same MetaData instance (required for Alembic and
    for ``Base.metadata.create_all``).
    """


# ── Engine ────────────────────────────────────────────────────────────────────

def build_engine() -> AsyncEngine:
    """
    Construct the async SQLAlchemy engine from settings.

    Pool parameters are intentionally conservative defaults; tune via env
    vars once load characteristics are known.

    Returns:
        AsyncEngine: ready to use, connected lazily on first query.
    """
    return create_async_engine(
        settings.database_url,
        echo=settings.app_debug,
        pool_size=10,
        max_overflow=20,
    )


engine: AsyncEngine = build_engine()  # type: ignore[assignment]

# ── Session factory ───────────────────────────────────────────────────────────

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,  # type: ignore[arg-type]
    expire_on_commit=False,
    class_=AsyncSession,
)
