"""
Integration tests for proxy quota enforcement on POST /api/v1/proxy/tool-call

Coverage:
    - Tool call from an org that has exceeded its monthly quota returns HTTP 429
    - Tool call from an enterprise org (unlimited) is never blocked by quota
    - Quota check fires BEFORE ProxyService (ProxyService is never reached on 429)
    - Under-quota org passes through quota check and reaches ProxyService normally
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_org(plan_tier: str = "free", org_id: uuid.UUID | None = None) -> MagicMock:
    org = MagicMock()
    org.id = org_id or uuid.uuid4()
    org.plan_tier = plan_tier
    return org


def _make_mock_agent(org_id: uuid.UUID) -> MagicMock:
    from app.core.security import generate_api_key, hash_api_key

    raw_key = generate_api_key()
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.name = "quota-test-agent"
    agent.is_active = True
    agent.org_id = org_id
    agent.api_key_hash = hash_api_key(raw_key)
    return agent, raw_key


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestProxyQuotaEnforcement:
    @pytest.mark.asyncio
    async def test_over_quota_org_gets_429(self, fake_redis):
        """
        An org that has hit its monthly quota should receive HTTP 429.

        Strategy:
            - Inject an agent belonging to a free org
            - Pre-load Redis cache with usage = 1050 (free limit = 1000, grace = 1050)
            - ProxyService.forward_tool_call is mocked: it must NOT be called
        """
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        from app.core.dependencies import get_db, get_redis, get_current_agent

        org_id = uuid.uuid4()
        org = _make_org(plan_tier="free", org_id=org_id)
        mock_agent, raw_key = _make_mock_agent(org_id=org_id)

        # Pre-load the quota cache key so Redis returns over-limit usage
        from datetime import datetime, timezone
        now = datetime.now(tz=timezone.utc)
        month_key = now.strftime("%Y-%m")
        cache_key = f"quota:{org_id}:tool_calls:{month_key}"
        await fake_redis.set(cache_key, b"1050")  # at effective limit (1000 * 1.05)

        db = AsyncMock()
        db.get = AsyncMock(return_value=org)  # db.get(Organization, agent.org_id) → org

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent

        proxy_called = []

        async def mock_forward(self, request, agent):
            proxy_called.append(True)
            from app.schemas.proxy import ToolCallResponse
            return ToolCallResponse(
                session_id=uuid.uuid4(),
                event_id=uuid.uuid4(),
                tool_name=request.tool_name,
                result={},
                cache_hit=False,
                duration_ms=1,
            )

        try:
            with patch(
                "app.services.proxy.proxy_service.ProxyService.forward_tool_call",
                new=mock_forward,
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post(
                        "/api/v1/proxy/tool-call",
                        json={
                            "server_name": "filesystem",
                            "tool_name": "read_file",
                            "params": {"path": "/tmp/test.txt"},
                        },
                        headers={"Authorization": f"Bearer {raw_key}"},
                    )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 429, (
            f"Expected HTTP 429 for over-quota org, got {resp.status_code}: {resp.text}"
        )
        # ProxyService must NOT have been invoked: quota guard fires first
        assert len(proxy_called) == 0, (
            "ProxyService.forward_tool_call was called despite org being over quota"
        )

    @pytest.mark.asyncio
    async def test_enterprise_org_is_not_quota_blocked(self, fake_redis):
        """
        Enterprise org has unlimited quota (None limit).
        Even with absurdly high usage in Redis, it must pass through to ProxyService.
        """
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        from app.core.dependencies import get_db, get_redis, get_current_agent
        from app.schemas.proxy import ToolCallResponse

        org_id = uuid.uuid4()
        org = _make_org(plan_tier="enterprise", org_id=org_id)
        mock_agent, raw_key = _make_mock_agent(org_id=org_id)

        # Put absurdly high usage in Redis: enterprise should ignore it
        from datetime import datetime, timezone
        now = datetime.now(tz=timezone.utc)
        month_key = now.strftime("%Y-%m")
        cache_key = f"quota:{org_id}:tool_calls:{month_key}"
        await fake_redis.set(cache_key, b"99999999")

        db = AsyncMock()
        db.get = AsyncMock(return_value=org)

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent

        proxy_call_count = [0]
        event_id = uuid.uuid4()
        session_id = uuid.uuid4()

        async def mock_forward(self, request, agent):
            proxy_call_count[0] += 1
            return ToolCallResponse(
                session_id=session_id,
                event_id=event_id,
                tool_name=request.tool_name,
                result={"content": "enterprise result"},
                cache_hit=False,
                duration_ms=5,
            )

        try:
            with patch(
                "app.services.proxy.proxy_service.ProxyService.forward_tool_call",
                new=mock_forward,
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post(
                        "/api/v1/proxy/tool-call",
                        json={
                            "server_name": "filesystem",
                            "tool_name": "read_file",
                            "params": {"path": "/tmp/test.txt"},
                        },
                        headers={"Authorization": f"Bearer {raw_key}"},
                    )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, (
            f"Enterprise org should not be quota-blocked, got {resp.status_code}: {resp.text}"
        )
        assert proxy_call_count[0] == 1, (
            "ProxyService.forward_tool_call should have been called for enterprise org"
        )

    @pytest.mark.asyncio
    async def test_under_quota_org_passes_through(self, fake_redis):
        """
        Org with usage well under its limit must reach ProxyService normally.
        """
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        from app.core.dependencies import get_db, get_redis, get_current_agent
        from app.schemas.proxy import ToolCallResponse

        org_id = uuid.uuid4()
        org = _make_org(plan_tier="pro", org_id=org_id)  # limit = 100_000
        mock_agent, raw_key = _make_mock_agent(org_id=org_id)

        from datetime import datetime, timezone
        now = datetime.now(tz=timezone.utc)
        month_key = now.strftime("%Y-%m")
        cache_key = f"quota:{org_id}:tool_calls:{month_key}"
        await fake_redis.set(cache_key, b"500")  # 500 << 100_000

        db = AsyncMock()
        db.get = AsyncMock(return_value=org)

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent

        event_id = uuid.uuid4()
        session_id = uuid.uuid4()
        proxy_called = [False]

        async def mock_forward(self, request, agent):
            proxy_called[0] = True
            return ToolCallResponse(
                session_id=session_id,
                event_id=event_id,
                tool_name=request.tool_name,
                result={"ok": True},
                cache_hit=False,
                duration_ms=10,
            )

        try:
            with patch(
                "app.services.proxy.proxy_service.ProxyService.forward_tool_call",
                new=mock_forward,
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post(
                        "/api/v1/proxy/tool-call",
                        json={
                            "server_name": "filesystem",
                            "tool_name": "list_dir",
                            "params": {"path": "/tmp"},
                        },
                        headers={"Authorization": f"Bearer {raw_key}"},
                    )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, (
            f"Under-quota org should reach ProxyService and return 200, got {resp.status_code}: {resp.text}"
        )
        assert proxy_called[0] is True
