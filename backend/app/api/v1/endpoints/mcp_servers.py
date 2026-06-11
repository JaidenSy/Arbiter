"""
Arbiter — API endpoints: MCP Servers.

CRUD management of MCP server registrations.

Routes:
    POST   /mcp-servers               — register a new MCP server
    GET    /mcp-servers               — list all active MCP servers
    GET    /mcp-servers/{id}          — get a single server
    PATCH  /mcp-servers/{id}          — update name, url, description, or cache_enabled
    DELETE /mcp-servers/{id}          — soft-delete
    POST   /mcp-servers/{id}/test     — test connectivity
    GET    /mcp-servers/{id}/tools    — discover available tools
"""

from __future__ import annotations

import json as _json
import re
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.db.models.mcp_server import MCPServer
from app.db.models.organization import Organization
from app.db.models.user import User
from app.schemas.pagination import Page
from app.services.plan.plan_service import check_resource_limit
from app.services.vault.vault_service import VaultService

_MCP_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def _parse_mcp_response(r: httpx.Response) -> dict:
    """Parse JSON or SSE-wrapped JSON from an MCP Streamable HTTP response."""
    if "text/event-stream" in r.headers.get("content-type", ""):
        for line in r.text.splitlines():
            if line.startswith("data: "):
                return _json.loads(line[6:])
        return {}
    return r.json()


async def _mcp_tools_list(base_url: str, extra_headers: dict[str, str] | None = None) -> list[dict]:
    """Perform MCP initialize + tools/list handshake, return raw tools list."""
    url = base_url.rstrip("/")
    base = dict(_MCP_HEADERS)
    if extra_headers:
        base.update(extra_headers)
    async with httpx.AsyncClient(timeout=10.0) as client:
        init_resp = await client.post(
            url,
            json={
                "jsonrpc": "2.0",
                "id": "init",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "arbiter-discover", "version": "1.0"},
                },
            },
            headers=base,
        )
        session_headers = dict(base)
        if session_id := init_resp.headers.get("Mcp-Session-Id"):
            session_headers["Mcp-Session-Id"] = session_id
        resp = await client.post(
            url,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers=session_headers,
        )
    data = _parse_mcp_response(resp)
    return data.get("result", {}).get("tools", [])


async def _resolve_server_headers(server: MCPServer, db: AsyncSession) -> dict[str, str]:
    """Resolve {{vault:SECRET}} placeholders in server headers using org-level vault secrets."""
    import re

    if not server.headers:
        return {}
    vault = VaultService(db)
    _PLACEHOLDER = re.compile(r"\{\{(?:vault:)?([A-Za-z0-9_]+)\}\}")
    resolved: dict[str, str] = {}
    for hdr_name, hdr_value in server.headers.items():

        async def _resolve(val: str) -> str:
            for secret_name in set(_PLACEHOLDER.findall(val)):
                try:
                    secret_value = await vault.get_secret(
                        secret_name, org_id=server.org_id, agent_id=None
                    )
                    val = re.sub(
                        r"\{\{(?:vault:)?" + re.escape(secret_name) + r"\}\}", secret_value, val
                    )
                except KeyError:
                    pass
            return val

        resolved[hdr_name] = await _resolve(hdr_value)
    return resolved


router = APIRouter(prefix="/mcp-servers", tags=["mcp-servers"])


# ── Inline schemas ────────────────────────────────────────────────────────────


