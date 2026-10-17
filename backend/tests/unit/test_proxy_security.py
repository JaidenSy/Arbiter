"""
Unit tests for ProxyService security hardening (roadmap #4).

Coverage:
    Cache scoping:
        - args with a vault placeholder -> cache lookup/store keyed by agent
        - placeholder-free args stay org-shared (agent_id=None)
        - upstream ``isError: true`` results are never cached
    Retry safety:
        - ReadTimeout is NOT retried for an unannotated tool
        - ReadTimeout IS retried when the approved definition is readOnlyHint
        - PoolTimeout (connect phase) is retried
    Tool-definition pinning:
        - changed tool + policy 'block' -> 403, audited, upstream never called
        - changed tool + policy 'allow' -> call proceeds
        - fetch_tools_list records definitions; a pin failure never fails it
    Audit gaps (SessionEvent persisted, not billed):
        - scope, per-tool rate limit, agent rate limit, quota, session budget,
          vault placeholder resolution (400, not 500), server header secret (502)
        - an audit-write failure does not mask the rejection
        - _persist_event(count_usage=False) skips usage counters and cost
"""

from __future__ import annotations

import uuid
from contextlib import ExitStack
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

import app.main  # noqa: F401  (registers every model so ORM mappers configure)
from app.db.models.tool_definition import ToolDefinition
from app.schemas.proxy import ToolCallRequest
from app.services.plan.plan_limits import QuotaExceededError, SessionBudgetExceededError
from app.services.proxy.proxy_service import _MAX_RETRIES, ProxyService
from app.services.tool_pin.tool_pin_service import definition_hash

P = "app.services.proxy.proxy_service"

# ── Fixtures / helpers ────────────────────────────────────────────────────────


def _agent(**overrides) -> MagicMock:
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.org_id = uuid.uuid4()
    agent.name = "agent-a"
    agent.scope = "full"
    agent.rate_limit_per_minute = None
    agent.max_calls_per_session = None
    for k, v in overrides.items():
        setattr(agent, k, v)
    return agent


def _server(org_id, **overrides) -> MagicMock:
    s = MagicMock()
    s.id = uuid.uuid4()
    s.org_id = org_id
    s.name = "github"
    s.base_url = "http://fake-mcp:9000"
    s.headers = {}
    s.cache_enabled = False
    s.tool_change_policy = None
    s.cost_per_call_usd = None
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def _org(policy: str = "allow") -> MagicMock:
    org = MagicMock()
    org.id = uuid.uuid4()
    org.plan_tier = "free"
    org.tool_change_policy = policy
    return org


def _pin(server, tool: dict, *, status: str = "approved") -> ToolDefinition:
    return ToolDefinition(
        id=uuid.uuid4(),
        org_id=server.org_id,
        mcp_server_id=server.id,
        tool_name=tool["name"],
        approved_hash=definition_hash(tool),
        approved_definition=tool,
        current_hash=definition_hash(tool) if status == "approved" else "f" * 64,
        current_definition=tool,
        status=status,
    )


