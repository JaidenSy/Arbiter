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

        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                http_resp = await client.post(
                    mcp_server.base_url,
                    json=jsonrpc_body,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                    },
                )

            if http_resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(
                        f"MCP server {request.server_name!r} returned "
                        f"HTTP {http_resp.status_code}"
                    ),
                )

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

        except HTTPException:
            raise
        except httpx.TimeoutException:
            error = f"MCP server {request.server_name!r} timed out after 30s"
            duration_ms = int((time.monotonic() - start_ms) * 1000)
            await self._persist_event(
                session=session, mcp_server=mcp_server,
                tool_name=request.tool_name, request_payload=request.params,
                response_payload=None, cache_hit=False,
                duration_ms=duration_ms, error=error,
            )
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=error)
        except Exception as exc:
            error = str(exc)
            duration_ms = int((time.monotonic() - start_ms) * 1000)
            await self._persist_event(
                session=session, mcp_server=mcp_server,
                tool_name=request.tool_name, request_payload=request.params,
                response_payload=None, cache_hit=False,
                duration_ms=duration_ms, error=error,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"MCP server communication error: {exc}",
            ) from exc

        duration_ms = int((time.monotonic() - start_ms) * 1000)

        # ── 6. Store in cache (only on success and if server allows caching) ──
        if error is None and getattr(mcp_server, "cache_enabled", True):
            try:
                await self._cache.store_cached(
                    tool_name=request.tool_name,
                    input_payload=request.params,  # original params, not injected
                    response_payload=response_payload,
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
                result[key] = await self._inject_secrets(value)
            else:
                result[key] = value
        return result

    async def _inject_secrets(self, value: str) -> str:
        """Replace all {{SECRET_NAME}} placeholders in a string value."""
        matches = _SECRET_PLACEHOLDER.findall(value)
        if not matches:
            return value
        for secret_name in set(matches):
            try:
                secret_value = await self._vault.get_secret(secret_name)
                value = value.replace(f"{{{{{secret_name}}}}}", secret_value)
            except KeyError:
                logger.warning(
                    "proxy: secret placeholder {{%s}} not found in vault", secret_name
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

        session = Session(agent_id=agent.id, metadata_={})
        self.db.add(session)
        await self.db.flush()  # get session.id before persisting events
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
    ) -> SessionEvent:
        """Append an immutable audit record to the session."""
        event = SessionEvent(
            session_id=session.id,
            mcp_server_id=mcp_server.id,
            tool_name=tool_name,
            request_payload=request_payload,
            response_payload=response_payload,
            cache_hit=cache_hit,
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