class MCPServerCreate(BaseModel):
    """Request body for creating an MCP server registration."""

    name: str = Field(..., min_length=1, max_length=255)
    base_url: str = Field(..., description="Full HTTP(S) URL of the MCP server")
    description: str | None = None
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Custom HTTP headers forwarded to the upstream server. Values may contain {{vault:SECRET_NAME}} placeholders.",
    )
    cache_enabled: bool = Field(
        True,
        description="Set False for side-effectful servers that must never serve cached responses",
    )
    cost_per_call_usd: float | None = Field(
        None,
        description="Optional per-call cost in USD for cost tracking; omit to disable",
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Ensure base_url is a valid HTTP(S) URL — SSRF/DNS check happens async in the endpoint."""
        stripped = v.strip()
        lower = stripped.lower()
        if not (lower.startswith("http://") or lower.startswith("https://")):
            raise ValueError("base_url must be a valid http:// or https:// URL")
        return stripped

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Reject '__' — it is the server/tool separator in the MCP endpoint's namespaced tool names."""
        if "__" in v:
            raise ValueError(
                "server name must not contain '__' (reserved as the server__tool separator)"
            )
        return v


class MCPServerUpdate(BaseModel):
    """Partial update body — all fields optional."""

    name: str | None = None
    base_url: str | None = None
    description: str | None = None
    headers: dict[str, str] | None = None
    cache_enabled: bool | None = None
    cost_per_call_usd: float | None = None
    is_active: bool | None = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str | None) -> str | None:
        """Ensure base_url is a valid HTTP(S) URL when provided — SSRF/DNS check happens async in the endpoint."""
        if v is None:
            return v
        stripped = v.strip()
        lower = stripped.lower()
        if not (lower.startswith("http://") or lower.startswith("https://")):
            raise ValueError("base_url must be a valid http:// or https:// URL")
        return stripped

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """Reject '__' — it is the server/tool separator in the MCP endpoint's namespaced tool names."""
        if v is not None and "__" in v:
            raise ValueError(
                "server name must not contain '__' (reserved as the server__tool separator)"
            )
        return v


class MCPServerTestResponse(BaseModel):
    reachable: bool
    tool_count: int | None = None
    error: str | None = None
    latency_ms: int | None = None


_VAULT_REF = re.compile(r"^\{\{(?:vault:)?[A-Za-z0-9_]+\}\}$")


def _mask_header_value(value: str) -> str:
    """Return value as-is if it's a vault reference; mask otherwise.

    Any raw value stored in the DB is a potential secret — users should be
    using {{vault:SECRET_NAME}} placeholders, not pasting keys directly.
    """
    return value if _VAULT_REF.match(value) else "***"


