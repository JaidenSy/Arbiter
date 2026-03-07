"""
NexusAI — RBACService.

Role-Based Access Control for tool call permissions.

Permission model:
    An Agent is allowed to call a specific tool on a specific MCP server
    if a matching row exists in tool_permissions:

        (agent_id, mcp_server_id, tool_name)

    The wildcard tool_name ``"*"`` grants access to ALL tools on that server.
    Specific tool entries take precedence over wildcards in error messages
    but both grant access (OR semantics).

Design decisions:
    - No role hierarchy in v1 — permissions are flat per (agent, server, tool).
    - Wildcard support keeps the admin UX simple for development agents.
    - All permission checks are cached in Redis for hot-path performance.
    - Cache is invalidated on every grant/revoke.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent


class RBACService:
    """
    Manages and enforces tool-call permissions for agents.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialise with injected DB session.

        Args:
            db: Async SQLAlchemy session.
        """
        self.db = db

    async def check_permission(
        self,
        agent: Agent,
        mcp_server_id: uuid.UUID,
        tool_name: str,
    ) -> bool:
        """
        Return True if the agent has permission to call the tool.

        Checks both exact tool_name match and wildcard ``"*"`` in one query.

        Args:
            agent:         The authenticated agent.
            mcp_server_id: UUID of the target MCP server.
            tool_name:     Name of the tool being called.

        Returns:
            bool: True if permitted, False otherwise.

        Raises:
            NotImplementedError: Until implemented.
        """
        # TODO: SELECT EXISTS (
        #           SELECT 1 FROM tool_permissions
        #           WHERE agent_id = agent.id
        #             AND mcp_server_id = mcp_server_id
        #             AND (tool_name = tool_name OR tool_name = '*')
        #       )
        raise NotImplementedError("RBACService.check_permission not yet implemented")

    async def grant_permission(
        self,
        agent_id: uuid.UUID,
        mcp_server_id: uuid.UUID,
        tool_name: str,
        granted_by: str,
    ) -> None:
        """
        Grant an agent permission to call a tool on an MCP server.

        Idempotent — does nothing if the permission already exists.

        Args:
            agent_id:      UUID of the agent to grant access to.
            mcp_server_id: UUID of the target MCP server.
            tool_name:     Tool name, or ``"*"`` for all tools on this server.
            granted_by:    Human-readable identifier of who approved this.

        Raises:
            NotImplementedError: Until implemented.
        """
        # TODO: INSERT INTO tool_permissions ... ON CONFLICT DO NOTHING
        raise NotImplementedError("RBACService.grant_permission not yet implemented")

    async def revoke_permission(
        self,
        agent_id: uuid.UUID,
        mcp_server_id: uuid.UUID,
        tool_name: str,
    ) -> None:
        """
        Revoke an agent's permission to call a specific tool.

        Args:
            agent_id:      UUID of the agent.
            mcp_server_id: UUID of the MCP server.
            tool_name:     Tool name to revoke (or ``"*"`` to revoke the wildcard).

        Raises:
            NotImplementedError: Until implemented.
        """
        # TODO: DELETE FROM tool_permissions WHERE agent_id=... AND tool_name=...
        raise NotImplementedError("RBACService.revoke_permission not yet implemented")
