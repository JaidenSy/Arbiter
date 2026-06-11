# Copyright (c) 2026 Jaiden Sy. All rights reserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Arbiter — ProxyService.

The core gateway component.  Every tool call from an agent passes through
here before reaching an MCP server.

Request pipeline:
    1. Resolve MCPServer by server_name from DB.
    2. RBACService.check_permission()     — agent allowed to call this tool?
    3. CacheService.get_cached()          — serve from cache if available
    4. check_tool_call_quota()            — enforce monthly quota (skipped on cache hit)
    5. VaultService secret injection      — substitute secret placeholders
    6. HTTP forward to MCP server         — actual call via httpx
    7. CacheService.store_cached()        — cache the response
    8. SessionEvent persistence           — write audit record

Design decisions:
    - httpx.AsyncClient used for non-blocking HTTP forwarding.
    - Timeout is 30 s (matches typical LLM response times).
    - SSE streaming from upstream is forwarded via StreamingResponse when
      the upstream returns text/event-stream content-type.
    - Errors from the MCP server are captured in SessionEvent.error and
      re-raised as HTTPException so the agent receives a meaningful status code.
    - Secret placeholder pattern: ``{{SECRET_NAME}}`` in string param values.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ssrf import assert_ssrf_safe
from app.db.models.agent import Agent
from app.db.models.mcp_server import MCPServer
from app.db.models.organization import Organization
from app.db.models.session import Session, SessionEvent
from app.db.models.usage_event import UsageEvent
from app.schemas.proxy import ToolCallRequest, ToolCallResponse
from app.services.cache.cache_service import CacheService
from app.services.plan.plan_limits import (
    PLAN_LIMITS,
    QuotaExceededError,
    SessionBudgetExceededError,
)
from app.services.plan.plan_service import check_tool_call_quota
from app.services.rbac.rbac_service import RBACService
from app.services.vault.vault_service import VaultService
from app.services.webhook.webhook_service import dispatch_event as _dispatch_webhook

logger = logging.getLogger(__name__)

_SECRET_PLACEHOLDER = re.compile(r"\{\{(?:vault:)?([A-Za-z0-9_]+)\}\}")
_HTTP_TIMEOUT = httpx.Timeout(30.0)
_MAX_RETRIES = 2  # retries on TimeoutException/ConnectError; backoff 1s then 2s
_QuotaExceededError = QuotaExceededError  # keep import alive past linter
_SessionBudgetExceededError = SessionBudgetExceededError  # keep import alive past linter
_SESSION_BUDGET_TTL = 86_400  # 24 h — sessions don't outlive a day


def _extract_jsonrpc_from_sse(text: str) -> dict:
    """
    Return the last complete JSON-RPC message from an SSE response body.

    Upstream servers may emit keepalives or partial events before the final
    response — breaking on the first event silently drops data, so we keep
    the last frame that carries a ``result`` or ``error``.
    """
    json_body: dict = {}
    for line in text.splitlines():
        if line.startswith("data: "):
            try:
                candidate = json.loads(line[6:])
                if "result" in candidate or "error" in candidate:
                    json_body = candidate
            except json.JSONDecodeError:
                pass
    return json_body


