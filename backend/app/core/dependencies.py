# Copyright (c) 2026 Jaiden Sy. All rights reserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Arbiter — FastAPI dependency injection.

Each function here is a FastAPI Depends provider.  They are consumed by
endpoint functions via:

    async def my_endpoint(db: AsyncSession = Depends(get_db)):
        ...
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from typing import AsyncGenerator, Union

from fastapi import Depends, Header, HTTPException, Request, Security, status

_logger = logging.getLogger(__name__)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.db.base import async_session_factory
from app.db.models.agent import Agent
from app.db.models.user import User


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


# ── JWT / User auth ───────────────────────────────────────────────────────────

_oauth2_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_oauth2_bearer),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> User:
    """
    Validate a JWT Bearer token and return the authenticated User.

    Steps:
        1. Extract Bearer token from the Authorization header.
        2. Decode and validate signature / expiry via security.decode_access_token.
        3. Check jti against Redis blocklist (populated on logout).
        4. Load User from DB, verify is_active.

    Args:
        credentials: HTTP Bearer token.
        db:          Injected database session.
        redis:       Injected Redis client.

    Returns:
        User: The authenticated, active user row.

    Raises:
        HTTPException 401: On missing/invalid token, revoked jti, or inactive user.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = security.decode_access_token(credentials.credentials)

    jti: str = payload.get("jti", "")
    if jti:
        try:
            is_blocked = await redis.exists(f"jti_blocklist:{jti}")
        except Exception:
            _logger.warning("Redis unavailable for JWT blocklist check — failing open")
            is_blocked = False
        if is_blocked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

    user_id = uuid.UUID(payload["sub"])
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive or not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_principal(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> Union[User, Agent]:
    """
    Accept either a JWT (human user) or an API key (agent).

    Tries JWT first; falls back to API key if the token starts with ``nxai_``.
    Raises 401 if neither succeeds.

    Args:
        authorization: Raw Authorization header value (e.g. "Bearer <token>").
        db:            Injected database session.
        redis:         Injected Redis client.

    Returns:
        User | Agent: The resolved principal.

    Raises:
        HTTPException 401: On missing or unrecognised credential.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ").strip()

    if token.startswith("nxai_"):
        key_hash = security.hash_api_key(token)
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

    # Assume JWT
    payload = security.decode_access_token(token)
    jti: str = payload.get("jti", "")
    if jti and await redis.exists(f"jti_blocklist:{jti}"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = uuid.UUID(payload["sub"])
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive or not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# ── Email verification gate ───────────────────────────────────────────────────

_ORG_VERIFIED_TTL = 300  # 5 minutes


async def require_org_verified(
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> None:
    """
    Ensure that at least one user in the agent's org has a verified email.

    Caches the result in Redis for 5 minutes to avoid repeated DB queries on
    every proxied request.  Cache is invalidated when the user verifies their
    email (see the verify_email endpoint).

    Raises:
        HTTPException 403: When no verified user exists in the org.
    """
    cache_key = f"org_verified:{agent.org_id}"

    if redis is not None:
        cached = await redis.get(cache_key)
        if cached is not None:
            if cached == b"1" or cached == "1":
                return
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "email_not_verified",
                    "message": (
                        "Verify your email to use the proxy. "
                        "Check your inbox or resend from your account settings."
                    ),
                },
            )

    result = await db.execute(
        text(
            "SELECT EXISTS("
            "  SELECT 1 FROM users"
            "  WHERE org_id = :org_id AND is_verified = true"
            ")"
        ),
        {"org_id": str(agent.org_id)},
    )
    is_verified: bool = result.scalar_one()

    if redis is not None:
        await redis.setex(cache_key, _ORG_VERIFIED_TTL, "1" if is_verified else "0")

    if not is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "email_not_verified",
                "message": (
                    "Verify your email to use the proxy. "
                    "Check your inbox or resend from your account settings."
                ),
            },
        )


def require_role(*roles: str) -> Callable[..., User]:
    """
    Dependency factory that enforces RBAC role membership.

    Usage::

        @router.post("/agents", dependencies=[Depends(require_role("admin", "owner"))])

    Args:
        *roles: Accepted role strings (e.g. "owner", "admin").

    Returns:
        FastAPI dependency that returns the current User or raises 403.
    """

    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(roles)}",
            )
        return user

    return _check
