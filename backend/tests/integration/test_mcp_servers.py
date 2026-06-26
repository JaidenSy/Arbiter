"""
Integration tests for MCP Server endpoints.

Coverage:
    POST   /api/v1/mcp-servers         : 201, cache_enabled defaults to True
    GET    /api/v1/mcp-servers         : list (only active)
    GET    /api/v1/mcp-servers/{id}    : 200
    PATCH  /api/v1/mcp-servers/{id}    : partial update, non-None fields only
    DELETE /api/v1/mcp-servers/{id}    : 204, soft-delete

    Error cases:
    - POST duplicate name → 409
    - GET /mcp-servers/{non_existent} → 404
    - PATCH /mcp-servers/{non_existent} → 404
    - cache_enabled: False preserved through update
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_mcp_server(
    server_id: uuid.UUID | None = None,
    name: str = "test-server",
    base_url: str = "http://mcp.example.com",
    description: str | None = None,
    is_active: bool = True,
    cache_enabled: bool = True,
) -> MagicMock:
    s = MagicMock()
    s.id = server_id or uuid.uuid4()
    s.name = name
    s.base_url = base_url
    s.description = description
    s.is_active = is_active
    s.cache_enabled = cache_enabled
    return s


def _make_db_for_create(existing_server=None, created_server=None):
    """DB mock for POST /mcp-servers: first execute checks collision, refresh populates."""
    db = AsyncMock()
    call_count = 0

    async def execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.scalar_one_or_none.return_value = existing_server
        else:
            result.scalar_one_or_none.return_value = None
        return result

    db.execute = execute

    if created_server is not None:
        async def refresh(obj):
            obj.id = created_server.id
            obj.name = created_server.name
            obj.base_url = created_server.base_url
            obj.description = created_server.description
            obj.is_active = created_server.is_active
            obj.cache_enabled = created_server.cache_enabled

        db.refresh = refresh

    return db


def _make_db_for_get(server=None):
    """DB mock for GET/PATCH/DELETE: scalar_one_or_none returns server."""
    db = AsyncMock()

    async def execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = server
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [server] if server else []
        result.scalars.return_value = scalars_mock
        return result

    db.execute = execute

    async def refresh(obj):
        pass

    db.refresh = refresh
    return db


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestCreateMCPServer:
    @pytest.mark.asyncio
    async def test_create_mcp_server_returns_201_with_cache_enabled_true(self, fake_redis):
        """POST /mcp-servers → 201, cache_enabled defaults to True."""
        from app.main import app
        from app.core.dependencies import get_db, get_redis, get_current_agent, get_current_user
        from tests.conftest import _make_mock_agent, _make_mock_user, _make_mock_org
        from app.core.security import generate_api_key

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()
        mock_org = _make_mock_org()
        server_id = uuid.uuid4()
        created = _make_mcp_server(server_id=server_id, name="my-mcp", cache_enabled=True)
        db = _make_db_for_create(existing_server=None, created_server=created)
        from unittest.mock import AsyncMock as _AsyncMock
        db.get = _AsyncMock(return_value=mock_org)
        db.scalar = _AsyncMock(return_value=0)

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
                    "/api/v1/mcp-servers",
                    json={"name": "my-mcp", "base_url": "http://mcp.example.com"},
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["name"] == "my-mcp"
        assert data["cache_enabled"] is True

    @pytest.mark.asyncio
    async def test_create_mcp_server_cache_enabled_false(self, fake_redis):
        """POST /mcp-servers with cache_enabled=False → persisted as False."""
        from app.main import app
        from app.core.dependencies import get_db, get_redis, get_current_agent, get_current_user
        from tests.conftest import _make_mock_agent, _make_mock_user, _make_mock_org
        from app.core.security import generate_api_key

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()
        mock_org = _make_mock_org()
        server_id = uuid.uuid4()
        created = _make_mcp_server(server_id=server_id, name="side-effectful", cache_enabled=False)
        db = _make_db_for_create(existing_server=None, created_server=created)
        from unittest.mock import AsyncMock as _AsyncMock
        db.get = _AsyncMock(return_value=mock_org)
        db.scalar = _AsyncMock(return_value=0)

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
                    "/api/v1/mcp-servers",
                    json={"name": "side-effectful", "base_url": "http://mcp2.example.com", "cache_enabled": False},
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 201, resp.text
        assert resp.json()["cache_enabled"] is False

    @pytest.mark.asyncio
    async def test_create_duplicate_name_returns_409(self, fake_redis):
        """POST /mcp-servers with duplicate name → 409 Conflict."""
        from app.main import app
        from app.core.dependencies import get_db, get_redis, get_current_agent, get_current_user
        from tests.conftest import _make_mock_agent, _make_mock_user, _make_mock_org
        from app.core.security import generate_api_key

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()
        existing = _make_mcp_server(name="existing-server")
        db = _make_db_for_create(existing_server=existing)

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
                    "/api/v1/mcp-servers",
                    json={"name": "existing-server", "base_url": "http://mcp.example.com"},
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 409, resp.text

    @pytest.mark.asyncio
    async def test_create_name_with_double_underscore_returns_422(self, fake_redis):
        """'__' is the MCP endpoint's server__tool separator: reject it in names."""
        from app.main import app
        from app.core.dependencies import get_db, get_redis, get_current_agent, get_current_user
        from tests.conftest import _make_mock_agent, _make_mock_user
        from app.core.security import generate_api_key

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()
        mock_user.role = "owner"
        db = _make_db_for_create(existing_server=None)

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
                    "/api/v1/mcp-servers",
                    json={"name": "billing__v2", "base_url": "http://mcp.example.com"},
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 422, resp.text


