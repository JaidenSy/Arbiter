# Copyright (c) 2026 Jaiden Sy. All rights reserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Arbiter — RBACService.

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
    - All permission checks hit the DB directly; Redis caching can be layered
      on top in Phase 2 if permission-check latency becomes a bottleneck.
    - grant_permission is idempotent via INSERT ... ON CONFLICT DO NOTHING.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import delete, exists, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.models.tool_permission import ToolPermission

logger = logging.getLogger(__name__)


_RBAC_TTL = 30  # seconds


class RBACService:
    """
    Manages and enforces tool-call permissions for agents.
    """

    def __init__(self, db: AsyncSession, redis=None) -> None:
        """
        Initialise with injected DB session and optional Redis client.

        Args:
            db:    Async SQLAlchemy session.
            redis: Optional Redis client for permission caching (30s TTL).
        """
        self.db = db
        self.redis = redis

    async def check_permission(
        self,
        agent: Agent,
        mcp_server_id: uuid.UUID,
        tool_name: str,
    ) -> bool:
        """
        Return True if the agent has permission to call the tool.

        Checks both exact tool_name match and wildcard ``"*"`` in one query.
        The org_id filter prevents orphaned permission rows from deleted or
        migrated agents in other orgs from granting unintended access.
        Result is cached in Redis for 30 seconds to reduce DB load on hot paths.

        Args:
            agent:         The authenticated agent (provides id and org_id).
            mcp_server_id: UUID of the target MCP server.
            tool_name:     Name of the tool being called.

        Returns:
            bool: True if permitted, False otherwise.
        """
        cache_key = f"rbac:{agent.id}:{mcp_server_id}:{tool_name}"
        if self.redis is not None:
            try:
                cached = await self.redis.get(cache_key)
                if cached is not None:
                    return cached == b"1"
            except Exception as exc:
                logger.warning("rbac: Redis permission cache read failed: %s", exc)

        stmt = select(
            exists(
                select(ToolPermission.id).where(
                    ToolPermission.org_id == agent.org_id,
                    ToolPermission.agent_id == agent.id,
                    ToolPermission.mcp_server_id == mcp_server_id,
                    or_(
                        ToolPermission.tool_name == tool_name,
                        ToolPermission.tool_name == "*",
                    ),
                )
            )
        )
        result = await self.db.execute(stmt)
        permitted: bool = result.scalar()

        if self.redis is not None:
            try:
                await self.redis.setex(cache_key, _RBAC_TTL, b"1" if permitted else b"0")
            except Exception as exc:
                logger.warning("rbac: Redis permission cache write failed: %s", exc)

        logger.debug(
            "rbac: agent=%s server=%s tool=%r permitted=%s",
            agent.id,
            mcp_server_id,
            tool_name,
            permitted,
        )
        return permitted

    async def grant_permission(
        self,
        agent_id: uuid.UUID,
        mcp_server_id: uuid.UUID,
        tool_name: str,
        granted_by: str = "system",
    ) -> None:
        """
        Grant an agent permission to call a tool on an MCP server.

        Idempotent — does nothing if the permission already exists (ON CONFLICT
        DO NOTHING via PostgreSQL upsert).

        Args:
            agent_id:      UUID of the agent to grant access to.
            mcp_server_id: UUID of the target MCP server.
            tool_name:     Tool name, or ``"*"`` for all tools on this server.
            granted_by:    Human-readable identifier of who approved this.
        """
        stmt = (
            pg_insert(ToolPermission)
            .values(
                id=uuid.uuid4(),
                agent_id=agent_id,
                mcp_server_id=mcp_server_id,
                tool_name=tool_name,
                granted_by=granted_by,
            )
            .on_conflict_do_nothing(
                index_elements=["agent_id", "mcp_server_id", "tool_name"]
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()
        logger.info(
            "rbac: granted agent=%s server=%s tool=%r by=%r",
            agent_id,
            mcp_server_id,
            tool_name,
            granted_by,
        )

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
        """
        stmt = delete(ToolPermission).where(
            ToolPermission.agent_id == agent_id,
            ToolPermission.mcp_server_id == mcp_server_id,
            ToolPermission.tool_name == tool_name,
        )
        await self.db.execute(stmt)
        await self.db.commit()
        logger.info(
            "rbac: revoked agent=%s server=%s tool=%r",
            agent_id,
            mcp_server_id,
            tool_name,
        )

    async def get_cache_ttl(
        self,
        agent_id: uuid.UUID,
        mcp_server_id: uuid.UUID,
        tool_name: str,
    ) -> int | None:
        """Return cache_ttl_seconds override for (agent, server, tool), or None for global default."""
        result = await self.db.execute(
            select(ToolPermission.tool_name, ToolPermission.cache_ttl_seconds).where(
                ToolPermission.agent_id == agent_id,
                ToolPermission.mcp_server_id == mcp_server_id,
                or_(ToolPermission.tool_name == tool_name, ToolPermission.tool_name == "*"),
            )
        )
        rows = result.all()
        specific = next((r for r in rows if r.tool_name == tool_name), None)
        wildcard = next((r for r in rows if r.tool_name == "*"), None)
        row = specific or wildcard
        return row.cache_ttl_seconds if row else None

    async def get_allowed_tools(
        self,
        agent_id: uuid.UUID,
        mcp_server_id: uuid.UUID,
    ) -> list[str]:
        """
        Return all tool names the agent is permitted to call on the MCP server.

        A wildcard ``"*"`` entry is returned as-is; callers must handle it by
        passing through all tools from tools/list without filtering.

        Args:
            agent_id:      UUID of the agent.
            mcp_server_id: UUID of the MCP server.

        Returns:
            list[str]: Permitted tool names (may include ``"*"``).
        """
        result = await self.db.execute(
            select(ToolPermission.tool_name).where(
                ToolPermission.agent_id == agent_id,
                ToolPermission.mcp_server_id == mcp_server_id,
            )
        )
        return list(result.scalars().all())

    async def get_rate_limit(
        self,
        agent_id: uuid.UUID,
        mcp_server_id: uuid.UUID,
        tool_name: str,
    ) -> int | None:
        """
        Return the rate_limit_per_minute for (agent, server, tool).

        Checks specific tool first, then wildcard '*'.  Returns None if unlimited.
        """
        result = await self.db.execute(
            select(ToolPermission.tool_name, ToolPermission.rate_limit_per_minute).where(
                ToolPermission.agent_id == agent_id,
                ToolPermission.mcp_server_id == mcp_server_id,
                or_(ToolPermission.tool_name == tool_name, ToolPermission.tool_name == "*"),
            )
        )
        rows = result.all()
        # Prefer the specific-tool row's limit over the wildcard's
        specific = next((r for r in rows if r.tool_name == tool_name), None)
        wildcard = next((r for r in rows if r.tool_name == "*"), None)
        row = specific or wildcard
        return row.rate_limit_per_minute if row else None

    async def filter_tools_list(
        self,
        agent_id: uuid.UUID,
        mcp_server_id: uuid.UUID,
        tools: list[dict],
    ) -> list[dict]:
        """
        Filter a tools/list response to only include RBAC-permitted tools.

        If the agent has a wildcard ``"*"`` permission, all tools are returned.
        Otherwise only tools whose name appears in tool_permissions are kept.

        Args:
            agent_id:      UUID of the agent.
            mcp_server_id: UUID of the MCP server.
            tools:         List of tool dicts from the upstream tools/list response.

        Returns:
            list[dict]: Filtered list of tool dicts.
        """
        allowed = await self.get_allowed_tools(agent_id, mcp_server_id)
        if "*" in allowed:
            return tools
        allowed_set = set(allowed)
        return [t for t in tools if t.get("name") in allowed_set]