def _ok(result: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {}
    resp.json.return_value = {"result": result or {"content": [{"type": "text", "text": "ok"}]}}
    return resp


class _Client:
    """Stand-in for httpx.AsyncClient: raises/returns from a scripted list."""

    def __init__(self, script: list):
        self.script = list(script)
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def post(self, *a, **kw):
        self.calls += 1
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return item


class Harness:
    """Builds a ProxyService with every collaborator mocked except the logic under test."""

    def __init__(self, *, agent=None, server=None, org=None, pin=None, client=None, redis=None):
        self.agent = agent or _agent()
        self.server = server or _server(self.agent.org_id)
        self.org = org or _org()
        self.pin = pin
        self.client = client or _Client([_ok()])
        self.redis = redis or AsyncMock()
        if redis is None:
            self.redis.get = AsyncMock(return_value=None)
            self.redis.incr = AsyncMock(return_value=1)
        self.db = AsyncMock()
        self.db.get = AsyncMock(return_value=self.org)
        self.svc = ProxyService(self.db, self.redis)
        self.session = MagicMock(id=uuid.uuid4(), org_id=self.agent.org_id)
        self.persist = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))
        self.quota = AsyncMock()
        self.webhook = AsyncMock()

    def enter(self, stack: ExitStack, *, real_intercept: bool = False):
        svc = self.svc
        stack.enter_context(
            patch.object(svc, "resolve_server", new=AsyncMock(return_value=self.server))
        )
        stack.enter_context(
            patch.object(svc, "_ensure_session", new=AsyncMock(return_value=self.session))
        )
        stack.enter_context(
            patch.object(svc._rbac, "check_permission", new=AsyncMock(return_value=True))
        )
        stack.enter_context(
            patch.object(svc._rbac, "get_rate_limit", new=AsyncMock(return_value=None))
        )
        stack.enter_context(
            patch.object(svc._rbac, "get_cache_ttl", new=AsyncMock(return_value=None))
        )
        stack.enter_context(
            patch.object(svc._pins, "get_pin", new=AsyncMock(return_value=self.pin))
        )
        if not real_intercept:
            stack.enter_context(
                patch.object(svc, "intercept_request", new=AsyncMock(return_value={}))
            )
        stack.enter_context(
            patch.object(svc, "_ensure_mcp_session", new=AsyncMock(return_value={}))
        )
        stack.enter_context(patch.object(svc, "_persist_event", new=self.persist))
        stack.enter_context(patch(f"{P}.check_tool_call_quota", new=self.quota))
        stack.enter_context(patch(f"{P}.assert_ssrf_safe", new=AsyncMock()))
        stack.enter_context(patch(f"{P}._dispatch_webhook", new=self.webhook))
        stack.enter_context(patch(f"{P}.PLAN_LIMITS", {"free": {"semantic_cache": False}}))
        stack.enter_context(patch(f"{P}.asyncio.sleep", new=AsyncMock()))
        stack.enter_context(patch(f"{P}.httpx.AsyncClient", return_value=self.client))
        return self

    def last_event(self) -> dict:
        return self.persist.call_args.kwargs


def _req(params: dict | None = None, tool: str = "get_repo") -> ToolCallRequest:
    return ToolCallRequest(server_name="github", tool_name=tool, params=params or {})


# ── Cache scoping ─────────────────────────────────────────────────────────────


class TestCacheScoping:
    @pytest.mark.asyncio
    async def test_placeholder_args_scope_cache_to_agent(self):
        h = Harness()
        h.server.cache_enabled = True
        get_cached = AsyncMock(return_value=None)
        store_cached = AsyncMock()
        with ExitStack() as stack:
            h.enter(stack)
            stack.enter_context(patch.object(h.svc._cache, "get_cached", new=get_cached))
            stack.enter_context(patch.object(h.svc._cache, "store_cached", new=store_cached))
            await h.svc.forward_tool_call(_req({"token": "{{GITHUB_PAT}}"}), h.agent)

        assert get_cached.call_args.kwargs["agent_id"] == h.agent.id
        assert store_cached.call_args.kwargs["agent_id"] == h.agent.id
        # Stored under the pre-injection args, never the resolved secret.
        assert store_cached.call_args.kwargs["input_payload"] == {"token": "{{GITHUB_PAT}}"}

    @pytest.mark.asyncio
    async def test_nested_placeholder_also_scopes_to_agent(self):
        h = Harness()
        h.server.cache_enabled = True
        get_cached = AsyncMock(return_value=None)
        with ExitStack() as stack:
            h.enter(stack)
            stack.enter_context(patch.object(h.svc._cache, "get_cached", new=get_cached))
            stack.enter_context(patch.object(h.svc._cache, "store_cached", new=AsyncMock()))
            await h.svc.forward_tool_call(
                _req({"auth": {"header": "Bearer {{vault:API_KEY}}"}}), h.agent
            )
        assert get_cached.call_args.kwargs["agent_id"] == h.agent.id

    @pytest.mark.asyncio
    async def test_plain_args_stay_org_shared(self):
        h = Harness()
        h.server.cache_enabled = True
        get_cached = AsyncMock(return_value=None)
        store_cached = AsyncMock()
        with ExitStack() as stack:
            h.enter(stack)
            stack.enter_context(patch.object(h.svc._cache, "get_cached", new=get_cached))
            stack.enter_context(patch.object(h.svc._cache, "store_cached", new=store_cached))
            await h.svc.forward_tool_call(_req({"repo": "acme/api"}), h.agent)

        assert get_cached.call_args.kwargs["agent_id"] is None
        assert store_cached.call_args.kwargs["agent_id"] is None

    @pytest.mark.asyncio
    async def test_upstream_is_error_result_not_cached(self):
        error_result = {"content": [{"type": "text", "text": "rate limited"}], "isError": True}
        h = Harness(client=_Client([_ok(error_result)]))
        h.server.cache_enabled = True
        store_cached = AsyncMock()
        with ExitStack() as stack:
            h.enter(stack)
            stack.enter_context(
                patch.object(h.svc._cache, "get_cached", new=AsyncMock(return_value=None))
            )
            stack.enter_context(patch.object(h.svc._cache, "store_cached", new=store_cached))
            resp = await h.svc.forward_tool_call(_req({"repo": "acme/api"}), h.agent)

        store_cached.assert_not_called()
        assert resp.result == error_result  # still returned to the caller

    @pytest.mark.asyncio
    async def test_successful_result_is_cached(self):
        h = Harness()
        h.server.cache_enabled = True
        store_cached = AsyncMock()
        with ExitStack() as stack:
            h.enter(stack)
            stack.enter_context(
                patch.object(h.svc._cache, "get_cached", new=AsyncMock(return_value=None))
            )
            stack.enter_context(patch.object(h.svc._cache, "store_cached", new=store_cached))
            await h.svc.forward_tool_call(_req({"repo": "acme/api"}), h.agent)
        store_cached.assert_awaited_once()


