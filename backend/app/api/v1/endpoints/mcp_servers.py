"""
NexusAI — API endpoints: MCP Servers.

CRUD management of MCP server registrations.

Routes:
    POST   /mcp-servers          — register a new MCP server
    GET    /mcp-servers          — list all active MCP servers
    GET    /mcp-servers/{id}     — get a single server
    PATCH  /mcp-servers/{id}     — update name, url, or description
    DELETE /mcp-servers/{id}     — soft-delete
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_agent, get_db
from app.db.models.agent import Agent

router = APIRouter(prefix="/mcp-servers", tags=["mcp-servers"])


# ── Inline schemas (simple enough not to warrant a separate schemas file) ──────

class MCPServerCreate(BaseModel):
    """Request body for creating an MCP server registration."""

    name: str = Field(..., min_length=1, max_length=255)
    base_url: str = Field(..., description="Full HTTP(S) URL of the MCP server")
    description: str | None = None


class MCPServerUpdate(BaseModel):
    """Partial update body — all fields optional."""

    name: str | None = None
    base_url: str | None = None
    description: str | None = None


class MCPServerResponse(BaseModel):
    """Response schema for an MCP server."""

    id: uuid.UUID
    name: str
    base_url: str
    description: str | None
    is_active: bool

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
        body:     Server name, URL, and optional description.
        db:       Injected DB session.
        _current: Auth guard.

    Returns:
        MCPServerResponse: The created server record.

    Raises:
        HTTPException 409: If a server with the same name already exists.
    """
    # TODO: persist MCPServer row
    raise NotImplementedError


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
    """Return a paginated list of active MCP servers."""
    # TODO: SELECT * FROM mcp_servers WHERE is_active=True
    raise NotImplementedError


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
    """Return a single MCP server by UUID."""
    # TODO: fetch MCPServer, raise 404 if not found
    raise NotImplementedError


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
    """Partially update name, URL, or description of an MCP server."""
    # TODO: fetch, apply partial update, commit
    raise NotImplementedError


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
    """Soft-delete an MCP server (sets is_active=False)."""
    # TODO: set server.is_active = False, commit
    raise NotImplementedError
