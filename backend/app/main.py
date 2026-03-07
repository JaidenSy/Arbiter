"""
NexusAI Backend — Application entry point.

Initialises the FastAPI app, registers all API routers, configures CORS,
and manages application lifespan (database pool + Redis connection setup
and teardown).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints import agents, mcp_servers, proxy, sessions, vault
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage startup and shutdown of shared resources.

    Startup:
        - Verify database connectivity
        - Verify Redis connectivity
        - Load embedding model for semantic cache

    Shutdown:
        - Close database connection pool
        - Close Redis connection
    """
    # TODO: initialise async DB engine (see app.db.base)
    # TODO: initialise Redis client (see app.core.dependencies)
    # TODO: warm up sentence-transformers embedding model

    yield

    # TODO: dispose DB engine
    # TODO: close Redis client


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application instance."""
    app = FastAPI(
        title="NexusAI",
        description="Self-hosted MCP gateway with secret management, semantic caching, RBAC, and audit logging.",
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
