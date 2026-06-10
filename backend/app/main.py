# Copyright (c) 2026 Jaiden Sy. All rights reserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Arbiter Backend — Application entry point.

Initialises the FastAPI app, registers all API routers, configures CORS,
and manages application lifespan (database pool + Redis connection setup
and teardown).
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import uuid as _uuid_lib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select, text, update
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.endpoints import (
    agents,
    analytics,
    audit,
    auth,
    billing,
    cache,
    cli_auth,
    mcp,
    mcp_servers,
    onboarding,
    org,
    proxy,
    sessions,
    sso,
    stats,
    tool_permissions,
    traces,
    vault,
)
from app.core.config import settings
from app.core.request_utils import get_client_ip
from app.db.base import async_session_factory, engine
from app.db.models.cache import CacheEntry
from app.db.models.cli_device_code import CliDeviceCode
from app.db.models.refresh_token import RefreshToken
from app.db.models.session import Session, SessionEvent
from app.services.plan.plan_limits import (
    PlanLimitError,
    QuotaExceededError,
)
from app.services.plan.plan_limits import (
    SessionBudgetExceededError as _SessionBudgetExceededError,
)

_SBE = _SessionBudgetExceededError  # alias used in exception handler below
from app.services.quota.quota_alert_service import quota_alert_loop
from app.tasks.purge_gdpr import gdpr_purge_loop

logger = logging.getLogger(__name__)

# ── Request-ID context (OPS-03) ───────────────────────────────────────────────

_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class _RequestIDFilter(logging.Filter):
    """Inject request_id into every log record for structured log correlation."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get("")  # type: ignore[attr-defined]
        return True


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate a UUID per request; expose it on `X-Request-ID` response header."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        req_id = request.headers.get("X-Request-ID") or str(_uuid_lib.uuid4())
        _request_id_var.set(req_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


# ── Logging setup (OPS-02) ────────────────────────────────────────────────────


def _configure_logging(is_production: bool) -> None:
    """
    Set up structured JSON logging in production, plain text in development.

    Attaches _RequestIDFilter to every handler so request_id is included in
    every log record without requiring callers to pass it explicitly.
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Remove any handlers that uvicorn or Python may have already installed.
    root.handlers = []

    handler = logging.StreamHandler()
    handler.addFilter(_RequestIDFilter())

    if is_production:
        from pythonjsonlogger import jsonlogger  # type: ignore[import]

        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s %(request_id)s",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(request_id)s] %(name)s %(levelname)s %(message)s"
        )

    handler.setFormatter(formatter)
    root.addHandler(handler)


_EVICTION_INTERVAL = 3600  # run every hour
_SESSION_INACTIVITY_MINUTES = 30


