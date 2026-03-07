"""
NexusAI Backend — Application entry point.

Initialises the FastAPI app, registers all API routers, configures CORS,
and manages application lifespan (database pool + Redis connection setup
and teardown).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.endpoints import agents, mcp_servers, proxy, sessions, vault
from app.core.config import settings
from app.db.base import engine

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

    @app.exception_handler(401)
    async def unauthorized_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Unauthorized — valid Bearer API key required"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(403)
    async def forbidden_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": str(exc)},
        )

    @app.exception_handler(422)
    async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "Request validation failed", "errors": str(exc)},
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(agents.router, prefix=settings.api_prefix)
    app.include_router(mcp_servers.router, prefix=settings.api_prefix)
    app.include_router(sessions.router, prefix=settings.api_prefix)
    app.include_router(proxy.router, prefix=settings.api_prefix)
    app.include_router(vault.router, prefix=settings.api_prefix)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        """Liveness probe — returns 200 when the process is up."""
        return {"status": "ok"}

    return app


app = create_app()
