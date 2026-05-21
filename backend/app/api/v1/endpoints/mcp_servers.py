"""
Arbiter — API endpoints: MCP Servers.

CRUD management of MCP server registrations.

Routes:
    POST   /mcp-servers          — register a new MCP server
    GET    /mcp-servers          — list all active MCP servers
    GET    /mcp-servers/{id}     — get a single server
    PATCH  /mcp-servers/{id}     — update name, url, description, or cache_enabled
    DELETE /mcp-servers/{id}     — soft-delete
"""

from __future__ import annotations

import ipaddress
import socket
import uuid
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.schemas.pagination import Page
from app.db.models.mcp_server import MCPServer
from app.db.models.organization import Organization
from app.db.models.user import User
from app.services.plan.plan_service import check_resource_limit

_PRIVATE_NETS = [
    ipaddress.ip_network(cidr) for cidr in (
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
        "127.0.0.0/8", "169.254.0.0/16", "::1/128", "fc00::/7",
    )
]


def _assert_ssrf_safe(url: str) -> None:
    """Raise ValueError if url resolves to a private/loopback address."""
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("base_url must contain a valid hostname")
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise ValueError(f"base_url hostname {hostname!r} could not be resolved")
    for _family, _type, _proto, _canonname, sockaddr in infos:
        addr = ipaddress.ip_address(sockaddr[0])
        if any(addr in net for net in _PRIVATE_NETS):
            raise ValueError(
                f"base_url resolves to a private/reserved address ({addr}) — "
                "registering internal hosts as MCP servers is not allowed"
            )

router = APIRouter(prefix="/mcp-servers", tags=["mcp-servers"])


# ── Inline schemas ────────────────────────────────────────────────────────────


class MCPServerCreate(BaseModel):
    """Request body for creating an MCP server registration."""

    name: str = Field(..., min_length=1, max_length=255)
    base_url: str = Field(..., description="Full HTTP(S) URL of the MCP server")
    description: str | None = None
    cache_enabled: bool = Field(
        True,
        description="Set False for side-effectful servers that must never serve cached responses",
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Ensure base_url is a public HTTP(S) URL — blocks SSRF via private IPs."""
        stripped = v.strip()
        lower = stripped.lower()
        if not (lower.startswith("http://") or lower.startswith("https://")):
            raise ValueError("base_url must be a valid http:// or https:// URL")
        _assert_ssrf_safe(stripped)
        return stripped


class MCPServerUpdate(BaseModel):
    """Partial update body — all fields optional."""

    name: str | None = None
    base_url: str | None = None
    description: str | None = None
    cache_enabled: bool | None = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str | None) -> str | None:
        """Ensure base_url is a public HTTP(S) URL when provided — blocks SSRF via private IPs."""
        if v is None:
            return v
        stripped = v.strip()
        lower = stripped.lower()
        if not (lower.startswith("http://") or lower.startswith("https://")):
            raise ValueError("base_url must be a valid http:// or https:// URL")
        _assert_ssrf_safe(stripped)
        return stripped


class MCPServerTestResponse(BaseModel):
    reachable: bool
    tool_count: int | None = None
    error: str | None = None
    latency_ms: int | None = None


class MCPServerResponse(BaseModel):
    """Response schema for an MCP server."""

    id: uuid.UUID
    name: str
    base_url: str
    description: str | None
    is_active: bool
    cache_enabled: bool = Field(
        ...,
        description="Set False for side-effectful servers that must never serve cached responses",
    )

    model_config = {"from_attributes": True}


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
    )

    server = MCPServer(
        org_id=current_user.org_id,
        name=body.name,
        base_url=body.base_url,
        description=body.description,
        cache_enabled=body.cache_enabled,
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
    total = await db.scalar(
        select(func.count(MCPServer.id)).where(
            MCPServer.is_active.is_(True), MCPServer.org_id == current_user.org_id
        )
    ) or 0
    result = await db.execute(
        select(MCPServer)
        .where(MCPServer.is_active.is_(True), MCPServer.org_id == current_user.org_id)
        .order_by(MCPServer.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    servers = result.scalars().all()
    return Page(items=[MCPServerResponse.model_validate(s) for s in servers], total=total, skip=skip, limit=limit)


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

    if body.name is not None:
        server.name = body.name
    if body.base_url is not None:
        server.base_url = body.base_url
    if body.description is not None:
        server.description = body.description
    if body.cache_enabled is not None:
        server.cache_enabled = body.cache_enabled

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
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id, MCPServer.org_id == current_user.org_id))
    server = result.scalar_one_or_none()
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server {server_id} not found",
        )

    server.is_active = False
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"MCP server {server_id} not found")

    import time
    url = server.base_url.rstrip("/") + "/tools/list"
    try:
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        latency_ms = int((time.monotonic() - t0) * 1000)
        if resp.status_code >= 400:
            return MCPServerTestResponse(reachable=False, error=f"HTTP {resp.status_code}", latency_ms=latency_ms)
        data = resp.json()
        tools = data.get("result", {}).get("tools", [])
        return MCPServerTestResponse(reachable=True, tool_count=len(tools), latency_ms=latency_ms)
    except Exception as exc:
        return MCPServerTestResponse(reachable=False, error=str(exc))