class TestListMCPServers:
    @pytest.mark.asyncio
    async def test_list_mcp_servers_returns_active_only(self, authed_client):
        """GET /mcp-servers returns only active servers."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        active_server = _make_mcp_server(name="active-mcp", is_active=True)
        db = _make_db_for_get(server=active_server)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.get(
                "/api/v1/mcp-servers",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200, resp.text
        items = resp.json()
        assert len(items) == 1
        assert items[0]["name"] == "active-mcp"


class TestGetMCPServer:
    @pytest.mark.asyncio
    async def test_get_mcp_server_returns_200(self, authed_client):
        """GET /mcp-servers/{id} → 200 with server data."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        server_id = uuid.uuid4()
        server = _make_mcp_server(server_id=server_id, name="my-server")
        db = _make_db_for_get(server=server)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.get(
                f"/api/v1/mcp-servers/{server_id}",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200, resp.text
        assert resp.json()["id"] == str(server_id)

    @pytest.mark.asyncio
    async def test_get_nonexistent_mcp_server_returns_404(self, authed_client):
        """GET /mcp-servers/{non_existent} → 404."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        db = _make_db_for_get(server=None)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.get(
                f"/api/v1/mcp-servers/{uuid.uuid4()}",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404, resp.text


class TestPatchMCPServer:
    @pytest.mark.asyncio
    async def test_patch_updates_name_only(self, authed_client):
        """PATCH /mcp-servers/{id} with only name → partial update applied."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        server_id = uuid.uuid4()
        server = _make_mcp_server(
            server_id=server_id,
            name="old-name",
            base_url="http://old.example.com",
            cache_enabled=False,
        )
        db = _make_db_for_get(server=server)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.patch(
                f"/api/v1/mcp-servers/{server_id}",
                json={"name": "new-name"},
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200, resp.text
        # The server mock has name updated in place
        assert server.name == "new-name"
        # base_url should not be touched
        assert server.base_url == "http://old.example.com"

    @pytest.mark.asyncio
    async def test_patch_cache_enabled_false_preserved(self, authed_client):
        """PATCH with cache_enabled=False preserved (not overwritten to True)."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        server_id = uuid.uuid4()
        server = _make_mcp_server(server_id=server_id, cache_enabled=True)
        db = _make_db_for_get(server=server)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.patch(
                f"/api/v1/mcp-servers/{server_id}",
                json={"cache_enabled": False},
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200, resp.text
        assert server.cache_enabled is False

    @pytest.mark.asyncio
    async def test_patch_nonexistent_mcp_server_returns_404(self, authed_client):
        """PATCH /mcp-servers/{non_existent} → 404."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        db = _make_db_for_get(server=None)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.patch(
                f"/api/v1/mcp-servers/{uuid.uuid4()}",
                json={"name": "irrelevant"},
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404, resp.text


class TestDeleteMCPServer:
    @pytest.mark.asyncio
    async def test_delete_mcp_server_soft_deletes_and_returns_204(self, authed_client):
        """DELETE /mcp-servers/{id} → 204, is_active set to False (soft delete)."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        server_id = uuid.uuid4()
        server = _make_mcp_server(server_id=server_id, name="to-delete", is_active=True)
        db = _make_db_for_get(server=server)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.delete(
                f"/api/v1/mcp-servers/{server_id}",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 204, resp.text
        # Soft delete: is_active set to False on the ORM object
        assert server.is_active is False, "Soft delete must set is_active=False"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_mcp_server_returns_404(self, authed_client):
        """DELETE /mcp-servers/{non_existent} → 404."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        db = _make_db_for_get(server=None)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.delete(
                f"/api/v1/mcp-servers/{uuid.uuid4()}",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404, resp.text
