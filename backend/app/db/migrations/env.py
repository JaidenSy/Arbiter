"""
Alembic migration environment for Arbiter.

Configured for async SQLAlchemy (asyncpg driver).  Uses the application's
own settings and Base.metadata so autogenerate discovers all model tables.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Import application Base and all models so autogenerate sees every table ───
from app.db.base import Base  # noqa: F401 — registers Base.metadata

# Import all models so their table definitions are attached to Base.metadata.
import app.db.models.agent  # noqa: F401
import app.db.models.cache  # noqa: F401
import app.db.models.mcp_server  # noqa: F401
import app.db.models.session  # noqa: F401
import app.db.models.task  # noqa: F401
import app.db.models.tool_permission  # noqa: F401
import app.db.models.tool_permission_event  # noqa: F401
import app.db.models.vault  # noqa: F401

# ── Alembic Config object ─────────────────────────────────────────────────────
config = context.config

# Interpret the config file for Python logging if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for --autogenerate support.
target_metadata = Base.metadata


def get_url() -> str:
    """
    Read the database URL from application settings.

    Converts the asyncpg URL to a standard postgresql:// URL for the
    offline mode (sync) runner.  Online mode re-adds asyncpg explicitly.
    """
    from app.core.config import settings
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


# ── Run migrations ─────────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """
    Run migrations without a live database connection.

    Emits SQL to stdout so it can be reviewed or piped to psql.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    """Configure context and run pending migrations on an open connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations within a sync wrapper."""
    # Use asyncpg URL for the async engine.
    async_url = get_url().replace("postgresql://", "postgresql+asyncpg://")
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = async_url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations against a live database using the async engine."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
