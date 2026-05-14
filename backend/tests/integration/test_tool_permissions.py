"""
Integration tests for Tool Permissions endpoints.

Coverage:
    POST   /api/v1/agents/{id}/permissions          — 201
    POST   with tool_name="*"                       — 201 (wildcard)
    GET    /api/v1/agents/{id}/permissions          — list
    DELETE /api/v1/agents/{id}/permissions/{perm}  — 204

    Error cases:
    - POST duplicate (same agent+server+tool) → 409
    - POST with non-existent agent_id → 404
    - POST with non-existent mcp_server_id → 404
    - DELETE non-existent permission → 404
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.exc import IntegrityError

import pytest
from httpx import AsyncClient, ASGITransport


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_agent_orm(agent_id: uuid.UUID, is_active: bool = True) -> MagicMock:
    a = MagicMock()
    a.id = agent_id
    a.is_active = is_active
    return a


def _make_server_orm(server_id: uuid.UUID, is_active: bool = True) -> MagicMock:
    s = MagicMock()
    s.id = server_id
    s.is_active = is_active
    return s


def _make_permission_orm(
    perm_id: uuid.UUID,
    agent_id: uuid.UUID,
    mcp_server_id: uuid.UUID,
    tool_name: str,
) -> MagicMock:
    from datetime import datetime, timezone

    p = MagicMock()
    p.id = perm_id
    p.agent_id = agent_id
    p.mcp_server_id = mcp_server_id
    p.tool_name = tool_name
    p.granted_at = datetime.now(timezone.utc)
    p.granted_by = None
    return p


def _make_db_for_create(agent=None, server=None, raises_integrity=False):
    """
    DB mock for POST /agents/{id}/permissions:
      call 1 → agent lookup
      call 2 → server lookup
      commit → optionally raise IntegrityError
    """
    db = AsyncMock()
    call_count = 0

    async def execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.scalar_one_or_none.return_value = agent
        elif call_count == 2:
            result.scalar_one_or_none.return_value = server
        else:
            result.scalar_one_or_none.return_value = None
        return result

    db.execute = execute

    if raises_integrity:
        db.commit.side_effect = IntegrityError("duplicate", {}, None)
    else:
        db.commit.return_value = None

    async def refresh(obj):
        from datetime import datetime, timezone

        obj.id = uuid.uuid4()
        obj.granted_at = datetime.now(timezone.utc)
        obj.granted_by = None

    db.refresh = refresh
    return db


def _make_db_for_list(agent=None, permissions=None):
    """DB mock for GET /agents/{id}/permissions."""
    db = AsyncMock()
    call_count = 0

    async def execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.scalar_one_or_none.return_value = agent
        else:
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = permissions or []
            result.scalars.return_value = scalars_mock
        return result

    db.execute = execute
    return db


def _make_db_for_delete(permission=None):
    """DB mock for DELETE /agents/{id}/permissions/{perm_id}."""
    db = AsyncMock()

    async def execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = permission
        return result

    db.execute = execute
    return db


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestCreateToolPermission:
    @pytest.mark.asyncio
    async def test_create_permission_returns_201(self, fake_redis):
        """POST /agents/{id}/permissions → 201 with permission record."""
        from app.main import app
        from app.core.dependencies import get_db, get_redis, get_current_agent, get_current_user
        from tests.conftest import _make_mock_agent, _make_mock_user
        from app.core.security import generate_api_key

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()

        target_agent_id = uuid.uuid4()
        server_id = uuid.uuid4()

        agent_orm = _make_agent_orm(target_agent_id)
        server_orm = _make_server_orm(server_id)
        db = _make_db_for_create(agent=agent_orm, server=server_orm)

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/agents/{target_agent_id}/permissions",
                    json={"mcp_server_id": str(server_id), "tool_name": "search"},
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert "id" in data
        assert data["tool_name"] == "search"

    @pytest.mark.asyncio
    async def test_create_permission_wildcard_tool_name(self, fake_redis):
        """POST /agents/{id}/permissions with tool_name='*' → 201."""
        from app.main import app
        from app.core.dependencies import get_db, get_redis, get_current_agent, get_current_user
        from tests.conftest import _make_mock_agent, _make_mock_user
        from app.core.security import generate_api_key

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()

        target_agent_id = uuid.uuid4()
        server_id = uuid.uuid4()

        agent_orm = _make_agent_orm(target_agent_id)
        server_orm = _make_server_orm(server_id)
        db = _make_db_for_create(agent=agent_orm, server=server_orm)

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/agents/{target_agent_id}/permissions",
                    json={"mcp_server_id": str(server_id), "tool_name": "*"},
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 201, resp.text
        assert resp.json()["tool_name"] == "*"

    @pytest.mark.asyncio
    async def test_create_permission_nonexistent_agent_returns_404(self, fake_redis):
        """POST /agents/{non_existent_id}/permissions → 404."""
        from app.main import app
        from app.core.dependencies import get_db, get_redis, get_current_agent, get_current_user
        from tests.conftest import _make_mock_agent, _make_mock_user
        from app.core.security import generate_api_key

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()

        db = _make_db_for_create(agent=None, server=_make_server_orm(uuid.uuid4()))

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/agents/{uuid.uuid4()}/permissions",
                    json={"mcp_server_id": str(uuid.uuid4()), "tool_name": "x"},
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404, resp.text

    @pytest.mark.asyncio
    async def test_create_permission_nonexistent_server_returns_404(self, fake_redis):
        """POST /agents/{id}/permissions with non-existent mcp_server_id → 404."""
        from app.main import app
        from app.core.dependencies import get_db, get_redis, get_current_agent, get_current_user
        from tests.conftest import _make_mock_agent, _make_mock_user
        from app.core.security import generate_api_key

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()

        target_agent_id = uuid.uuid4()
        agent_orm = _make_agent_orm(target_agent_id)
        db = _make_db_for_create(agent=agent_orm, server=None)

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/agents/{target_agent_id}/permissions",
                    json={"mcp_server_id": str(uuid.uuid4()), "tool_name": "x"},
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404, resp.text

    @pytest.mark.asyncio
    async def test_create_duplicate_permission_returns_409(self, fake_redis):
        """POST duplicate (same agent+server+tool) → 409 Conflict."""
        from app.main import app
        from app.core.dependencies import get_db, get_redis, get_current_agent, get_current_user
        from tests.conftest import _make_mock_agent, _make_mock_user
        from app.core.security import generate_api_key

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()

        target_agent_id = uuid.uuid4()
        server_id = uuid.uuid4()
        agent_orm = _make_agent_orm(target_agent_id)
        server_orm = _make_server_orm(server_id)
        db = _make_db_for_create(agent=agent_orm, server=server_orm, raises_integrity=True)

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/agents/{target_agent_id}/permissions",
                    json={"mcp_server_id": str(server_id), "tool_name": "search"},
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 409, resp.text


class TestListToolPermissions:
    @pytest.mark.asyncio
    async def test_list_permissions_returns_200(self, authed_client):
        """GET /agents/{id}/permissions → 200 with list."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        agent_id = uuid.uuid4()
        server_id = uuid.uuid4()
        perm_id = uuid.uuid4()

        agent_orm = _make_agent_orm(agent_id)
        perm = _make_permission_orm(perm_id, agent_id, server_id, "search")
        db = _make_db_for_list(agent=agent_orm, permissions=[perm])

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.get(
                f"/api/v1/agents/{agent_id}/permissions",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200, resp.text
        items = resp.json()
        assert len(items) == 1
        assert items[0]["tool_name"] == "search"

    @pytest.mark.asyncio
    async def test_list_permissions_nonexistent_agent_returns_404(self, authed_client):
        """GET /agents/{non_existent}/permissions → 404."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        db = _make_db_for_list(agent=None)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.get(
                f"/api/v1/agents/{uuid.uuid4()}/permissions",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404, resp.text


class TestDeleteToolPermission:
    @pytest.mark.asyncio
    async def test_delete_permission_returns_204(self, authed_client):
        """DELETE /agents/{id}/permissions/{perm_id} → 204."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        agent_id = uuid.uuid4()
        server_id = uuid.uuid4()
        perm_id = uuid.uuid4()
        perm = _make_permission_orm(perm_id, agent_id, server_id, "search")
        db = _make_db_for_delete(permission=perm)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.delete(
                f"/api/v1/agents/{agent_id}/permissions/{perm_id}",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 204, resp.text
        db.delete.assert_called_once_with(perm)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_permission_returns_404(self, authed_client):
        """DELETE /agents/{id}/permissions/{non_existent_perm} → 404."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        db = _make_db_for_delete(permission=None)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.delete(
                f"/api/v1/agents/{uuid.uuid4()}/permissions/{uuid.uuid4()}",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404, resp.text
