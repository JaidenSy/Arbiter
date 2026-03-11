"""
NexusAI — API endpoints: MCP Servers.

CRUD management of MCP server registrations.

Routes:
    POST   /mcp-servers          — register a new MCP server
    GET    /mcp-servers          — list all active MCP servers
    GET    /mcp-servers/{id}     — get a single server
    PATCH  /mcp-servers/{id}     — update name, url, description, or cache_enabled
    DELETE /mcp-servers/{id}     — soft-delete
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_agent, get_db
from app.db.models.agent import Agent
from app.db.models.mcp_server import MCPServer

router = APIRouter(prefix="/mcp-servers", tags=["mcp-servers"])


# ── Inline schemas ────────────────────────────────────────────────────────────

class MCPServerCreate(BaseModel):
    """Request body for creating an MCP server registration."""

    name: str = Field(..., min_length=1, max_length=255)
    base_url: str = Field(..., description="Full HTTP(S) URL of the MCP server")
    description: str | None = None
    cache_enabled: bool = Field(True, description="Set False for side-effectful servers that must never serve cached responses")


class MCPServerUpdate(BaseModel):
    """Partial update body — all fields optional."""

    name: str | None = None
    base_url: str | None = None
    description: str | None = None
    cache_enabled: bool | None = None


class MCPServerResponse(BaseModel):
    """Response schema for an MCP server."""

    id: uuid.UUID
    name: str
    base_url: str
    description: str | None
    is_active: bool
    cache_enabled: bool

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
    _current: Agent = Depends(get_current_agent),
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
            MCPServer.is_active.is_(True),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An MCP server named {body.name!r} already exists",
        )

    server = MCPServer(
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
    response_model=list[MCPServerResponse],
    summary="List all MCP servers",
)
async def list_mcp_servers(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _current: Agent = Depends(get_current_agent),
) -> list[MCPServerResponse]:
    """
    Return a paginated list of active MCP servers.

    Args:
        skip:     Number of records to skip (offset).
        limit:    Maximum records to return (capped at 200).
        db:       Injected DB session.
        _current: Auth guard.

    Returns:
        list[MCPServerResponse]: Active servers ordered by created_at DESC.
    """
    limit = min(limit, 200)
    result = await db.execute(
        select(MCPServer)
        .where(MCPServer.is_active.is_(True))
        .order_by(MCPServer.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    servers = result.scalars().all()
    return [MCPServerResponse.model_validate(s) for s in servers]


@router.get(
    "/{server_id}",
    response_model=MCPServerResponse,
    summary="Get MCP server by ID",
)
async def get_mcp_server(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current: Agent = Depends(get_current_agent),
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
    _current: Agent = Depends(get_current_agent),
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
    _current: Agent = Depends(get_current_agent),
) -> None:
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
        select(MCPServer).where(MCPServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server {server_id} not found",
        )

    server.is_active = False
    await db.commit()
