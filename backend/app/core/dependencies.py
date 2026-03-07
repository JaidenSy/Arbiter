"""
NexusAI — FastAPI dependency injection stubs.

Each function here is a FastAPI Depends provider.  They are consumed by
endpoint functions via:

    async def my_endpoint(db: AsyncSession = Depends(get_db)):
        ...

Implementations fill in the connection/auth logic; the signatures here
define the expected return types so endpoints can be written and type-
checked before the implementations land.
"""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.db.base import async_session_factory
from app.db.models.agent import Agent


# ── Database ─────────────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async SQLAlchemy session for a single request.

    Opens a session from the async engine pool, yields it to the endpoint,
    then commits (or rolls back on exception) and closes it.

    Yields:
        AsyncSession: bound to the request lifetime.
    """
    async with async_session_factory() as session:
        yield session


# ── Redis ─────────────────────────────────────────────────────────────────────

async def get_redis(request: Request):  # type: ignore[return]
    """
    Return an async Redis client.

    The client is initialised once at app startup (lifespan) and stored on
    app.state.redis.  This dependency retrieves it for the current request.

    Returns:
        redis.asyncio.Redis: connected Redis client.
    """
    return request.app.state.redis


# ── Authentication ────────────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_agent(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    """
    Validate the Bearer API key and return the authenticated Agent.

    Extracts the Bearer token from the Authorization header, hashes it,
    and looks it up in the agents table.  Raises 401 if missing or invalid.

    Args:
        credentials: HTTP Bearer token from the Authorization header.
        db: injected database session.

    Returns:
        Agent: the authenticated agent row.

    Raises:
        HTTPException 401: when token is missing or does not match any agent.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_key = credentials.credentials
    key_hash = security.hash_api_key(raw_key)

    result = await db.execute(
        select(Agent).where(
            Agent.api_key_hash == key_hash,
            Agent.is_active.is_(True),
        )
    )
    agent = result.scalar_one_or_none()

    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return agent