class ProxyService:
    """
    Orchestrates the full lifecycle of a proxied MCP tool call.
    """

    def __init__(self, db: AsyncSession, redis: Any) -> None:
        """
        Initialise with injected dependencies.

        Args:
            db:    Async SQLAlchemy session.
            redis: Async Redis client.
        """
        self.db = db
        self.redis = redis
        self._rbac = RBACService(db, redis)
        self._vault = VaultService(db)
        self._cache = CacheService(db, redis)

    # ── Main entry point ──────────────────────────────────────────────────────

    async def forward_tool_call(
        self,
        request: ToolCallRequest,
        agent: Agent,
    ) -> ToolCallResponse:
        """
        Process and forward a tool call through the full pipeline.

        Steps:
            1. Resolve the target MCPServer by server_name from the DB.
            2. Check RBAC permission for (agent, server, tool).
            3. Check semantic cache — return early on hit (skips quota).
            4. Check monthly tool-call quota — raises 429 if exceeded.
            5. Inject vault secrets into request parameters.
            6. POST to ``{mcp_server.base_url}`` as JSON-RPC tools/call.
            7. Store response in cache.
            8. Persist SessionEvent audit record.

        Args:
            request: Validated ToolCallRequest from the endpoint.
            agent:   Authenticated agent making the call.

        Returns:
            ToolCallResponse: Structured response with payload and cache metadata.

        Raises:
            HTTPException 403: Agent lacks permission for this tool.
            HTTPException 404: Named MCP server not found or inactive.
            HTTPException 502: MCP server returned an error.
        """
        start_ms = time.monotonic()

        # ── 1. Resolve MCP server (org-scoped) ────────────────────────────────
        mcp_server = await self.resolve_server(request.server_name, agent.org_id)

        # ── 1b. Scope enforcement ──────────────────────────────────────────────
        if agent.scope == "vault_read_only":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Agent {agent.name!r} has scope 'vault_read_only' and cannot make tool calls",
            )

        # ── 2. RBAC check ──────────────────────────────────────────────────────
        permitted = await self._rbac.check_permission(
            agent=agent,
            mcp_server_id=mcp_server.id,
            tool_name=request.tool_name,
        )
        if not permitted:
            asyncio.create_task(
                _dispatch_webhook(
                    agent.org_id,
                    "permission.denied",
                    {"agent": agent.name, "tool": request.tool_name, "server": request.server_name},
                )
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Agent {agent.name!r} does not have permission to call "
                    f"tool {request.tool_name!r} on server {request.server_name!r}"
                ),
            )

        # ── 2b. Per-tool rate limiting ─────────────────────────────────────────
        rate_limit = await self._rbac.get_rate_limit(
            agent_id=agent.id,
            mcp_server_id=mcp_server.id,
            tool_name=request.tool_name,
        )
        if rate_limit is not None:
            minute_bucket = int(time.time() // 60)
            rl_key = f"rl:{agent.id}:{mcp_server.id}:{request.tool_name}:{minute_bucket}"
            count = await self.redis.incr(rl_key)
            if count == 1:
                await self.redis.expire(rl_key, 120)  # TTL 2 min to survive clock edges
            if count > rate_limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Rate limit exceeded: agent {agent.name!r} may call "
                        f"tool {request.tool_name!r} at most {rate_limit} times per minute"
                    ),
                )

        # ── 2c. Agent-level aggregate rate limiting ────────────────────────────
        if agent.rate_limit_per_minute is not None:
            minute_bucket = int(time.time() // 60)
            agent_rl_key = f"rl:agent:{agent.id}:{minute_bucket}"
            agent_count = await self.redis.incr(agent_rl_key)
            if agent_count == 1:
                await self.redis.expire(agent_rl_key, 120)
            if agent_count > agent.rate_limit_per_minute:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Agent rate limit exceeded: {agent.name!r} may make at most "
                        f"{agent.rate_limit_per_minute} tool calls per minute across all tools"
                    ),
                )

        # ── 3. Load org + determine plan features ─────────────────────────────
        org = await self.db.get(Organization, agent.org_id)
        semantic_cache = PLAN_LIMITS.get(org.plan_tier, {}).get("semantic_cache", False)

        # ── 3b. Cache lookup (org-scoped) ──────────────────────────────────────
        cached_result = None
        if mcp_server.cache_enabled:
            cached_result = await self._cache.get_cached(
                tool_name=request.tool_name,
                input_payload=request.params,
                org_id=agent.org_id,
                semantic=semantic_cache,
            )

        # Ensure/create session — propagate parent for multi-hop tracing.
        session = await self._ensure_session(
            agent=agent,
            session_id=request.session_id,
            parent_session_id=request.parent_session_id,
        )

        if cached_result is not None:
            duration_ms = int((time.monotonic() - start_ms) * 1000)
            event = await self._persist_event(
                session=session,
                mcp_server=mcp_server,
                tool_name=request.tool_name,
                request_payload=request.params,
                response_payload=cached_result,
                cache_hit=True,
                duration_ms=duration_ms,
                error=None,
            )
            return ToolCallResponse(
                session_id=session.id,
                event_id=event.id,
                tool_name=request.tool_name,
                result=cached_result,
                cache_hit=True,
                duration_ms=duration_ms,
            )

        # ── 4. Quota check (skipped for cache hits) ───────────────────────────
        try:
            await check_tool_call_quota(self.redis, self.db, org)
        except _QuotaExceededError:
            asyncio.create_task(
                _dispatch_webhook(
                    agent.org_id,
                    "quota.exceeded",
                    {"agent": agent.name, "plan": org.plan_tier},
                )
            )
            raise

        # ── 4b. Per-session budget check (skipped for cache hits) ─────────────
        if agent.max_calls_per_session is not None:
            budget_key = f"session_budget:{session.id}"
            used = await self.redis.incr(budget_key)
            if used == 1:
                await self.redis.expire(budget_key, _SESSION_BUDGET_TTL)
            if used > agent.max_calls_per_session:
                raise _SessionBudgetExceededError(
                    session_id=str(session.id),
                    used=used,
                    limit=agent.max_calls_per_session,
                )

        # ── 5. Secret injection ────────────────────────────────────────────────
        injected_params = await self.intercept_request(
            tool_name=request.tool_name,
            params=request.params,
            agent=agent,
        )

        # ── 6. Forward to MCP server ──────────────────────────────────────────
        jsonrpc_body = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {
                "name": request.tool_name,
                "arguments": injected_params,
            },
        }

        error: str | None = None
        response_payload: dict[str, Any] = {}

        # ── Resolve server-level auth headers from vault first ──────────────
        # Must happen before _ensure_mcp_session so the initialize handshake
        # also carries auth (e.g. GitHub MCP requires auth even for initialize).
        resolved_server_headers: dict[str, str] = {}
        if mcp_server.headers:
            for hdr_name, hdr_value in mcp_server.headers.items():
                # Use agent_id=None — server headers reference org-level vault secrets
                # (stored with agent_id=NULL via the dashboard), not agent-scoped ones.
                resolved_server_headers[hdr_name] = await self._inject_secrets(
                    hdr_value, agent_id=None, org_id=agent.org_id
                )

        # ── Build outbound headers (initialize upstream session if needed) ────
        # Include a fingerprint of server headers in the cache key so that
        # changing auth config (e.g. rotating a vault secret) invalidates
        # any previously cached unauthorized session IDs.
        import hashlib as _hl

        _headers_fp = _hl.md5(str(sorted(mcp_server.headers.items())).encode()).hexdigest()[:8]
        upstream_session_key = f"mcp_sessions:{session.id}:{request.server_name}:{_headers_fp}"

        # Re-validate DNS at request time to guard against DNS rebinding (#182):
        # a hostname that resolved to a public IP at registration may now point
        # to a private address.  This check runs before both the MCP initialize
        # handshake and the tool call so neither can be redirected internally.
        await assert_ssrf_safe(mcp_server.base_url, error_status=status.HTTP_502_BAD_GATEWAY)

        outbound_headers = await self._ensure_mcp_session(
            mcp_server=mcp_server,
            cache_key=upstream_session_key,
            extra_headers=resolved_server_headers,
        )

        try:
            # Retry on transient network errors only; never retry upstream 4xx/5xx.
            _last_exc: Exception | None = None
            http_resp = None
            for _attempt in range(_MAX_RETRIES + 1):
                try:
                    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                        http_resp = await client.post(
                            mcp_server.base_url,
                            json=jsonrpc_body,
                            headers=outbound_headers,
                        )
                    _last_exc = None
                    break
                except (httpx.TimeoutException, httpx.ConnectError) as exc:
                    _last_exc = exc
                    if _attempt < _MAX_RETRIES:
                        await asyncio.sleep(2**_attempt)  # 1s then 2s

            if _last_exc is not None:
                raise _last_exc

            assert http_resp is not None
            if http_resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(
                        f"MCP server {request.server_name!r} returned HTTP {http_resp.status_code}"
                    ),
                )

            # Persist upstream MCP session ID for subsequent requests.
            upstream_session_id = http_resp.headers.get("Mcp-Session-Id")
            if upstream_session_id:
                try:
                    await self.redis.set(upstream_session_key, upstream_session_id, ex=3600)
                except Exception as exc:
                    logger.warning("proxy: Redis session store failed: %s", exc)

            try:
                if "text/event-stream" in http_resp.headers.get("content-type", ""):
                    json_body = _extract_jsonrpc_from_sse(http_resp.text)
                else:
                    json_body = http_resp.json()
            except Exception:
                # Non-JSON response — wrap as text.
                json_body = {"content": [{"type": "text", "text": http_resp.text}]}

            # Extract result from JSON-RPC envelope.
            if "result" in json_body:
                response_payload = json_body["result"]
            elif "error" in json_body:
                # JSON-RPC application-level error.
                error = json.dumps(json_body["error"])
                response_payload = json_body["error"]
            else:
                response_payload = json_body

        except HTTPException as http_exc:
            error = http_exc.detail if isinstance(http_exc.detail, str) else str(http_exc.detail)
            duration_ms = int((time.monotonic() - start_ms) * 1000)
            await self._persist_event(
                session=session,
                mcp_server=mcp_server,
                tool_name=request.tool_name,
                request_payload=request.params,
                response_payload=None,
                cache_hit=False,
                duration_ms=duration_ms,
                error=error,
            )
            raise
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            error = (
                f"MCP server {request.server_name!r} unreachable after {_MAX_RETRIES + 1} attempts"
            )
            duration_ms = int((time.monotonic() - start_ms) * 1000)
            await self._persist_event(
                session=session,
                mcp_server=mcp_server,
                tool_name=request.tool_name,
                request_payload=request.params,
                response_payload=None,
                cache_hit=False,
                duration_ms=duration_ms,
                error=error,
            )
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=error) from exc
        except Exception as exc:
            error = str(exc)
            duration_ms = int((time.monotonic() - start_ms) * 1000)
            await self._persist_event(
                session=session,
                mcp_server=mcp_server,
                tool_name=request.tool_name,
                request_payload=request.params,
                response_payload=None,
                cache_hit=False,
                duration_ms=duration_ms,
                error=error,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"MCP server communication error: {exc}",
            ) from exc

        duration_ms = int((time.monotonic() - start_ms) * 1000)

        # ── 7. Store in cache (only on success and if server allows caching) ──
        if error is None and mcp_server.cache_enabled:
            try:
                cache_ttl = await self._rbac.get_cache_ttl(
                    agent_id=agent.id,
                    mcp_server_id=mcp_server.id,
                    tool_name=request.tool_name,
                )
                await self._cache.store_cached(
                    tool_name=request.tool_name,
                    input_payload=request.params,  # original params, not injected
                    response_payload=response_payload,
                    org_id=agent.org_id,
                    ttl_override=cache_ttl,
                    semantic=semantic_cache,
                )
            except Exception as exc:
                # Cache write failure must not prevent the response.
                logger.warning("proxy: cache store failed: %s", exc)

        # ── 8. Persist audit record ────────────────────────────────────────────
        event = await self._persist_event(
            session=session,
            mcp_server=mcp_server,
            tool_name=request.tool_name,
            request_payload=request.params,
            response_payload=response_payload if error is None else None,
            cache_hit=False,
            duration_ms=duration_ms,
            error=error,
        )

        return ToolCallResponse(
            session_id=session.id,
            event_id=event.id,
            tool_name=request.tool_name,
            result=response_payload,
            cache_hit=False,
            duration_ms=duration_ms,
        )

    # ── Secret injection ──────────────────────────────────────────────────────

    async def intercept_request(
        self,
        tool_name: str,
        params: dict[str, Any],
        agent: Agent,
    ) -> dict[str, Any]:
        """
        Pre-process a tool call request before forwarding.

        Substitutes ``{{SECRET_NAME}}`` placeholders in string param values
        with decrypted values from VaultService.  Non-string values are
        passed through unchanged.

        Args:
            tool_name: Name of the tool being invoked (for logging).
            params:    Raw parameters from the agent request.
            agent:     The calling agent (used for org-scoped and agent-scoped secret lookup).

        Returns:
            dict: Modified params with placeholders resolved.
        """
        result: dict[str, Any] = {}
        for key, value in params.items():
            if isinstance(value, str):
                result[key] = await self._inject_secrets(
                    value, agent_id=agent.id, org_id=agent.org_id
                )
            else:
                result[key] = value
        return result

    async def _inject_secrets(
        self, value: str, agent_id: uuid.UUID | None, org_id: uuid.UUID
    ) -> str:
        """Replace all {{SECRET_NAME}} and {{vault:SECRET_NAME}} placeholders in a string value."""
        matches = _SECRET_PLACEHOLDER.findall(value)
        if not matches:
            return value
        for secret_name in set(matches):
            try:
                secret_value = await self._vault.get_secret(
                    secret_name, org_id=org_id, agent_id=agent_id
                )
                # Replace both {{secret_name}} and {{vault:secret_name}} forms
                value = re.sub(
                    r"\{\{(?:vault:)?" + re.escape(secret_name) + r"\}\}",
                    secret_value,
                    value,
                )
            except KeyError:
                logger.warning(
                    "proxy: secret placeholder {{%s}} not found in vault for agent %s",
                    secret_name,
                    agent_id,
                )
        return value

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def resolve_server(self, server_name: str, org_id: uuid.UUID) -> MCPServer:
        """Fetch MCPServer by name scoped to the calling agent's org, or raise 404."""
        result = await self.db.execute(
            select(MCPServer).where(
                MCPServer.name == server_name,
                MCPServer.org_id == org_id,
                MCPServer.is_active.is_(True),
            )
        )
        server = result.scalar_one_or_none()
        if server is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"MCP server {server_name!r} not found or inactive",
            )
        return server

    async def resolve_server_headers(self, server: MCPServer) -> dict[str, str]:
        """Return server.headers with all {{vault:SECRET}} placeholders resolved."""
        if not server.headers:
            return {}
        resolved: dict[str, str] = {}
        for name, value in server.headers.items():
            resolved[name] = await self._inject_secrets(value, agent_id=None, org_id=server.org_id)
        return resolved

    async def fetch_tools_list(self, mcp_server: MCPServer) -> list[dict]:
        """
        Fetch the raw (unfiltered) tools/list from an upstream MCP server.

        Resolves vault-referenced auth headers, validates the URL against
        SSRF/DNS-rebinding at request time, posts a JSON-RPC tools/list, and
        parses either a plain JSON or SSE response.

        Returns:
            list[dict]: Raw tool dicts from the upstream server.

        Raises:
            HTTPException 502: upstream returned an error or was unreachable.
        """
        resolved_headers = await self.resolve_server_headers(mcp_server)
        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **resolved_headers,
        }

        jsonrpc_body = {
            "jsonrpc": "2.0",
            "id": "tools-list",
            "method": "tools/list",
            "params": {},
        }

        # Same DNS-rebinding guard as forward_tool_call — re-validate at
        # request time, not just at server registration.
        await assert_ssrf_safe(mcp_server.base_url, error_status=status.HTTP_502_BAD_GATEWAY)

        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                resp = await client.post(
                    mcp_server.base_url,
                    json=jsonrpc_body,
                    headers=request_headers,
                )
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(f"MCP server {mcp_server.name!r} returned HTTP {resp.status_code}"),
                )
            if "text/event-stream" in resp.headers.get("content-type", ""):
                json_body: dict = _extract_jsonrpc_from_sse(resp.text)
            else:
                json_body = resp.json()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"MCP server communication error: {exc}",
            ) from exc

        if "result" in json_body and "tools" in json_body["result"]:
            return json_body["result"]["tools"]
        if "error" in json_body:
            logger.warning(
                "proxy: tools/list on %r returned JSON-RPC error: %s",
                mcp_server.name,
                json_body["error"],
            )
        return []

    async def _ensure_mcp_session(
        self,
        mcp_server: MCPServer,
        cache_key: str,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """
        Return outbound headers for an upstream MCP server request.

        If a session ID is cached in Redis for this server, attach it.
        Otherwise, perform the MCP initialize handshake to obtain one,
        cache it, and attach it.  This handles the Streamable HTTP transport
        which requires an initialize before any tool calls.

        extra_headers are merged in before any request — including the
        initialize handshake — so auth headers reach the upstream server
        on every call, not just tool calls.
        """
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if extra_headers:
            headers.update(extra_headers)

        # Check cache first.
        try:
            stored_id = await self.redis.get(cache_key)
            if stored_id:
                if isinstance(stored_id, bytes):
                    stored_id = stored_id.decode()
                headers["Mcp-Session-Id"] = stored_id
                return headers
        except Exception as exc:
            logger.warning("proxy: Redis session lookup failed: %s", exc)

        # No cached session — do MCP initialize handshake (with auth headers).
        init_body = {
            "jsonrpc": "2.0",
            "id": "arbiter-init",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "arbiter-gateway", "version": "1.0"},
            },
        }
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                resp = await client.post(mcp_server.base_url, json=init_body, headers=headers)
            session_id = resp.headers.get("Mcp-Session-Id")
            if session_id:
                try:
                    await self.redis.set(cache_key, session_id, ex=3600)
                except Exception as exc:
                    logger.warning("proxy: Redis session store (init) failed: %s", exc)
                headers["Mcp-Session-Id"] = session_id
                logger.debug(
                    "proxy: initialized upstream MCP session %r for %s", session_id, mcp_server.name
                )
        except Exception as exc:
            logger.warning(
                "proxy: MCP initialize handshake failed for %s: %s", mcp_server.name, exc
            )

        return headers

    async def create_session(self, agent: Agent) -> Session:
        """
        Create a fresh audit session for an agent.

        Used by the native MCP endpoint's initialize handshake so the whole
        client connection maps to one session (returned as Mcp-Session-Id).
        """
        return await self._ensure_session(agent=agent, session_id=None)

    async def _ensure_session(
        self,
        agent: Agent,
        session_id: uuid.UUID | None,
        parent_session_id: uuid.UUID | None = None,
    ) -> Session:
        """
        Fetch an existing session or create a new one.

        If session_id is provided but does not belong to this agent, a new
        session is created (prevents session hijacking).

        When parent_session_id is provided the new session is linked into the
        parent's call chain: trace_id is inherited from the parent so the full
        multi-hop chain shares one trace_id.  If the parent belongs to a
        different org it is silently ignored (no cross-org linking).
        """
        if session_id is not None:
            result = await self.db.execute(
                select(Session).where(
                    Session.id == session_id,
                    Session.agent_id == agent.id,
                )
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                return existing

        # Resolve trace_id: inherit from parent if valid, else start a new chain.
        trace_id: uuid.UUID | None = None
        validated_parent_id: uuid.UUID | None = None
        if parent_session_id is not None:
            parent_result = await self.db.execute(
                select(Session).where(
                    Session.id == parent_session_id,
                    Session.org_id == agent.org_id,
                )
            )
            parent = parent_result.scalar_one_or_none()
            if parent is not None:
                trace_id = parent.trace_id
                validated_parent_id = parent.id

        new_id = uuid.uuid4()
        session = Session(
            id=new_id,
            agent_id=agent.id,
            org_id=agent.org_id,
            metadata_={},
            parent_session_id=validated_parent_id,
            trace_id=trace_id if trace_id is not None else new_id,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def _persist_event(
        self,
        session: Session,
        mcp_server: MCPServer,
        tool_name: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any] | None,
        cache_hit: bool,
        duration_ms: int,
        error: str | None,
        user_id: uuid.UUID | None = None,
    ) -> SessionEvent:
        """Append an immutable audit record and increment daily usage counters."""
        cost_usd: float | None = None
        if not cache_hit and mcp_server.cost_per_call_usd is not None:
            cost_usd = float(mcp_server.cost_per_call_usd)

        event = SessionEvent(
            session_id=session.id,
            org_id=session.org_id,
            mcp_server_id=mcp_server.id,
            user_id=user_id,
            tool_name=tool_name,
            request_payload=request_payload,
            response_payload=response_payload,
            cache_hit=cache_hit,
            duration_ms=duration_ms,
            error=error,
            cost_usd=cost_usd,
        )
        self.db.add(event)

        # Upsert daily usage counters — enforces quota on subsequent calls.
        today = datetime.now(tz=UTC).date()
        stmt = (
            pg_insert(UsageEvent)
            .values(
                org_id=session.org_id,
                event_date=today,
                tool_calls=1,
                cache_hits=1 if cache_hit else 0,
            )
            .on_conflict_do_update(
                constraint="uq_usage_events_org_date",
                set_={
                    "tool_calls": UsageEvent.tool_calls + 1,
                    "cache_hits": UsageEvent.cache_hits + (1 if cache_hit else 0),
                },
            )
        )
        await self.db.execute(stmt)

        await self.db.commit()
        await self.db.refresh(event)
        return event

    # ── tools/list filtering ──────────────────────────────────────────────────

    async def filter_tools_list(
        self,
        agent: Agent,
        server_name: str,
        tools: list[dict],
        mcp_server: MCPServer | None = None,
    ) -> list[dict]:
        """
        Filter a tools/list response to only RBAC-permitted tools.

        Args:
            agent:       Authenticated agent.
            server_name: Logical MCP server name.
            tools:       Raw tool list from upstream tools/list response.
            mcp_server:  Pre-resolved MCPServer to avoid a second DB round-trip.

        Returns:
            list[dict]: Filtered tool dicts visible to this agent.
        """
        if mcp_server is None:
            mcp_server = await self.resolve_server(server_name, agent.org_id)
        return await self._rbac.filter_tools_list(
            agent_id=agent.id,
            mcp_server_id=mcp_server.id,
            tools=tools,
        )
