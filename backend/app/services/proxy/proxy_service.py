"""
NexusAI — ProxyService.

The core gateway component.  Every tool call from an agent passes through
here before reaching an MCP server.

Request pipeline:
    1. Resolve MCPServer by server_name from DB.
    2. RBACService.check_permission()     — agent allowed to call this tool?
    3. CacheService.get_cached()          — serve from cache if available
    4. VaultService secret injection      — substitute secret placeholders
    5. HTTP forward to MCP server         — actual call via httpx
    6. CacheService.store_cached()        — cache the response
    7. SessionEvent persistence           — write audit record

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

import json
import logging
import re
import time
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.models.mcp_server import MCPServer
from app.db.models.session import Session, SessionEvent
from app.schemas.proxy import ToolCallRequest, ToolCallResponse
from app.services.cache.cache_service import CacheService
from app.services.rbac.rbac_service import RBACService
from app.services.vault.vault_service import VaultService

logger = logging.getLogger(__name__)

_SECRET_PLACEHOLDER = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")
_HTTP_TIMEOUT = httpx.Timeout(30.0)


@dataclass
class PreparedCall:
    """
    Output of ``ProxyService.prepare_tool_call``.

    Contains everything needed to make the upstream HTTP call and finalise
    the audit record, without any HTTP I/O having occurred yet.
    """

    mcp_server: MCPServer
    session: Session
    jsonrpc_body: dict[str, Any]
    outbound_headers: dict[str, str]
    upstream_session_key: str
    raw_params: dict[str, Any]       # original (pre-injection) params for audit
    start_ms: float = field(default_factory=time.monotonic)


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
        self._rbac = RBACService(db)
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
            3. Check semantic cache — return early on hit.
            4. Inject vault secrets into request parameters.
            5. POST to ``{mcp_server.base_url}`` as JSON-RPC tools/call.
            6. Store response in cache.
            7. Persist SessionEvent audit record.

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

        # ── 1. Resolve MCP server ──────────────────────────────────────────────
        mcp_server = await self.resolve_server(request.server_name)

        # ── 2. RBAC check ──────────────────────────────────────────────────────
        permitted = await self._rbac.check_permission(
            agent=agent,
            mcp_server_id=mcp_server.id,
            tool_name=request.tool_name,
        )
        if not permitted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Agent {agent.name!r} does not have permission to call "
                    f"tool {request.tool_name!r} on server {request.server_name!r}"
                ),
            )

        # ── 3. Cache lookup ────────────────────────────────────────────────────
        cached_result = None
        if mcp_server.cache_enabled:
            cached_result = await self._cache.get_cached(
                tool_name=request.tool_name,
                input_payload=request.params,
            )

        # Ensure/create session.
        session = await self._ensure_session(
            agent=agent,
            session_id=request.session_id,
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

        # ── 4. Secret injection ────────────────────────────────────────────────
        injected_params = await self.intercept_request(
            tool_name=request.tool_name,
            params=request.params,
            agent=agent,
        )

        # ── 5. Forward to MCP server ──────────────────────────────────────────
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

        # ── Build outbound headers (initialize upstream session if needed) ────
        upstream_session_key = f"mcp_sessions:{session.id}:{request.server_name}"
        outbound_headers = await self._ensure_mcp_session(
            mcp_server=mcp_server,
            cache_key=upstream_session_key,
        )

        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                http_resp = await client.post(
                    mcp_server.base_url,
                    json=jsonrpc_body,
                    headers=outbound_headers,
                )

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
                session=session, mcp_server=mcp_server,
                tool_name=request.tool_name, request_payload=request.params,
                response_payload=None, cache_hit=False,
                duration_ms=duration_ms, error=error,
            )
            raise
        except httpx.TimeoutException as exc:
            error = f"MCP server {request.server_name!r} timed out after 30s"
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

        # ── 6. Store in cache (only on success and if server allows caching) ──
        if error is None and mcp_server.cache_enabled:
            try:
                await self._cache.store_cached(
                    tool_name=request.tool_name,
                    input_payload=request.params,  # original params, not injected
                    response_payload=response_payload,
                    org_id=agent.org_id,
                )
            except Exception as exc:
                # Cache write failure must not prevent the response.
                logger.warning("proxy: cache store failed: %s", exc)

        # ── 7. Persist audit record ────────────────────────────────────────────
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

    # ── Preparation layer (shared by buffered + streaming paths) ─────────────

    async def prepare_tool_call(
        self,
        request: ToolCallRequest,
        agent: Agent,
    ) -> tuple[ToolCallResponse | None, PreparedCall | None]:
        """
        Run all pre-flight steps without making the upstream HTTP call.

        Steps executed:
            1. Resolve MCPServer.
            2. RBAC permission check.
            3. Semantic cache lookup (returns early on hit).
            4. Session ensure/create.
            5. Vault secret injection into params.

        Returns:
            ``(ToolCallResponse, None)`` when the cache was hit — the caller
            can return the response immediately without opening an upstream
            connection.

            ``(None, PreparedCall)`` on a cache miss — the caller should open
            the upstream connection and call ``finalize_json_call`` or use the
            streaming generator.
        """
        start_ms = time.monotonic()

        mcp_server = await self.resolve_server(request.server_name)

        permitted = await self._rbac.check_permission(
            agent=agent,
            mcp_server_id=mcp_server.id,
            tool_name=request.tool_name,
        )
        if not permitted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Agent {agent.name!r} does not have permission to call "
                    f"tool {request.tool_name!r} on server {request.server_name!r}"
                ),
            )

        # Cache lookup.
        cached_result = None
        if mcp_server.cache_enabled:
            cached_result = await self._cache.get_cached(
                tool_name=request.tool_name,
                input_payload=request.params,
            )

        session = await self._ensure_session(agent=agent, session_id=request.session_id)

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
            return (
                ToolCallResponse(
                    session_id=session.id,
                    event_id=event.id,
                    tool_name=request.tool_name,
                    result=cached_result,
                    cache_hit=True,
                    duration_ms=duration_ms,
                ),
                None,
            )

        # Vault injection.
        injected_params = await self.intercept_request(
            tool_name=request.tool_name,
            params=request.params,
            agent=agent,
        )

        jsonrpc_body: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {
                "name": request.tool_name,
                "arguments": injected_params,
            },
        }

        upstream_session_key = f"mcp_sessions:{session.id}:{request.server_name}"
        outbound_headers = await self._ensure_mcp_session(
            mcp_server=mcp_server,
            cache_key=upstream_session_key,
        )

        return (
            None,
            PreparedCall(
                mcp_server=mcp_server,
                session=session,
                jsonrpc_body=jsonrpc_body,
                outbound_headers=outbound_headers,
                upstream_session_key=upstream_session_key,
                raw_params=request.params,
                start_ms=start_ms,
            ),
        )

    async def finalize_json_call(
        self,
        prepared: PreparedCall,
        tool_name: str,
        http_resp: httpx.Response,
    ) -> ToolCallResponse:
        """
        Complete the non-streaming pipeline after reading an upstream JSON response.

        Steps:
            6. Parse JSON-RPC response body.
            7. Store in cache (if server allows caching and no error).
            8. Persist SessionEvent audit record.

        Args:
            prepared:   Context from ``prepare_tool_call``.
            tool_name:  Tool name from the original request.
            http_resp:  Fully-read httpx response (body already in memory).
        """
        mcp_server = prepared.mcp_server
        session = prepared.session
        start_ms = prepared.start_ms

        # Persist upstream MCP session ID if returned.
        upstream_session_id = http_resp.headers.get("Mcp-Session-Id")
        if upstream_session_id:
            try:
                await self.redis.set(prepared.upstream_session_key, upstream_session_id, ex=3600)
            except Exception as exc:
                logger.warning("proxy: Redis session store (json) failed: %s", exc)

        error: str | None = None
        response_payload: dict[str, Any] = {}

        if http_resp.status_code >= 400:
            error = f"MCP server {mcp_server.name!r} returned HTTP {http_resp.status_code}"
            duration_ms = int((time.monotonic() - start_ms) * 1000)
            await self._persist_event(
                session=session, mcp_server=mcp_server,
                tool_name=tool_name, request_payload=prepared.raw_params,
                response_payload=None, cache_hit=False,
                duration_ms=duration_ms, error=error,
            )
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=error)

        try:
            json_body = http_resp.json()
        except Exception:
            json_body = {"content": [{"type": "text", "text": http_resp.text}]}

        if "result" in json_body:
            response_payload = json_body["result"]
        elif "error" in json_body:
            error = json.dumps(json_body["error"])
            response_payload = json_body["error"]
        else:
            response_payload = json_body

        duration_ms = int((time.monotonic() - start_ms) * 1000)

        if error is None and mcp_server.cache_enabled:
            try:
                await self._cache.store_cached(
                    tool_name=tool_name,
                    input_payload=prepared.raw_params,
                    response_payload=response_payload,
                    org_id=session.org_id,
                )
            except Exception as exc:
                logger.warning("proxy: cache store failed: %s", exc)

        event = await self._persist_event(
            session=session,
            mcp_server=mcp_server,
            tool_name=tool_name,
            request_payload=prepared.raw_params,
            response_payload=response_payload if error is None else None,
            cache_hit=False,
            duration_ms=duration_ms,
            error=error,
        )

        return ToolCallResponse(
            session_id=session.id,
            event_id=event.id,
            tool_name=tool_name,
            result=response_payload,
            cache_hit=False,
            duration_ms=duration_ms,
        )

    # ── Streaming entry point ─────────────────────────────────────────────────

    async def iter_sse_stream(
        self,
        prepared: PreparedCall,
        tool_name: str,
        resp: httpx.Response,
    ) -> AsyncGenerator[bytes, None]:
        """
        Yield raw SSE bytes from an already-open upstream ``httpx.Response``.

        Caller is responsible for opening (and ultimately closing) the
        ``httpx.AsyncClient`` and ``httpx.Response``.  This method owns only
        the audit-persist side-effect on completion.

        Cache is intentionally skipped — SSE chunks are not individually
        cacheable.

        A ``SessionEvent`` with ``is_streaming=True`` is always persisted in a
        ``try/finally`` block so the audit record survives client disconnects.

        Args:
            prepared:  Context from ``prepare_tool_call``.
            tool_name: Tool name from the original request (for audit).
            resp:      Open upstream response with ``text/event-stream`` content.

        Yields:
            Raw SSE bytes from the upstream server.
        """
        error: str | None = None
        byte_count = 0
        first_chunk: bytes | None = None

        # Persist upstream MCP session ID if returned in response headers.
        upstream_session_id = resp.headers.get("Mcp-Session-Id")
        if upstream_session_id:
            try:
                await self.redis.set(
                    prepared.upstream_session_key, upstream_session_id, ex=3600
                )
            except Exception as exc:
                logger.warning("proxy: Redis session store (stream) failed: %s", exc)

        try:
            async for chunk in resp.aiter_bytes():
                if chunk:
                    byte_count += len(chunk)
                    if first_chunk is None:
                        first_chunk = chunk
                    yield chunk
        except Exception as exc:
            error = str(exc)
            logger.warning("proxy: SSE stream interrupted: %s", exc)
        finally:
            duration_ms = int((time.monotonic() - prepared.start_ms) * 1000)
            try:
                response_meta: dict[str, Any] = {
                    "streaming": True,
                    "byte_count": byte_count,
                }
                if first_chunk is not None:
                    try:
                        response_meta["first_chunk"] = first_chunk.decode(
                            "utf-8", errors="replace"
                        )
                    except Exception:
                        pass
                await self._persist_event(
                    session=prepared.session,
                    mcp_server=prepared.mcp_server,
                    tool_name=tool_name,
                    request_payload=prepared.raw_params,
                    response_payload=response_meta,
                    cache_hit=False,
                    is_streaming=True,
                    duration_ms=duration_ms,
                    error=error,
                )
            except Exception as exc:
                logger.warning("proxy: SSE audit persist failed: %s", exc)

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
            agent:     The calling agent (used for scoped secret lookup).

        Returns:
            dict: Modified params with placeholders resolved.
        """
        result: dict[str, Any] = {}
        for key, value in params.items():
            if isinstance(value, str):
                result[key] = await self._inject_secrets(value, agent.id)
            else:
                result[key] = value
        return result

    async def _inject_secrets(self, value: str, agent_id: uuid.UUID) -> str:
        """Replace all {{SECRET_NAME}} placeholders in a string value."""
        matches = _SECRET_PLACEHOLDER.findall(value)
        if not matches:
            return value
        for secret_name in set(matches):
            try:
                secret_value = await self._vault.get_secret(secret_name, agent_id=agent_id)
                value = value.replace(f"{{{{{secret_name}}}}}", secret_value)
            except KeyError:
                logger.warning(
                    "proxy: secret placeholder {{%s}} not found in vault for agent %s",
                    secret_name, agent_id,
                )
        return value

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def resolve_server(self, server_name: str) -> MCPServer:
        """Fetch MCPServer by name or raise 404."""
        result = await self.db.execute(
            select(MCPServer).where(
                MCPServer.name == server_name,
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

    async def _ensure_mcp_session(
        self,
        mcp_server: MCPServer,
        cache_key: str,
    ) -> dict[str, str]:
        """
        Return outbound headers for an upstream MCP server request.

        If a session ID is cached in Redis for this server, attach it.
        Otherwise, perform the MCP initialize handshake to obtain one,
        cache it, and attach it.  This handles the Streamable HTTP transport
        which requires an initialize before any tool calls.
        """
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

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

        # No cached session — do MCP initialize handshake.
        init_body = {
            "jsonrpc": "2.0",
            "id": "nexusai-init",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "nexusai-gateway", "version": "1.0"},
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
                logger.debug("proxy: initialized upstream MCP session %r for %s", session_id, mcp_server.name)
        except Exception as exc:
            logger.warning("proxy: MCP initialize handshake failed for %s: %s", mcp_server.name, exc)

        return headers

    async def _ensure_session(
        self,
        agent: Agent,
        session_id: uuid.UUID | None,
    ) -> Session:
        """
        Fetch an existing session or create a new one.

        If session_id is provided but does not belong to this agent, a new
        session is created (prevents session hijacking).
        """
        if session_id is not None:
            result = await self.db.execute(
                select(Session).where(
                    Session.id == session_id,
                    Session.agent_id == agent.id,
                )
            )
            session = result.scalar_one_or_none()
            if session is not None:
                return session

        session = Session(agent_id=agent.id, org_id=agent.org_id, metadata_={})
        self.db.add(session)
        await self.db.flush()   # populate session.id
        await self.db.commit()  # commit so the row is visible to the streaming generator's finally block
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
        is_streaming: bool = False,
    ) -> SessionEvent:
        """Append an immutable audit record to the session."""
        event = SessionEvent(
            session_id=session.id,
            org_id=session.org_id,
            mcp_server_id=mcp_server.id,
            tool_name=tool_name,
            request_payload=request_payload,
            response_payload=response_payload,
            cache_hit=cache_hit,
            is_streaming=is_streaming,
            duration_ms=duration_ms,
            error=error,
        )
        self.db.add(event)
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
            mcp_server = await self.resolve_server(server_name)
        return await self._rbac.filter_tools_list(
            agent_id=agent.id,
            mcp_server_id=mcp_server.id,
            tools=tools,
        )
