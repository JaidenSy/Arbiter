"""
Integration tests for POST/GET/DELETE /api/v1/agents

Uses httpx AsyncClient against the FastAPI app with mocked DB and Redis.

Coverage:
    - POST /api/v1/agents creates agent, returns API key starting with "nxai_"
    - API key only returned once: GET /api/v1/agents does not include key
    - DELETE /api/v1/agents/{id} sets is_active=False
    - Request without X-Arbiter-Key header returns 401
    - Request with invalid key returns 401
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_db_for_create_agent(existing_agent=None, created_agent=None):
    """
    Return a mock DB session suitable for create_agent endpoint:
    - First execute (name collision check): returns existing_agent (None = no collision)
    - db.refresh(agent): populates the agent's fields from created_agent template
    """
    db = AsyncMock()
    call_count = 0

    async def execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            # Name collision check
            result.scalar_one_or_none.return_value = existing_agent
        else:
            result.scalar_one_or_none.return_value = None
        return result

    db.execute = execute

    # db.refresh populates the agent object
    if created_agent is not None:
        async def refresh(obj):
            obj.id = created_agent["id"]
            obj.name = created_agent["name"]
            obj.description = created_agent.get("description")
            obj.is_active = True
            obj.created_at = created_agent.get("created_at", datetime.now(tz=timezone.utc))
            obj.updated_at = created_agent.get("updated_at", datetime.now(tz=timezone.utc))
        db.refresh = refresh

    return db


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestCreateAgent:
    @pytest.mark.asyncio
    async def test_create_agent_returns_201_and_api_key(self, fake_redis):
        """POST /api/v1/agents → 201 with api_key starting with nxai_"""
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        from app.core.dependencies import get_db, get_redis, get_current_user
        from tests.conftest import _make_mock_user, _make_mock_org
        from unittest.mock import AsyncMock as _AsyncMock

        agent_id = uuid.uuid4()
        now = datetime.now(tz=timezone.utc)

        mock_user = _make_mock_user()
        mock_org = _make_mock_org()
        db = _make_db_for_create_agent(
            existing_agent=None,
            created_agent={
                "id": agent_id,
                "name": "my-agent",
                "description": None,
                "created_at": now,
                "updated_at": now,
            },
        )
        db.get = _AsyncMock(return_value=mock_org)
        db.scalar = _AsyncMock(return_value=0)

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/agents",
                    json={"name": "my-agent"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "api_key" in data, "Response must include api_key"
        assert data["api_key"].startswith("nxai_"), (
            f"api_key {data['api_key']!r} does not start with 'nxai_'"
        )

    @pytest.mark.asyncio
    async def test_create_agent_name_collision_returns_409(self, fake_redis):
        """POST /api/v1/agents with duplicate name → 409"""
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        from app.core.dependencies import get_db, get_redis, get_current_user
        from tests.conftest import _make_mock_user
        from unittest.mock import AsyncMock as _AsyncMock

        # Simulate existing agent with same name
        existing = MagicMock()
        existing.name = "existing-agent"
        mock_user = _make_mock_user()
        db = _make_db_for_create_agent(existing_agent=existing)

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/agents",
                    json={"name": "existing-agent"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"


class TestGetAgents:
    @pytest.mark.asyncio
    async def test_list_agents_does_not_include_api_key(self, authed_client):
        """GET /api/v1/agents: response objects must NOT contain api_key field."""
        client, raw_key, mock_agent = authed_client

        # Override get_db to return list of agents
        from app.main import app
        from app.core.dependencies import get_db, get_current_agent

        agent_id = uuid.uuid4()
        now = datetime.now(tz=timezone.utc)

        def _make_agent_orm():
            a = MagicMock()
            a.id = agent_id
            a.name = "listed-agent"
            a.description = None
            a.is_active = True
            a.created_at = now
            a.updated_at = now
            return a

        db = AsyncMock()

        async def execute(stmt):
            result = MagicMock()
            scalars_result = MagicMock()
            scalars_result.all.return_value = [_make_agent_orm()]
            result.scalars.return_value = scalars_result
            return result

        db.execute = execute

        async def override_get_db():
            yield db

        async def override_current_agent():
            return mock_agent

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_agent] = override_current_agent

        try:
            resp = await client.get(
                "/api/v1/agents",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_agent, None)

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        agents_list = resp.json()
        for agent_item in agents_list:
            assert "api_key" not in agent_item, (
                "GET /agents must never return api_key in response"
            )

    @pytest.mark.asyncio
    async def test_list_agents_requires_auth(self, test_client):
        """GET /api/v1/agents without Authorization header → 401"""
        client = test_client
        resp = await client.get("/api/v1/agents")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


class TestDeleteAgent:
    @pytest.mark.asyncio
    async def test_delete_agent_sets_is_active_false(self, authed_client):
        """DELETE /api/v1/agents/{id} should soft-delete (is_active=False) and return 204."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db, get_current_agent

        agent_id = uuid.uuid4()
        target_agent = MagicMock()
        target_agent.id = agent_id
        target_agent.name = "to-delete"
        target_agent.is_active = True

        db = AsyncMock()

        async def execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = target_agent
            return result

        db.execute = execute

        async def override_get_db():
            yield db

        async def override_current_agent():
            return mock_agent

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_agent] = override_current_agent

        try:
            resp = await client.delete(
                f"/api/v1/agents/{agent_id}",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_agent, None)

        assert resp.status_code == 204, f"Expected 204, got {resp.status_code}: {resp.text}"
        # Verify is_active was set to False on the ORM object
        assert target_agent.is_active is False, "is_active was not set to False"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_agent_returns_404(self, authed_client):
        """DELETE /api/v1/agents/{id} for non-existent agent → 404"""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db, get_current_agent

        db = AsyncMock()

        async def execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        db.execute = execute

        async def override_get_db():
            yield db

        async def override_current_agent():
            return mock_agent

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_agent] = override_current_agent

        try:
            resp = await client.delete(
                f"/api/v1/agents/{uuid.uuid4()}",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_agent, None)

        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


class TestAuth:
    @pytest.mark.asyncio
    async def test_no_auth_header_returns_401(self, test_client):
        """Request without Authorization header → 401"""
        resp = await test_client.get("/api/v1/agents")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_key_returns_401(self, fake_redis):
        """Request with a key that doesn't match any agent → 401"""
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        from app.core.dependencies import get_db, get_redis

        # DB returns None for agent lookup (key not found)
        db = AsyncMock()

        async def execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        db.execute = execute

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/agents",
                    headers={"Authorization": "Bearer nxai_invalidkey000000000000000000000000000000000000000000000000000000"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_health_endpoint_requires_no_auth(self, test_client):
        """GET /health should return 200 without any auth."""
        resp = await test_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
