# Copyright 2026 Jaiden Sy
# SPDX-License-Identifier: Apache-2.0
"""
Arbiter ToolPinService: tool-definition pinning (rug-pull defense, OWASP MCP03).

An MCP server can change a tool's description or input schema after the tool
was reviewed, for example to slip prompt-injection text into the description
the model reads.  Nothing in the protocol stops that, so the gateway pins
what it saw:

    * Every time a server's tools are listed (aggregated /mcp tools/list,
      REST /proxy/{server}/tools, dashboard discovery), each tool's
      ``{name, description, inputSchema}`` is hashed as canonical JSON.
    * The first hash seen for (server, tool) is trusted on first use and
      becomes the approved pin.
    * A later, different hash flips the tool to ``changed`` (pending
      re-approval), logs a warning and fires the ``tool.definition_changed``
      webhook once per new hash.  Reverting to the approved definition clears
      the flag.
    * At call time ProxyService looks the pin up.  Calls to a ``changed``
      tool are blocked when the effective policy is ``block`` (server
      override, else org default), otherwise allowed and logged.
    * An admin approves the new definition through the REST API.

Annotations (readOnlyHint / idempotentHint) are read from the *approved*
definition only, so a server cannot unlock retries by changing its hints.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.mcp_server import MCPServer
from app.db.models.tool_definition import (
    TOOL_CHANGE_POLICY_ALLOW,
    TOOL_CHANGE_POLICY_BLOCK,
    TOOL_STATUS_APPROVED,
    TOOL_STATUS_CHANGED,
    ToolDefinition,
)
from app.services.webhook.webhook_service import dispatch_event as _dispatch_webhook

logger = logging.getLogger(__name__)

TOOL_DEFINITION_CHANGED_EVENT = "tool.definition_changed"


def definition_hash(tool: dict[str, Any]) -> str:
    """SHA-256 of the canonical JSON of a tool's name, description and inputSchema."""
    pinned = {
        "name": tool.get("name"),
        "description": tool.get("description"),
        "inputSchema": tool.get("inputSchema"),
    }
    canonical = json.dumps(pinned, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def effective_policy(mcp_server: Any, org: Any) -> str:
    """Server override wins; otherwise the org default; otherwise 'allow'."""
    for candidate in (
        getattr(mcp_server, "tool_change_policy", None),
        getattr(org, "tool_change_policy", None),
    ):
        if candidate == TOOL_CHANGE_POLICY_BLOCK:
            return TOOL_CHANGE_POLICY_BLOCK
        if candidate == TOOL_CHANGE_POLICY_ALLOW:
            return TOOL_CHANGE_POLICY_ALLOW
    return TOOL_CHANGE_POLICY_ALLOW


def is_retry_safe(pin: ToolDefinition | None) -> bool:
    """True when the approved definition declares the tool read-only or idempotent."""
    if pin is None:
        return False
    approved = pin.approved_definition
    if not isinstance(approved, dict):
        return False
    annotations = approved.get("annotations")
    if not isinstance(annotations, dict):
        return False
    return annotations.get("readOnlyHint") is True or annotations.get("idempotentHint") is True


class ToolPinService:
    """Records, checks and approves pinned tool definitions."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_tools(self, mcp_server: MCPServer, tools: list[dict[str, Any]]) -> list[str]:
        """
        Pin or compare every named tool from a tools/list response.

        Returns the names of tools that were newly flagged as changed on this
        call (a tool already flagged with the same new hash is not re-reported).
        Commits on the caller's session.
        """
        named = [t for t in tools if isinstance(t, dict) and t.get("name")]
        if not named:
            return []

        result = await self.db.execute(
            select(ToolDefinition).where(ToolDefinition.mcp_server_id == mcp_server.id)
        )
        existing = {row.tool_name: row for row in result.scalars().all()}

        now = datetime.now(tz=UTC)
        newly_changed: list[str] = []
        for tool in named:
            name = tool["name"]
            digest = definition_hash(tool)
            row = existing.get(name)
            if row is None:
                # Trust on first use: the first definition seen is the pin.
                self.db.add(
                    ToolDefinition(
                        org_id=mcp_server.org_id,
                        mcp_server_id=mcp_server.id,
                        tool_name=name,
                        approved_hash=digest,
                        approved_definition=tool,
                        current_hash=digest,
                        current_definition=tool,
                        status=TOOL_STATUS_APPROVED,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                )
                continue

            row.last_seen_at = now
            if digest == row.approved_hash:
                if row.status != TOOL_STATUS_APPROVED:
                    logger.info(
                        "tool_pin: %r on server %r reverted to its approved definition",
                        name,
                        mcp_server.name,
                    )
                row.status = TOOL_STATUS_APPROVED
                row.current_hash = digest
                row.current_definition = tool
                continue

            if row.status == TOOL_STATUS_CHANGED and row.current_hash == digest:
                continue  # already flagged for this exact definition

            row.status = TOOL_STATUS_CHANGED
            row.current_hash = digest
            row.current_definition = tool
            row.changed_at = now
            newly_changed.append(name)

        await self.db.commit()

        for name in newly_changed:
            logger.warning(
                "tool_pin: definition of %r on server %r changed since approval; "
                "pending re-approval",
                name,
                mcp_server.name,
            )
            asyncio.create_task(
                _dispatch_webhook(
                    mcp_server.org_id,
                    TOOL_DEFINITION_CHANGED_EVENT,
                    {
                        "server": mcp_server.name,
                        "server_id": str(mcp_server.id),
                        "tool": name,
                    },
                )
            )
        return newly_changed

    async def get_pin(self, mcp_server_id: uuid.UUID, tool_name: str) -> ToolDefinition | None:
        """Return the pin row for (server, tool), or None if never listed."""
        result = await self.db.execute(
            select(ToolDefinition).where(
                ToolDefinition.mcp_server_id == mcp_server_id,
                ToolDefinition.tool_name == tool_name,
            )
        )
        return result.scalar_one_or_none()

    async def approve(self, pin: ToolDefinition, user_id: uuid.UUID | None) -> ToolDefinition:
        """Accept the currently seen definition as the new pin."""
        pin.approved_hash = pin.current_hash
        pin.approved_definition = pin.current_definition
        pin.status = TOOL_STATUS_APPROVED
        pin.approved_at = datetime.now(tz=UTC)
        pin.approved_by_user_id = user_id
        await self.db.commit()
        await self.db.refresh(pin)
        return pin