async def _eviction_loop() -> None:
    """Background task: evict expired cache/tokens and close inactive sessions."""
    while True:
        await asyncio.sleep(_EVICTION_INTERVAL)
        try:
            async with async_session_factory() as db:
                now = datetime.now(tz=UTC)
                inactivity_cutoff = now - timedelta(minutes=_SESSION_INACTIVITY_MINUTES)

                cache_result = await db.execute(
                    delete(CacheEntry).where(CacheEntry.expires_at <= now)
                )
                token_result = await db.execute(
                    delete(RefreshToken).where(RefreshToken.expires_at <= now)
                )

                # Purge expired CLI device codes — consumed and rejected codes
                # older than their TTL have no further utility.
                await db.execute(delete(CliDeviceCode).where(CliDeviceCode.expires_at <= now))

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

                # Audit log retention — delete sessions (+ events via DB cascade)
                # older than AUDIT_LOG_RETENTION_DAYS. Skip if set to 0.
                retention_deleted = 0
                if settings.audit_log_retention_days > 0:
                    retention_cutoff = now - timedelta(days=settings.audit_log_retention_days)
                    retention_result = await db.execute(
                        delete(Session).where(Session.started_at < retention_cutoff)
                    )
                    retention_deleted = retention_result.rowcount

                await db.commit()
                logger.info(
                    "eviction: removed %d cache entries, %d tokens; "
                    "closed %d inactive sessions; deleted %d sessions past retention (%d days)",
                    cache_result.rowcount,
                    token_result.rowcount,
                    session_result.rowcount,
                    retention_deleted,
                    settings.audit_log_retention_days,
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

    # Warn if public registration is open in production.
    if settings.is_production and settings.allow_public_registration:
        logger.warning(
            "SECURITY: ALLOW_PUBLIC_REGISTRATION=true in production — "
            "set to false and provide INVITE_CODE to restrict sign-ups."
        )

    # Start background eviction task.
    eviction_task = asyncio.create_task(_eviction_loop())
    logger.info("arbiter: eviction task started (interval=%ds)", _EVICTION_INTERVAL)

    # Start GDPR 30-day hard-purge task (P2-FIX-8).
    gdpr_purge_task = asyncio.create_task(gdpr_purge_loop())
    logger.info("arbiter: GDPR purge task started (interval=86400s)")

    # Start hourly quota alert task.
    quota_alert_task = asyncio.create_task(quota_alert_loop())
    logger.info("arbiter: quota alert task started (interval=3600s)")

    # Start hourly MCP server health monitoring.
    from app.tasks.health_check import health_check_loop  # noqa: PLC0415

    health_task = asyncio.create_task(health_check_loop(redis=redis_client))
    logger.info("arbiter: MCP health check task started (interval=3600s)")

    yield

    # Shutdown: cancel background tasks cleanly.
    eviction_task.cancel()
    gdpr_purge_task.cancel()
    quota_alert_task.cancel()
    health_task.cancel()
    try:
        await eviction_task
    except asyncio.CancelledError:
        pass
    try:
        await gdpr_purge_task
    except asyncio.CancelledError:
        pass
    try:
        await health_task
    except asyncio.CancelledError:
        pass
    try:
        await quota_alert_task
    except asyncio.CancelledError:
        pass

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("arbiter: shutting down")
    await redis_client.aclose()
    await engine.dispose()
    logger.info("arbiter: shutdown complete")


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application instance."""
    _configure_logging(settings.is_production)

    app = FastAPI(
        title="Arbiter",
        description=(
            "Self-hosted MCP gateway with secret management, "
            "semantic caching, RBAC, and audit logging."
        ),
        version="0.1.0",
        # Disable Swagger/ReDoc/OpenAPI schema in production — a security
        # gateway with its full API surface publicly browsable is a trust killer.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan,
    )

    # ── Request-ID middleware (OPS-03) ────────────────────────────────────────
    # Must be innermost (added last) so it wraps every request before CORS.
    app.add_middleware(RequestIDMiddleware)

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
    async def plan_limit_error_handler(request: Request, exc: PlanLimitError) -> JSONResponse:
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

    @app.exception_handler(_SBE)
    async def session_budget_exceeded_handler(
        request: Request,
        exc: _SBE,  # type: ignore[valid-type]
    ) -> JSONResponse:
        """Return HTTP 402 when an agent's per-session tool-call budget is exhausted."""
        return JSONResponse(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            content={
                "error": "session_budget_exceeded",
                "session_id": exc.session_id,
                "used": exc.used,
                "limit": exc.limit,
            },
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(cli_auth.router, prefix=settings.api_prefix)
    app.include_router(sso.router, prefix=settings.api_prefix)
    app.include_router(agents.router, prefix=settings.api_prefix)
    app.include_router(mcp_servers.router, prefix=settings.api_prefix)
    app.include_router(sessions.router, prefix=settings.api_prefix)
    app.include_router(proxy.router, prefix=settings.api_prefix)
    app.include_router(vault.router, prefix=settings.api_prefix)
    app.include_router(tool_permissions.router, prefix=settings.api_prefix)
    app.include_router(stats.router, prefix=settings.api_prefix)
    app.include_router(analytics.router, prefix=settings.api_prefix)
    app.include_router(audit.router, prefix=settings.api_prefix)
    app.include_router(traces.router, prefix=settings.api_prefix)
    app.include_router(onboarding.router, prefix=settings.api_prefix)
    app.include_router(billing.router, prefix=settings.api_prefix)
    app.include_router(cache.router, prefix=settings.api_prefix)
    app.include_router(org.router, prefix=settings.api_prefix)
    app.include_router(org._accept_router, prefix=settings.api_prefix)
    app.include_router(webhooks.router, prefix=settings.api_prefix)
    # Native MCP endpoint — mounted at the app root (/mcp), not under /api/v1,
    # so MCP clients connect to the URL advertised on the landing page.
    app.include_router(mcp.router)

    # ── Health checks ─────────────────────────────────────────────────────────
    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        """Liveness probe — returns 200 when the process is up."""
        return {"status": "ok"}

    @app.get("/health/db", tags=["meta"])
    async def health_db(request: Request) -> dict[str, str]:
        """Readiness probe — verifies database connectivity.

        Rate-limited to 10 requests/minute per IP to prevent DB connection
        pool exhaustion from unauthenticated external hammering.
        """
        try:
            redis = request.app.state.redis
            if redis is not None:
                client_ip = get_client_ip(request)
                rl_key = f"rate_limit:health_db:{client_ip}"
                count = await redis.incr(rl_key)
                if count == 1:
                    await redis.expire(rl_key, 60)  # 1-minute window
                if count > 10:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Too many requests. Try again in 1 minute.",
                    )
        except HTTPException:
            raise
        except Exception:
            pass  # Redis unavailable — don't block the health check itself

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
        """Readiness probe — verifies Redis connectivity.

        Rate-limited to 10 requests/minute per IP to prevent Redis connection
        exhaustion from unauthenticated external hammering.
        """
        redis = request.app.state.redis
        try:
            if redis is not None:
                client_ip = get_client_ip(request)
                rl_key = f"rate_limit:health_cache:{client_ip}"
                count = await redis.incr(rl_key)
                if count == 1:
                    await redis.expire(rl_key, 60)  # 1-minute window
                if count > 10:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Too many requests. Try again in 1 minute.",
                    )
        except HTTPException:
            raise
        except Exception:
            pass  # rate-limit check failure should not block the probe

        try:
            await redis.ping()
            return {"status": "ok"}
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Redis unreachable: {exc}",
            )

    return app


app = create_app()