# ── Retry safety ──────────────────────────────────────────────────────────────


class TestRetrySafety:
    @pytest.mark.asyncio
    async def test_read_timeout_not_retried_for_unannotated_tool(self):
        client = _Client([httpx.ReadTimeout("slow")])
        h = Harness(client=client)
        with ExitStack() as stack:
            h.enter(stack)
            with pytest.raises(HTTPException) as exc:
                await h.svc.forward_tool_call(_req(tool="create_issue"), h.agent)
        assert exc.value.status_code == 502
        assert client.calls == 1
        assert "not retried" in h.last_event()["error"]

    @pytest.mark.asyncio
    async def test_read_timeout_not_retried_when_only_unapproved_change_claims_idempotent(self):
        server = _server(uuid.uuid4())
        pin = _pin(server, {"name": "create_issue"}, status="changed")
        pin.current_definition = {"name": "create_issue", "annotations": {"idempotentHint": True}}
        client = _Client([httpx.ReadTimeout("slow")])
        agent = _agent(org_id=server.org_id)
        h = Harness(agent=agent, server=server, pin=pin, client=client)
        with ExitStack() as stack:
            h.enter(stack)
            with pytest.raises(HTTPException):
                await h.svc.forward_tool_call(_req(tool="create_issue"), h.agent)
        assert client.calls == 1

    @pytest.mark.asyncio
    async def test_read_timeout_retried_for_read_only_tool(self):
        agent = _agent()
        server = _server(agent.org_id)
        pin = _pin(server, {"name": "get_repo", "annotations": {"readOnlyHint": True}})
        client = _Client([httpx.ReadTimeout("slow"), httpx.ReadTimeout("slow"), _ok()])
        h = Harness(agent=agent, server=server, pin=pin, client=client)
        with ExitStack() as stack:
            h.enter(stack)
            resp = await h.svc.forward_tool_call(_req(), h.agent)
        assert client.calls == 3
        assert resp.cache_hit is False

    @pytest.mark.asyncio
    async def test_pool_timeout_is_connect_phase_and_retried(self):
        client = _Client([httpx.PoolTimeout("pool")])
        h = Harness(client=client)
        with ExitStack() as stack:
            h.enter(stack)
            with pytest.raises(HTTPException) as exc:
                await h.svc.forward_tool_call(_req(tool="create_issue"), h.agent)
        assert exc.value.status_code == 502
        assert client.calls == _MAX_RETRIES + 1
        assert "unreachable" in h.last_event()["error"]


# ── Tool-definition pinning at call time ─────────────────────────────────────


