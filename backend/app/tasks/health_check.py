"""
Arbiter — Background task: MCP server health monitoring (#208).

Runs every HEALTH_CHECK_INTERVAL seconds (default 3600 = 1 hour).

For each active MCP server across all orgs it:
  1. Probes the server by performing an MCP tools/list call.
  2. Records a MCPServerHealthCheck row (is_healthy, latency_ms, error).
  3. Circuit breaker: if consecutive failures >= CIRCUIT_BREAKER_THRESHOLD,
     deactivates the server (is_active=False).  A circuit-open is logged
     and can be cleared by re-activating the server via PATCH /mcp-servers/{id}.
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx
from sqlalchemy import select, update

from app.db.base import async_session_factory
from app.db.models.mcp_server import MCPServer
from app.db.models.mcp_server_health_check import MCPServerHealthCheck
from app.services.vault.vault_service import VaultService
from app.services.webhook.webhook_service import dispatch_event as _dispatch_webhook

logger = logging.getLogger(__name__)

HEALTH_CHECK_INTERVAL = 3600  # seconds between full check runs
CIRCUIT_BREAKER_THRESHOLD = 5  # consecutive failures before deactivating

# Redis key pattern: health:circuit:{server_id}
_CIRCUIT_KEY = "health:circuit:{server_id}"
_MCP_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


async def _probe_server(
    base_url: str, headers: dict[str, str]
) -> tuple[bool, int | None, str | None]:
    """
    Fire MCP initialize + tools/list at base_url.

    Returns (is_healthy, latency_ms, error_message).
    """
    merged = {**_MCP_HEADERS, **headers}
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            init_resp = await client.post(
                base_url,
                json={
                    "jsonrpc": "2.0",
                    "id": "health-init",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "arbiter-healthcheck", "version": "1.0"},
                    },
                },
                headers=merged,
            )
            session_headers = dict(merged)
            if session_id := init_resp.headers.get("Mcp-Session-Id"):
                session_headers["Mcp-Session-Id"] = session_id
            await client.post(
                base_url,
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                headers=session_headers,
            )
        latency_ms = int((time.monotonic() - t0) * 1000)
        return True, latency_ms, None
    except Exception as exc:
        return False, None, str(exc)


async def run_health_checks(redis: object | None = None) -> None:
    """
    Check all active MCP servers, persist results, trip circuit breakers as needed.

    This is also callable directly for testing; pass a Redis client to get circuit
    breaker behaviour, or None to skip it.
    """
    async with async_session_factory() as db:
        result = await db.execute(select(MCPServer).where(MCPServer.is_active.is_(True)))
        servers = result.scalars().all()

    for server in servers:
        async with async_session_factory() as db:
            try:
                # Resolve vault secrets in server headers
                vault = VaultService(db)
                resolved_headers: dict[str, str] = {}
                if server.headers:
                    import re

                    _PH = re.compile(r"\{\{(?:vault:)?([A-Za-z0-9_]+)\}\}")
                    for hdr_name, hdr_value in server.headers.items():
                        for secret_name in set(_PH.findall(hdr_value)):
                            try:
                                secret_val = await vault.get_secret(
                                    secret_name, org_id=server.org_id, agent_id=None
                                )
                                hdr_value = hdr_value.replace(f"{{{{{secret_name}}}}}", secret_val)
                                hdr_value = hdr_value.replace(
                                    f"{{{{vault:{secret_name}}}}}", secret_val
                                )
                            except KeyError:
                                pass
                        resolved_headers[hdr_name] = hdr_value

                is_healthy, latency_ms, error = await _probe_server(
                    server.base_url, resolved_headers
                )

                # Persist health check record
                check = MCPServerHealthCheck(
                    server_id=server.id,
                    org_id=server.org_id,
                    is_healthy=is_healthy,
                    latency_ms=latency_ms,
                    error=error,
                )
                db.add(check)

                # Circuit breaker logic
                if redis is not None:
                    circuit_key = _CIRCUIT_KEY.format(server_id=str(server.id))
                    if is_healthy:
                        await redis.delete(circuit_key)  # type: ignore[union-attr]
                    else:
                        fail_count = await redis.incr(circuit_key)  # type: ignore[union-attr]
                        await redis.expire(
                            circuit_key, 86400 * 7
                        )  # 7 day TTL (safety valve)  # type: ignore[union-attr]
                        if fail_count >= CIRCUIT_BREAKER_THRESHOLD:
                            await db.execute(
                                update(MCPServer)
                                .where(MCPServer.id == server.id)
                                .values(is_active=False)
                            )
                            logger.warning(
                                "health: circuit breaker tripped for server %s (%s) — "
                                "%d consecutive failures, deactivating",
                                server.name,
                                server.id,
                                fail_count,
                            )
                            asyncio.create_task(
                                _dispatch_webhook(
                                    db,
                                    server.org_id,
                                    "mcp_server.offline",
                                    {"server": server.name, "failures": int(fail_count)},
                                )
                            )

                await db.commit()

                log_fn = logger.debug if is_healthy else logger.warning
                log_fn(
                    "health: server %s (%s) — healthy=%s latency=%sms",
                    server.name,
                    server.id,
                    is_healthy,
                    latency_ms,
                )

            except Exception as exc:
                logger.error("health: unexpected error checking server %s: %s", server.name, exc)
                await db.rollback()


async def health_check_loop(redis: object | None = None) -> None:
    """Run health checks on a recurring interval."""
    while True:
        try:
            await run_health_checks(redis=redis)
        except Exception as exc:
            logger.error("health: check loop error: %s", exc)
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)
