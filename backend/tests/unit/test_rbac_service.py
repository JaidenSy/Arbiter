"""
Unit tests for app.services.rbac.rbac_service

Coverage:
    - check_permission returns True when exact tool name is allowed
    - check_permission returns True when "*" wildcard is granted
    - check_permission returns False when no permission exists
    - get_allowed_tools returns correct list for agent
    - filter_tools_list removes tools agent cannot access
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_agent(agent_id: uuid.UUID | None = None, org_id: uuid.UUID | None = None) -> MagicMock:
    """Return a mock Agent ORM object."""
    agent = MagicMock()
    agent.id = agent_id or uuid.uuid4()
    agent.org_id = org_id or uuid.uuid4()
    agent.name = "test-agent"
    agent.is_active = True
    return agent


def _make_db_with_permission(tool_names: list[str]) -> AsyncMock:
    """
    Return a mock AsyncSession whose execute().scalar() returns True
    if any of the tool_names match (simulating EXISTS query).
    """
    db = AsyncMock()

    async def execute(stmt):
        # Return a mock result that yields True/False for scalar()
        result = MagicMock()
        result.scalar.return_value = len(tool_names) > 0
        return result

    db.execute = execute
    return db


def _make_db_for_get_allowed(tool_names: list[str]) -> AsyncMock:
    """Mock DB that returns given tool_names from scalars().all()."""
    db = AsyncMock()

    async def execute(stmt):
        result = MagicMock()
        scalars_result = MagicMock()
        scalars_result.all.return_value = tool_names
        result.scalars.return_value = scalars_result
        return result

    db.execute = execute
    return db


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestCheckPermission:
    @pytest.mark.asyncio
    async def test_returns_true_when_exact_tool_allowed(self):
        """check_permission → True when exact tool name exists in DB."""
        from app.services.rbac.rbac_service import RBACService

        agent = _make_agent()
        db = _make_db_with_permission(["read_file"])

        svc = RBACService(db=db)
        result = await svc.check_permission(
            agent=agent,
            mcp_server_id=uuid.uuid4(),
            tool_name="read_file",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_when_wildcard_granted(self):
        """check_permission → True when "*" wildcard covers the tool."""
        from app.services.rbac.rbac_service import RBACService

        agent = _make_agent()
        db = _make_db_with_permission(["*"])

        svc = RBACService(db=db)
        result = await svc.check_permission(
            agent=agent,
            mcp_server_id=uuid.uuid4(),
            tool_name="any_tool_name",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_no_permission_exists(self):
        """check_permission → False when no matching row in DB."""
        from app.services.rbac.rbac_service import RBACService

        agent = _make_agent()
        # DB returns False from EXISTS
        db = AsyncMock()

        async def execute(stmt):
            result = MagicMock()
            result.scalar.return_value = False
            return result

        db.execute = execute
        svc = RBACService(db=db)
        result = await svc.check_permission(
            agent=agent,
            mcp_server_id=uuid.uuid4(),
            tool_name="forbidden_tool",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_bool_type(self):
        """check_permission always returns a proper bool, not just truthy value."""
        from app.services.rbac.rbac_service import RBACService

        agent = _make_agent()
        db = _make_db_with_permission(["read_file"])
        svc = RBACService(db=db)
        result = await svc.check_permission(
            agent=agent,
            mcp_server_id=uuid.uuid4(),
            tool_name="read_file",
        )
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_org_id_is_included_in_query(self):
        """check_permission must include org_id in the WHERE clause.

        We capture the compiled SQL text and assert ToolPermission.org_id is
        referenced, preventing cross-org permission leakage from orphaned rows.
        """
        from sqlalchemy import exists, or_, select
        from app.db.models.tool_permission import ToolPermission
        from app.services.rbac.rbac_service import RBACService

        captured_stmts: list = []

        db = AsyncMock()

        async def execute(stmt):
            captured_stmts.append(stmt)
            result = MagicMock()
            result.scalar.return_value = False
            return result

        db.execute = execute

        org_id = uuid.uuid4()
        agent = _make_agent(org_id=org_id)
        svc = RBACService(db=db)
        await svc.check_permission(
            agent=agent,
            mcp_server_id=uuid.uuid4(),
            tool_name="some_tool",
        )

        assert len(captured_stmts) == 1, "Expected exactly one DB query"
        # Walk the compiled WHERE clauses and verify org_id column is referenced.
        stmt = captured_stmts[0]
        stmt_str = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        assert "org_id" in stmt_str, (
            "org_id filter missing from check_permission query — "
            "orphaned permission rows could grant unintended access"
        )


class TestGetAllowedTools:
    @pytest.mark.asyncio
    async def test_returns_list_of_tool_names(self):
        """get_allowed_tools returns the exact list from DB."""
        from app.services.rbac.rbac_service import RBACService

        agent_id = uuid.uuid4()
        server_id = uuid.uuid4()
        expected_tools = ["read_file", "write_file", "list_dir"]

        db = _make_db_for_get_allowed(expected_tools)
        svc = RBACService(db=db)
        result = await svc.get_allowed_tools(
            agent_id=agent_id,
            mcp_server_id=server_id,
        )
        assert result == expected_tools

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_permissions(self):
        from app.services.rbac.rbac_service import RBACService

        db = _make_db_for_get_allowed([])
        svc = RBACService(db=db)
        result = await svc.get_allowed_tools(
            agent_id=uuid.uuid4(),
            mcp_server_id=uuid.uuid4(),
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_wildcard_returned_as_is(self):
        """get_allowed_tools returns "*" literally when wildcard is granted."""
        from app.services.rbac.rbac_service import RBACService

        db = _make_db_for_get_allowed(["*"])
        svc = RBACService(db=db)
        result = await svc.get_allowed_tools(
            agent_id=uuid.uuid4(),
            mcp_server_id=uuid.uuid4(),
        )
        assert "*" in result


class TestFilterToolsList:
    @pytest.mark.asyncio
    async def test_removes_disallowed_tools(self):
        """filter_tools_list removes tools not in the allowed set."""
        from app.services.rbac.rbac_service import RBACService

        tools = [
            {"name": "read_file"},
            {"name": "write_file"},
            {"name": "delete_file"},
        ]
        # Agent only allowed to call read_file
        db = _make_db_for_get_allowed(["read_file"])
        svc = RBACService(db=db)
        result = await svc.filter_tools_list(
            agent_id=uuid.uuid4(),
            mcp_server_id=uuid.uuid4(),
            tools=tools,
        )
        assert len(result) == 1
        assert result[0]["name"] == "read_file"

    @pytest.mark.asyncio
    async def test_wildcard_returns_all_tools(self):
        """filter_tools_list returns all tools when "*" is in allowed set."""
        from app.services.rbac.rbac_service import RBACService

        tools = [
            {"name": "read_file"},
            {"name": "write_file"},
            {"name": "execute_code"},
        ]
        db = _make_db_for_get_allowed(["*"])
        svc = RBACService(db=db)
        result = await svc.filter_tools_list(
            agent_id=uuid.uuid4(),
            mcp_server_id=uuid.uuid4(),
            tools=tools,
        )
        assert result == tools

    @pytest.mark.asyncio
    async def test_empty_allowed_returns_empty_list(self):
        """filter_tools_list returns [] when agent has no permissions."""
        from app.services.rbac.rbac_service import RBACService

        tools = [{"name": "read_file"}, {"name": "write_file"}]
        db = _make_db_for_get_allowed([])
        svc = RBACService(db=db)
        result = await svc.filter_tools_list(
            agent_id=uuid.uuid4(),
            mcp_server_id=uuid.uuid4(),
            tools=tools,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_partial_match(self):
        """Only tools in the allowed list are returned."""
        from app.services.rbac.rbac_service import RBACService

        tools = [
            {"name": "alpha"},
            {"name": "beta"},
            {"name": "gamma"},
        ]
        db = _make_db_for_get_allowed(["alpha", "gamma"])
        svc = RBACService(db=db)
        result = await svc.filter_tools_list(
            agent_id=uuid.uuid4(),
            mcp_server_id=uuid.uuid4(),
            tools=tools,
        )
        names = [t["name"] for t in result]
        assert set(names) == {"alpha", "gamma"}
        assert len(result) == 2


class TestRevokePermission:
    @pytest.mark.asyncio
    async def test_revoke_deletes_redis_cache_key(self):
        """revoke_permission deletes the RBAC cache entry so the 30s stale window is closed."""
        from app.services.rbac.rbac_service import RBACService

        agent_id = uuid.uuid4()
        server_id = uuid.uuid4()
        tool = "write_file"

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock())
        db.commit = AsyncMock()

        redis = AsyncMock()
        redis.delete = AsyncMock()

        svc = RBACService(db=db, redis=redis)
        await svc.revoke_permission(
            agent_id=agent_id,
            mcp_server_id=server_id,
            tool_name=tool,
        )

        expected_key = f"rbac:{agent_id}:{server_id}:{tool}"
        redis.delete.assert_awaited_once_with(expected_key)

    @pytest.mark.asyncio
    async def test_revoke_without_redis_does_not_raise(self):
        """revoke_permission works correctly when no Redis client is provided."""
        from app.services.rbac.rbac_service import RBACService

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock())
        db.commit = AsyncMock()

        svc = RBACService(db=db, redis=None)
        await svc.revoke_permission(
            agent_id=uuid.uuid4(),
            mcp_server_id=uuid.uuid4(),
            tool_name="read_file",
        )  # must not raise