class TestChangedToolPolicy:
    @pytest.mark.asyncio
    async def test_block_policy_rejects_and_audits(self):
        agent = _agent()
        server = _server(agent.org_id)
        pin = _pin(server, {"name": "get_repo"}, status="changed")
        client = _Client([_ok()])
        h = Harness(agent=agent, server=server, org=_org("block"), pin=pin, client=client)
        with ExitStack() as stack:
            h.enter(stack)
            with pytest.raises(HTTPException) as exc:
                await h.svc.forward_tool_call(_req(), h.agent)
        assert exc.value.status_code == 403
        assert "pending re-approval" in exc.value.detail
        assert client.calls == 0
        assert h.last_event()["count_usage"] is False
        assert "pending re-approval" in h.last_event()["error"]

    @pytest.mark.asyncio
    async def test_server_block_overrides_org_allow(self):
        agent = _agent()
        server = _server(agent.org_id, tool_change_policy="block")
        pin = _pin(server, {"name": "get_repo"}, status="changed")
        h = Harness(agent=agent, server=server, org=_org("allow"), pin=pin)
        with ExitStack() as stack:
            h.enter(stack)
            with pytest.raises(HTTPException) as exc:
                await h.svc.forward_tool_call(_req(), h.agent)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_allow_policy_proceeds(self):
        agent = _agent()
        server = _server(agent.org_id)
        pin = _pin(server, {"name": "get_repo"}, status="changed")
        client = _Client([_ok()])
        h = Harness(agent=agent, server=server, org=_org("allow"), pin=pin, client=client)
        with ExitStack() as stack:
            h.enter(stack)
            resp = await h.svc.forward_tool_call(_req(), h.agent)
        assert client.calls == 1
        assert resp.tool_name == "get_repo"


class TestFetchToolsListPins:
    def _tools_client(self, tools):
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {}
        resp.json.return_value = {"result": {"tools": tools}}
        return _Client([resp])

    @pytest.mark.asyncio
    async def test_tools_list_records_definitions(self):
        svc = ProxyService(AsyncMock(), AsyncMock())
        server = _server(uuid.uuid4())
        tools = [{"name": "get_repo", "description": "Read a repo"}]
        record = AsyncMock(return_value=[])
        with (
            patch.object(svc._pins, "record_tools", new=record),
            patch(f"{P}.assert_ssrf_safe", new=AsyncMock()),
            patch(f"{P}.httpx.AsyncClient", return_value=self._tools_client(tools)),
        ):
            result = await svc.fetch_tools_list(server)
        assert result == tools
        record.assert_awaited_once_with(server, tools)

    @pytest.mark.asyncio
    async def test_pinning_failure_never_fails_the_listing(self):
        db = AsyncMock()
        svc = ProxyService(db, AsyncMock())
        server = _server(uuid.uuid4())
        tools = [{"name": "get_repo"}]
        with (
            patch.object(svc._pins, "record_tools", new=AsyncMock(side_effect=RuntimeError("db"))),
            patch(f"{P}.assert_ssrf_safe", new=AsyncMock()),
            patch(f"{P}.httpx.AsyncClient", return_value=self._tools_client(tools)),
        ):
            result = await svc.fetch_tools_list(server)
        assert result == tools
        db.rollback.assert_awaited()


# ── Audit gaps ────────────────────────────────────────────────────────────────


def _assert_rejection_audited(h: Harness, fragment: str) -> None:
    kwargs = h.last_event()
    assert kwargs["count_usage"] is False
    assert kwargs["cache_hit"] is False
    assert kwargs["response_payload"] is None
    assert fragment in kwargs["error"]
    assert h.client.calls == 0


