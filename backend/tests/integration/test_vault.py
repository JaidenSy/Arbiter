"""
Integration tests for Vault endpoints.

Coverage:
    POST   /api/v1/vault/secrets          — 201, no value in response
    GET    /api/v1/vault/secrets          — list scoped to current agent
    GET    /api/v1/vault/secrets/{id}     — returns decrypted value
    DELETE /api/v1/vault/secrets/{id}     — 204

    404 cases: non-existent secret on GET and DELETE
    Security: cross-agent isolation (Agent B cannot see Agent A's secrets)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_vault_secret(
    secret_id: uuid.UUID,
    name: str,
    agent_id: uuid.UUID,
    ciphertext: str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
) -> MagicMock:
    from datetime import datetime, timezone

    s = MagicMock()
    s.id = secret_id
    s.name = name
    s.agent_id = agent_id
    s.ciphertext = ciphertext
    s.created_at = datetime.now(timezone.utc)
    return s


def _make_authed_db(secret_obj=None, scalars_list=None):
    """
    Build a mock DB where:
      - scalar_one_or_none returns secret_obj
      - scalars().all() returns scalars_list (or [])
    """
    db = AsyncMock()

    async def execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = secret_obj
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = scalars_list or []
        result.scalars.return_value = scalars_mock
        return result

    db.execute = execute
    return db


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestCreateSecret:
    @pytest.mark.asyncio
    async def test_create_secret_returns_201_no_value(self, fake_redis):
        """POST /vault/secrets → 201, response has id/name/agent_id but NOT value."""
        from app.main import app
        from app.core.dependencies import get_db, get_redis, get_current_agent, get_current_user
        from tests.conftest import _make_mock_agent, _make_mock_user, _make_mock_org
        from app.core.security import generate_api_key

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()
        mock_org = _make_mock_org()
        secret_id = uuid.uuid4()

        # store_secret calls db.execute (upsert lookup) then db.commit + db.refresh
        db = AsyncMock()

        async def execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = None  # no existing secret
            return result

        async def refresh(obj):
            from datetime import datetime, timezone

            obj.id = secret_id
            obj.name = "MY_TOKEN"
            obj.agent_id = mock_agent.id
            obj.created_at = datetime.now(timezone.utc)

        db.execute = execute
        db.refresh = refresh
        db.get = AsyncMock(return_value=mock_org)
        db.scalar = AsyncMock(return_value=0)

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
                    "/api/v1/vault/secrets",
                    json={"name": "MY_TOKEN", "value": "super-secret"},
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert "id" in data
        assert data["name"] == "MY_TOKEN"
        assert "value" not in data, "POST response must NOT echo the secret value"

    @pytest.mark.asyncio
    async def test_create_secret_requires_auth(self, test_client):
        """POST /vault/secrets without auth → 401."""
        resp = await test_client.post(
            "/api/v1/vault/secrets",
            json={"name": "X", "value": "y"},
        )
        assert resp.status_code == 401


class TestListSecrets:
    @pytest.mark.asyncio
    async def test_list_secrets_scoped_to_agent(self, authed_client):
        """GET /vault/secrets returns only the calling agent's secrets."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        secret_id = uuid.uuid4()
        secret = _make_vault_secret(secret_id, "GITHUB_TOKEN", mock_agent.id)

        db = AsyncMock()

        async def execute(stmt):
            result = MagicMock()
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = [secret]
            result.scalars.return_value = scalars_mock
            return result

        db.execute = execute

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.get(
                "/api/v1/vault/secrets",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200, resp.text
        items = resp.json()
        assert len(items) == 1
        assert items[0]["name"] == "GITHUB_TOKEN"
        assert "value" not in items[0], "List response must NOT include secret value"

    @pytest.mark.asyncio
    async def test_list_secrets_empty_for_new_agent(self, authed_client):
        """GET /vault/secrets returns [] when agent has no secrets."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        db = _make_authed_db(scalars_list=[])

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.get(
                "/api/v1/vault/secrets",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200, resp.text
        assert resp.json() == []


class TestGetSecret:
    @pytest.mark.asyncio
    async def test_get_secret_returns_decrypted_value(self, fake_redis):
        """GET /vault/secrets/{id} returns id/name/value with plaintext."""
        from app.main import app
        from app.core.dependencies import get_db, get_redis, get_current_agent, get_current_user
        from app.services.vault.vault_service import VaultService
        from tests.conftest import _make_mock_agent, _make_mock_user
        from app.core.security import generate_api_key

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()
        secret_id = uuid.uuid4()

        # Encrypt a real value using VaultService so decrypt works
        svc = VaultService.__new__(VaultService)
        svc.db = None
        ciphertext = svc.encrypt("my-real-value")

        secret = _make_vault_secret(secret_id, "DB_PASSWORD", mock_agent.id, ciphertext)
        db = _make_authed_db(secret_obj=secret)

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
                resp = await client.get(
                    f"/api/v1/vault/secrets/{secret_id}",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["id"] == str(secret_id)
        assert data["name"] == "DB_PASSWORD"
        assert data["value"] == "my-real-value"

    @pytest.mark.asyncio
    async def test_get_nonexistent_secret_returns_404(self, authed_client):
        """GET /vault/secrets/{non_existent_id} → 404."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        db = _make_authed_db(secret_obj=None)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.get(
                f"/api/v1/vault/secrets/{uuid.uuid4()}",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404, resp.text


class TestDeleteSecret:
    @pytest.mark.asyncio
    async def test_delete_secret_returns_204(self, authed_client):
        """DELETE /vault/secrets/{id} → 204."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        secret_id = uuid.uuid4()
        secret = _make_vault_secret(secret_id, "OLD_KEY", mock_agent.id)
        db = _make_authed_db(secret_obj=secret)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.delete(
                f"/api/v1/vault/secrets/{secret_id}",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 204, resp.text
        # Verify the ORM object was actually deleted
        db.delete.assert_called_once_with(secret)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_secret_returns_404(self, authed_client):
        """DELETE /vault/secrets/{non_existent_id} → 404."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        db = _make_authed_db(secret_obj=None)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.delete(
                f"/api/v1/vault/secrets/{uuid.uuid4()}",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404, resp.text


class TestCrossAgentIsolation:
    @pytest.mark.asyncio
    async def test_agent_b_cannot_list_agent_a_secrets(self, fake_redis):
        """
        Agent B's GET /vault/secrets returns [] even though Agent A has secrets.

        The endpoint filters by current_agent.id so Agent B's call should never
        see Agent A's secrets — DB mock returns empty list when Agent B is the caller.
        """
        from app.main import app
        from app.core.dependencies import get_db, get_redis, get_current_agent, get_current_user
        from tests.conftest import _make_mock_agent, _make_mock_user
        from app.core.security import generate_api_key

        # Agent B
        raw_key_b = generate_api_key()
        mock_agent_b = _make_mock_agent(raw_key_b)
        mock_agent_b.id = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002")
        mock_user = _make_mock_user()

        # DB returns empty list (Agent B has no secrets)
        db = AsyncMock()

        async def execute(stmt):
            result = MagicMock()
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = []
            result.scalars.return_value = scalars_mock
            return result

        db.execute = execute

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent_b

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/vault/secrets",
                    headers={"Authorization": f"Bearer {raw_key_b}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        assert resp.json() == [], "Agent B must see 0 secrets (Agent A's secrets are isolated)"

    @pytest.mark.asyncio
    async def test_agent_b_get_agent_a_secret_by_id_returns_404(self, fake_redis):
        """
        Agent B calling GET /vault/secrets/{agent_a_secret_id} → 404 (not 403).

        The endpoint queries with WHERE id=? AND agent_id=current_agent.id,
        so a secret owned by Agent A returns None → 404.
        """
        from app.main import app
        from app.core.dependencies import get_db, get_redis, get_current_agent, get_current_user
        from tests.conftest import _make_mock_agent, _make_mock_user
        from app.core.security import generate_api_key

        raw_key_b = generate_api_key()
        mock_agent_b = _make_mock_agent(raw_key_b)
        mock_agent_b.id = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002")
        mock_user = _make_mock_user()

        agent_a_secret_id = uuid.uuid4()

        # DB returns None — the WHERE agent_id=B filter excludes Agent A's secret
        db = _make_authed_db(secret_obj=None)

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent_b

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    f"/api/v1/vault/secrets/{agent_a_secret_id}",
                    headers={"Authorization": f"Bearer {raw_key_b}"},
                )
        finally:
            app.dependency_overrides.clear()

        # Must be 404, not 403 — don't reveal existence of other agents' secrets
        assert resp.status_code == 404, (
            f"Expected 404 (not 403), got {resp.status_code}. "
            "Cross-agent access must not reveal secret existence."
        )
