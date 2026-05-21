"""
Arbiter Backend — Application entry point.

Initialises the FastAPI app, registers all API routers, configures CORS,
and manages application lifespan (database pool + Redis connection setup
and teardown).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from sqlalchemy import delete, select, text, update

from app.api.v1.endpoints import (
    agents,
    auth,
    billing,
    cache,
    mcp_servers,
    onboarding,
    org,
    proxy,
    sessions,
    sso,
    stats,
    tool_permissions,
    vault,
)
from app.core.config import settings
from app.db.base import async_session_factory, engine
from app.db.models.cache import CacheEntry
from app.db.models.refresh_token import RefreshToken
from app.db.models.session import Session, SessionEvent
from app.services.plan.plan_limits import PlanLimitError, QuotaExceededError

logger = logging.getLogger(__name__)

_EVICTION_INTERVAL = 3600  # run every hour
_SESSION_INACTIVITY_MINUTES = 30


async def _eviction_loop() -> None:
    """Background task: evict expired cache/tokens and close inactive sessions."""
    while True:
        await asyncio.sleep(_EVICTION_INTERVAL)
        try:
            async with async_session_factory() as db:
                now = datetime.now(tz=timezone.utc)
                inactivity_cutoff = now - timedelta(minutes=_SESSION_INACTIVITY_MINUTES)

                cache_result = await db.execute(
                    delete(CacheEntry).where(CacheEntry.expires_at <= now)
                )
                token_result = await db.execute(
                    delete(RefreshToken).where(RefreshToken.expires_at <= now)
                )

                # Close sessions with no events in the last 30 minutes.
                recent_session_ids = select(SessionEvent.session_id).where(
                    SessionEvent.occurred_at > inactivity_cutoff
                )
                session_result = await db.execute(
                    update(Session)
                    .where(
                        Session.ended_at.is_(None),
                        Session.started_at < inactivity_cutoff,
                        Session.id.not_in(recent_session_ids),
                    )
                    .values(ended_at=now)
                )

                await db.commit()
                logger.info(
                    "eviction: removed %d cache entries, %d tokens; closed %d inactive sessions",
                    cache_result.rowcount,
                    token_result.rowcount,
                    session_result.rowcount,
                )
        except Exception as exc:
            logger.warning("eviction: sweep failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage startup and shutdown of shared resources.

    Startup:
        - Connect to Redis and store client on app.state.redis
        - Warm up sentence-transformers embedding model (best-effort)

    Shutdown:
        - Close Redis connection pool
        - Dispose SQLAlchemy async engine connection pool
    """
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("arbiter: starting up")

    # Redis
    redis_client = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=False,  # keep bytes so JSON payloads survive round-trip
    )
    app.state.redis = redis_client
    try:
        await redis_client.ping()
        logger.info("arbiter: Redis connected at %s", settings.redis_url)
    except Exception as exc:
        logger.warning("arbiter: Redis ping failed at startup: %s", exc)

    # Warm up embedding model (best-effort; does not block startup on failure).
    try:
        from app.services.cache.cache_service import _get_model

        _get_model()
        logger.info("arbiter: embedding model loaded")
    except Exception as exc:
        logger.warning(
            "arbiter: embedding model could not be pre-loaded: %s — "
            "it will be loaded on first semantic cache call",
            exc,
        )

    # Warn if public registration is open in production.
    if settings.is_production and settings.allow_public_registration:
        logger.warning(
            "SECURITY: ALLOW_PUBLIC_REGISTRATION=true in production — "
            "set to false and provide INVITE_CODE to restrict sign-ups."
        )

    # Start background eviction task.
    eviction_task = asyncio.create_task(_eviction_loop())
    logger.info("arbiter: eviction task started (interval=%ds)", _EVICTION_INTERVAL)

    yield

    # Shutdown: cancel the eviction task cleanly.
    eviction_task.cancel()
    try:
        await eviction_task
    except asyncio.CancelledError:
        pass

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("arbiter: shutting down")
    await redis_client.aclose()
    await engine.dispose()
    logger.info("arbiter: shutdown complete")


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application instance."""
    app = FastAPI(
        title="Arbiter",
        description=(
            "Self-hosted MCP gateway with secret management, "
            "semantic caching, RBAC, and audit logging."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── Session middleware (required by Authlib for OAuth2 state) ─────────────
    # Must be added before CORS so it wraps the full request lifecycle.
    app.add_middleware(SessionMiddleware, secret_key=settings.app_secret_key)

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ────────────────────────────────────────────────────

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """
        Consolidate all HTTPException status codes into one handler.

        Dispatches custom response bodies for 401 (adds WWW-Authenticate header)
        and 403.  All other status codes echo the exception detail verbatim.
        """
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Unauthorized — valid Bearer API key required"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": exc.detail},
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Return a consistent validation error shape."""
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "Request validation failed", "errors": str(exc)},
        )

    @app.exception_handler(PlanLimitError)
    async def plan_limit_error_handler(
        request: Request, exc: PlanLimitError
    ) -> JSONResponse:
        """
        Return HTTP 402 when an org's count-based plan limit is reached.

        Response body matches the canonical shape from architect-output.md:
            { error, resource, current, limit, plan, upgrade_url }
        """
        return JSONResponse(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            content={
                "error": "plan_limit_reached",
                "resource": exc.resource,
                "current": exc.current,
                "limit": exc.limit,
                "plan": exc.plan,
                "upgrade_url": "https://arbiterai.dev/pricing",
            },
        )

    @app.exception_handler(QuotaExceededError)
    async def quota_exceeded_error_handler(
        request: Request, exc: QuotaExceededError
    ) -> JSONResponse:
        """
        Return HTTP 429 when an org's monthly tool-call quota is exhausted.

        Response body matches the canonical shape from architect-output.md:
            { error, resource, used, limit, resets_at, upgrade_url }
        """
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "quota_exceeded",
                "resource": exc.resource,
                "used": exc.used,
                "limit": exc.limit,
                "resets_at": exc.resets_at.isoformat(),
                "upgrade_url": "https://arbiterai.dev/pricing",
            },
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(sso.router, prefix=settings.api_prefix)
    app.include_router(agents.router, prefix=settings.api_prefix)
    app.include_router(mcp_servers.router, prefix=settings.api_prefix)
    app.include_router(sessions.router, prefix=settings.api_prefix)
    app.include_router(proxy.router, prefix=settings.api_prefix)
    app.include_router(vault.router, prefix=settings.api_prefix)
    app.include_router(tool_permissions.router, prefix=settings.api_prefix)
    app.include_router(stats.router, prefix=settings.api_prefix)
    app.include_router(onboarding.router, prefix=settings.api_prefix)
    app.include_router(billing.router, prefix=settings.api_prefix)
    app.include_router(cache.router, prefix=settings.api_prefix)
    app.include_router(org.router, prefix=settings.api_prefix)
    app.include_router(org._accept_router, prefix=settings.api_prefix)

    # ── Health checks ─────────────────────────────────────────────────────────
    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        """Liveness probe — returns 200 when the process is up."""
        return {"status": "ok"}

    @app.get("/health/db", tags=["meta"])
    async def health_db() -> dict[str, str]:
        """Readiness probe — verifies database connectivity."""
        try:
            async with async_session_factory() as session:
                await session.execute(text("SELECT 1"))
            return {"status": "ok"}
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Database unreachable: {exc}",
            )

    @app.get("/health/cache", tags=["meta"])
    async def health_cache(request: Request) -> dict[str, str]:
        """Readiness probe — verifies Redis connectivity."""
        try:
            redis = request.app.state.redis
            await redis.ping()
            return {"status": "ok"}
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Redis unreachable: {exc}",
            )

    return app


app = create_app()
