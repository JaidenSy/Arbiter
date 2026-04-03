"""
NexusAI Backend — Application entry point.

Initialises the FastAPI app, registers all API routers, configures CORS,
and manages application lifespan (database pool + Redis connection setup
and teardown).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.endpoints import (
    agents,
    auth,
    mcp_servers,
    onboarding,
    proxy,
    sessions,
    stats,
    tool_permissions,
    vault,
)
from app.core.config import settings
from app.db.base import engine
from app.services.plan.plan_limits import PlanLimitError, QuotaExceededError

logger = logging.getLogger(__name__)


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
    logger.info("nexusai: starting up")

    # Redis
    redis_client = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=False,  # keep bytes so JSON payloads survive round-trip
    )
    app.state.redis = redis_client
    try:
        await redis_client.ping()
        logger.info("nexusai: Redis connected at %s", settings.redis_url)
    except Exception as exc:
        logger.warning("nexusai: Redis ping failed at startup: %s", exc)

    # Warm up embedding model (best-effort; does not block startup on failure).
    try:
        from app.services.cache.cache_service import _get_model

        _get_model()
        logger.info("nexusai: embedding model loaded")
    except Exception as exc:
        logger.warning(
            "nexusai: embedding model could not be pre-loaded: %s — "
            "it will be loaded on first semantic cache call",
            exc,
        )

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("nexusai: shutting down")
    await redis_client.aclose()
    await engine.dispose()
    logger.info("nexusai: shutdown complete")


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application instance."""
    app = FastAPI(
        title="NexusAI",
        description=(
            "Self-hosted MCP gateway with secret management, "
            "semantic caching, RBAC, and audit logging."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

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
                "upgrade_url": "https://nexusai.dev/pricing",
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
                "upgrade_url": "https://nexusai.dev/pricing",
            },
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(agents.router, prefix=settings.api_prefix)
    app.include_router(mcp_servers.router, prefix=settings.api_prefix)
    app.include_router(sessions.router, prefix=settings.api_prefix)
    app.include_router(proxy.router, prefix=settings.api_prefix)
    app.include_router(vault.router, prefix=settings.api_prefix)
    app.include_router(tool_permissions.router, prefix=settings.api_prefix)
    app.include_router(stats.router, prefix=settings.api_prefix)
    app.include_router(onboarding.router, prefix=settings.api_prefix)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        """Liveness probe — returns 200 when the process is up."""
        return {"status": "ok"}

    return app


app = create_app()