class MCPServerResponse(BaseModel):
    """Response schema for an MCP server."""

    id: uuid.UUID
    name: str
    base_url: str
    description: str | None
    headers: dict[str, str]
    is_active: bool
    cache_enabled: bool = Field(
        ...,
        description="Set False for side-effectful servers that must never serve cached responses",
    )
    cost_per_call_usd: float | None = None

    model_config = {"from_attributes": True}

    @field_validator("headers")
    @classmethod
    def mask_plaintext_headers(cls, v: dict[str, str]) -> dict[str, str]:
        return {k: _mask_header_value(val) for k, val in v.items()}


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=MCPServerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new MCP server",
)
async def create_mcp_server(
    body: MCPServerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> MCPServerResponse:
    """
    Register a new MCP server so agents can route tool calls to it.

    Args:
        body:     Server name, URL, optional description, and cache_enabled flag.
        db:       Injected DB session.
        _current: Auth guard.

    Returns:
        MCPServerResponse: The created server record.

    Raises:
        HTTPException 409: If an active server with the same name already exists.
    """
    await assert_ssrf_safe(body.base_url)

    existing = await db.execute(
        select(MCPServer).where(
            MCPServer.name == body.name,
            MCPServer.org_id == current_user.org_id,
            MCPServer.is_active.is_(True),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An MCP server named {body.name!r} already exists",
        )

    org = await db.get(Organization, current_user.org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Org not found",
        )
    await check_resource_limit(
        db=db,
        org=org,
        resource="mcp_servers",
        model=MCPServer,
        filter_col=MCPServer.org_id,
        count_active_only=True,
    )

    server = MCPServer(
        org_id=current_user.org_id,
        name=body.name,
        base_url=body.base_url,
        description=body.description,
        headers=body.headers,
        cache_enabled=body.cache_enabled,
        cost_per_call_usd=body.cost_per_call_usd,
        is_active=True,
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return MCPServerResponse.model_validate(server)


@router.get(
    "",
    response_model=Page[MCPServerResponse],
    summary="List all MCP servers",
)
async def list_mcp_servers(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[MCPServerResponse]:
    """
    Return a paginated list of active MCP servers.

    Args:
        skip:     Number of records to skip (offset).
        limit:    Maximum records to return (capped at 200).
        db:       Injected DB session.
        _current: Auth guard.

    Returns:
        Page[MCPServerResponse]: Active servers ordered by created_at DESC.
    """
    limit = min(limit, 200)
    total = (
        await db.scalar(
            select(func.count(MCPServer.id)).where(MCPServer.org_id == current_user.org_id)
        )
        or 0
    )
    result = await db.execute(
        select(MCPServer)
        .where(MCPServer.org_id == current_user.org_id)
        .order_by(MCPServer.is_active.desc(), MCPServer.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    servers = result.scalars().all()
    return Page(
        items=[MCPServerResponse.model_validate(s) for s in servers],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{server_id}",
    response_model=MCPServerResponse,
    summary="Get MCP server by ID",
)
async def get_mcp_server(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MCPServerResponse:
    """
    Return a single active MCP server by UUID.

    Args:
        server_id: UUID of the MCP server to retrieve.
        db:        Injected DB session.
        _current:  Auth guard.

    Returns:
        MCPServerResponse: The server's metadata.

    Raises:
        HTTPException 404: If the server does not exist or is inactive.
    """
    result = await db.execute(
        select(MCPServer).where(
            MCPServer.id == server_id,
            MCPServer.org_id == current_user.org_id,
            MCPServer.is_active.is_(True),
        )
    )
    server = result.scalar_one_or_none()
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server {server_id} not found",
        )
    return MCPServerResponse.model_validate(server)


@router.patch(
    "/{server_id}",
    response_model=MCPServerResponse,
    summary="Update MCP server",
)
async def update_mcp_server(
    server_id: uuid.UUID,
    body: MCPServerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> MCPServerResponse:
    """
    Partially update name, URL, description, or cache_enabled flag of an MCP server.

    Only fields explicitly provided (non-None) in the request body are applied.

    Args:
        server_id: UUID of the MCP server to update.
        body:      Partial update payload.
        db:        Injected DB session.
        _current:  Auth guard.

    Returns:
        MCPServerResponse: Updated server record.

    Raises:
        HTTPException 404: If the server does not exist or is inactive.
    """
    if body.base_url is not None:
        await assert_ssrf_safe(body.base_url)

    result = await db.execute(
        select(MCPServer).where(
            MCPServer.id == server_id,
            MCPServer.org_id == current_user.org_id,
        )
    )
    server = result.scalar_one_or_none()
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server {server_id} not found",
        )

    if body.is_active is True and not server.is_active:
        org = await db.get(Organization, current_user.org_id)
        if org is None:
            raise HTTPException(status_code=500, detail="Org not found")
        await check_resource_limit(
            db=db,
            org=org,
            resource="mcp_servers",
            model=MCPServer,
            filter_col=MCPServer.org_id,
            count_active_only=True,
        )

    if body.name is not None:
        server.name = body.name
    if body.base_url is not None:
        server.base_url = body.base_url
    if body.description is not None:
        server.description = body.description
    if body.headers is not None:
        server.headers = body.headers
    if body.cache_enabled is not None:
        server.cache_enabled = body.cache_enabled
    if body.cost_per_call_usd is not None:
        server.cost_per_call_usd = body.cost_per_call_usd
    if body.is_active is not None:
        server.is_active = body.is_active

    await db.commit()
    await db.refresh(server)
    return MCPServerResponse.model_validate(server)


@router.delete(
    "/{server_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate MCP server",
)
async def delete_mcp_server(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> Response:
    """
    Soft-delete an MCP server by setting is_active=False.

    Historical sessions and events referencing this server are preserved.

    Args:
        server_id: UUID of the MCP server to deactivate.
        db:        Injected DB session.
        _current:  Auth guard.

    Raises:
        HTTPException 404: If the server does not exist.
    """
    result = await db.execute(
        select(MCPServer).where(MCPServer.id == server_id, MCPServer.org_id == current_user.org_id)
    )
    server = result.scalar_one_or_none()
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server {server_id} not found",
        )

    await db.delete(server)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{server_id}/test",
    response_model=MCPServerTestResponse,
    summary="Test MCP server connectivity",
)
async def test_mcp_server(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MCPServerTestResponse:
    """Fire tools/list against the server and return tool count or error."""
    result = await db.execute(
        select(MCPServer).where(
            MCPServer.id == server_id,
            MCPServer.org_id == current_user.org_id,
            MCPServer.is_active.is_(True),
        )
    )
    server = result.scalar_one_or_none()
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"MCP server {server_id} not found"
        )

    import time

    try:
        t0 = time.monotonic()
        auth_headers = await _resolve_server_headers(server, db)
        tools = await _mcp_tools_list(server.base_url, extra_headers=auth_headers)
        latency_ms = int((time.monotonic() - t0) * 1000)
        return MCPServerTestResponse(reachable=True, tool_count=len(tools), latency_ms=latency_ms)
    except Exception as exc:
        return MCPServerTestResponse(reachable=False, error=str(exc))


class MCPToolInfo(BaseModel):
    name: str
    description: str | None = None


@router.get(
    "/{server_id}/tools",
    response_model=list[MCPToolInfo],
    summary="Discover tools available on an MCP server",
)
async def list_mcp_server_tools(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MCPToolInfo]:
    """Return the tools/list from the upstream MCP server for display in the UI."""
    result = await db.execute(
        select(MCPServer).where(
            MCPServer.id == server_id,
            MCPServer.org_id == current_user.org_id,
            MCPServer.is_active.is_(True),
        )
    )
    server = result.scalar_one_or_none()
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"MCP server {server_id} not found"
        )
    try:
        auth_headers = await _resolve_server_headers(server, db)
        tools = await _mcp_tools_list(server.base_url, extra_headers=auth_headers)
        return [
            MCPToolInfo(name=t.get("name", ""), description=t.get("description")) for t in tools
        ]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Could not fetch tools: {exc}"
        ) from exc


# ── Health history endpoint ───────────────────────────────────────────────────


class HealthCheckEntry(BaseModel):
    checked_at: str
    is_healthy: bool
    latency_ms: int | None
    error: str | None


class MCPServerHealthResponse(BaseModel):
    server_id: str
    uptime_pct: float  # 0.0–100.0; -1.0 = no data yet
    total_checks: int
    recent_checks: list[HealthCheckEntry]  # last 24 checks, newest first


@router.get(
    "/{server_id}/health",
    response_model=MCPServerHealthResponse,
    summary="Get health check history for an MCP server",
)
async def get_mcp_server_health(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MCPServerHealthResponse:
    """Return the last 24 health checks and uptime % for this server."""
    from app.db.models.mcp_server_health_check import MCPServerHealthCheck

    # Verify ownership
    result = await db.execute(
        select(MCPServer).where(MCPServer.id == server_id, MCPServer.org_id == current_user.org_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"MCP server {server_id} not found"
        )

    # Fetch last 24 checks
    checks_result = await db.execute(
        select(MCPServerHealthCheck)
        .where(
            MCPServerHealthCheck.server_id == server_id,
            MCPServerHealthCheck.org_id == current_user.org_id,
        )
        .order_by(MCPServerHealthCheck.checked_at.desc())
        .limit(24)
    )
    checks = checks_result.scalars().all()

    # Uptime % from all-time checks
    total_checks_result = await db.execute(
        select(func.count(MCPServerHealthCheck.id)).where(
            MCPServerHealthCheck.server_id == server_id,
            MCPServerHealthCheck.org_id == current_user.org_id,
        )
    )
    total_checks = int(total_checks_result.scalar_one() or 0)

    healthy_checks_result = await db.execute(
        select(func.count(MCPServerHealthCheck.id)).where(
            MCPServerHealthCheck.server_id == server_id,
            MCPServerHealthCheck.org_id == current_user.org_id,
            MCPServerHealthCheck.is_healthy.is_(True),
        )
    )
    healthy_count = int(healthy_checks_result.scalar_one() or 0)
    uptime_pct = (healthy_count / total_checks * 100) if total_checks > 0 else -1.0

    return MCPServerHealthResponse(
        server_id=str(server_id),
        uptime_pct=round(uptime_pct, 1),
        total_checks=total_checks,
        recent_checks=[
            HealthCheckEntry(
                checked_at=c.checked_at.isoformat(),
                is_healthy=c.is_healthy,
                latency_ms=c.latency_ms,
                error=c.error,
            )
            for c in checks
        ],
    )