class TestRejectionsAreAudited:
    @pytest.mark.asyncio
    async def test_scope_rejection(self):
        h = Harness(agent=_agent(scope="vault_read_only"))
        with ExitStack() as stack:
            h.enter(stack)
            with pytest.raises(HTTPException) as exc:
                await h.svc.forward_tool_call(_req(), h.agent)
        assert exc.value.status_code == 403
        _assert_rejection_audited(h, "vault_read_only")

    @pytest.mark.asyncio
    async def test_per_tool_rate_limit(self):
        h = Harness()
        h.redis.incr = AsyncMock(return_value=6)
        with ExitStack() as stack:
            h.enter(stack)
            stack.enter_context(
                patch.object(h.svc._rbac, "get_rate_limit", new=AsyncMock(return_value=5))
            )
            with pytest.raises(HTTPException) as exc:
                await h.svc.forward_tool_call(_req(), h.agent)
        assert exc.value.status_code == 429
        _assert_rejection_audited(h, "Rate limit exceeded")

    @pytest.mark.asyncio
    async def test_agent_rate_limit(self):
        h = Harness(agent=_agent(rate_limit_per_minute=3))
        h.redis.incr = AsyncMock(return_value=4)
        with ExitStack() as stack:
            h.enter(stack)
            with pytest.raises(HTTPException) as exc:
                await h.svc.forward_tool_call(_req(), h.agent)
        assert exc.value.status_code == 429
        _assert_rejection_audited(h, "Agent rate limit exceeded")

    @pytest.mark.asyncio
    async def test_quota_exceeded(self):
        h = Harness()
        h.quota.side_effect = QuotaExceededError(
            resource="tool_calls", used=1000, limit=1000, resets_at=datetime.now(tz=UTC)
        )
        with ExitStack() as stack:
            h.enter(stack)
            with pytest.raises(QuotaExceededError):
                await h.svc.forward_tool_call(_req(), h.agent)
        _assert_rejection_audited(h, "1000")
        assert h.webhook.call_args.args[1] == "quota.exceeded"

    @pytest.mark.asyncio
    async def test_session_budget_exceeded(self):
        h = Harness(agent=_agent(max_calls_per_session=2))
        h.redis.incr = AsyncMock(return_value=3)
        with ExitStack() as stack:
            h.enter(stack)
            with pytest.raises(SessionBudgetExceededError):
                await h.svc.forward_tool_call(_req(), h.agent)
        _assert_rejection_audited(h, "3")

    @pytest.mark.asyncio
    async def test_unresolvable_placeholder_is_400_and_audited(self):
        h = Harness()
        with ExitStack() as stack:
            h.enter(stack, real_intercept=True)
            stack.enter_context(
                patch.object(
                    h.svc._vault, "get_secret", new=AsyncMock(side_effect=KeyError("missing"))
                )
            )
            with pytest.raises(HTTPException) as exc:
                await h.svc.forward_tool_call(_req({"token": "{{NOPE}}"}), h.agent)
        assert exc.value.status_code == 400
        assert "NOPE" in exc.value.detail
        _assert_rejection_audited(h, "could not be resolved")
        # Audit stores the placeholder form of the args, never a secret.
        assert h.last_event()["request_payload"] == {"token": "{{NOPE}}"}

    @pytest.mark.asyncio
    async def test_missing_server_header_secret_is_502_and_audited(self):
        agent = _agent()
        server = _server(agent.org_id, headers={"Authorization": "Bearer {{vault:GH_TOKEN}}"})
        h = Harness(agent=agent, server=server)
        with ExitStack() as stack:
            h.enter(stack)
            stack.enter_context(
                patch.object(
                    h.svc._vault, "get_secret", new=AsyncMock(side_effect=KeyError("missing"))
                )
            )
            with pytest.raises(HTTPException) as exc:
                await h.svc.forward_tool_call(_req(), h.agent)
        assert exc.value.status_code == 502
        _assert_rejection_audited(h, "Authorization")

    @pytest.mark.asyncio
    async def test_audit_failure_does_not_mask_rejection(self):
        h = Harness(agent=_agent(rate_limit_per_minute=1))
        h.redis.incr = AsyncMock(return_value=2)
        h.persist.side_effect = RuntimeError("db down")
        with ExitStack() as stack:
            h.enter(stack)
            with pytest.raises(HTTPException) as exc:
                await h.svc.forward_tool_call(_req(), h.agent)
        assert exc.value.status_code == 429


class TestPersistEventCountUsage:
    @pytest.mark.asyncio
    async def test_rejection_event_skips_usage_and_cost(self):
        db = AsyncMock()
        db.add = MagicMock()
        svc = ProxyService(db, AsyncMock())
        server = _server(uuid.uuid4(), cost_per_call_usd=0.01)
        session = MagicMock(id=uuid.uuid4(), org_id=server.org_id)
        await svc._persist_event(
            session=session,
            mcp_server=server,
            tool_name="get_repo",
            request_payload={},
            response_payload=None,
            cache_hit=False,
            duration_ms=1,
            error="Rate limit exceeded",
            count_usage=False,
        )
        db.execute.assert_not_called()  # no usage_events upsert
        event = db.add.call_args.args[0]
        assert event.cost_usd is None
        assert event.error == "Rate limit exceeded"

    @pytest.mark.asyncio
    async def test_normal_event_still_counts_usage(self):
        db = AsyncMock()
        db.add = MagicMock()
        svc = ProxyService(db, AsyncMock())
        server = _server(uuid.uuid4(), cost_per_call_usd=0.01)
        session = MagicMock(id=uuid.uuid4(), org_id=server.org_id)
        await svc._persist_event(
            session=session,
            mcp_server=server,
            tool_name="get_repo",
            request_payload={},
            response_payload={},
            cache_hit=False,
            duration_ms=1,
            error=None,
        )
        db.execute.assert_awaited_once()
        assert db.add.call_args.args[0].cost_usd == pytest.approx(0.01)
