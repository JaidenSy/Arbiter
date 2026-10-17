"""
Unit tests for agent-scoped cache entries (cross-agent secret leak fix).

The cache key is computed over pre-injection args, so ``{{GITHUB_PAT}}`` is
identical for every agent even when it resolves to a different agent-scoped
secret.  Entries stored with ``agent_id`` must only ever be served back to
that agent, in all three tiers (Redis L1, Postgres exact, pgvector semantic).

Coverage:
    - agent_id changes the exact hash; agent_id=None keeps the legacy hash
    - Redis L1: agent B never sees agent A's entry; org-shared entries are
      not served to agent-scoped lookups
    - Postgres exact and semantic queries filter on agent_id (= :id / IS NULL)
    - store_cached persists agent_id on new rows and filters the upsert lookup
"""

from __future__ import annotations

import hashlib
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from app.services.cache.cache_service import CacheService, _canonical, _exact_hash

ORG = uuid.UUID("11111111-0000-0000-0000-000000000001")
SERVER = uuid.UUID("22222222-0000-0000-0000-000000000001")
AGENT_A = uuid.UUID("33333333-0000-0000-0000-00000000000a")
AGENT_B = uuid.UUID("33333333-0000-0000-0000-00000000000b")

PARAMS = {"token": "{{GITHUB_PAT}}", "repo": "acme/api"}


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def _service(fake_redis, captured: list) -> CacheService:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None

    async def execute(stmt):
        captured.append(stmt)
        return result

    db.execute = execute
    db.add = MagicMock()
    return CacheService(db=db, redis=fake_redis)


class TestAgentScopedHash:
    def test_agent_id_changes_hash(self):
        canonical = _canonical("get_repo", PARAMS)
        shared = _exact_hash(ORG, SERVER, canonical)
        a = _exact_hash(ORG, SERVER, canonical, AGENT_A)
        b = _exact_hash(ORG, SERVER, canonical, AGENT_B)
        assert len({shared, a, b}) == 3

    def test_org_shared_hash_is_unchanged_format(self):
        """agent_id=None must keep the pre-existing hash so live entries stay valid."""
        canonical = _canonical("get_repo", PARAMS)
        legacy = hashlib.sha256(f"{ORG}:{SERVER}:{canonical}".encode()).hexdigest()
        assert _exact_hash(ORG, SERVER, canonical) == legacy
        assert _exact_hash(ORG, SERVER, canonical, None) == legacy


class TestRedisTierIsolation:
    @pytest.mark.asyncio
    async def test_agent_b_never_sees_agent_a_entry(self, fake_redis):
        captured: list = []
        svc = _service(fake_redis, captured)
        await svc.store_cached(
            "get_repo",
            PARAMS,
            {"content": [{"type": "text", "text": "private to A"}]},
            org_id=ORG,
            mcp_server_id=SERVER,
            semantic=False,
            agent_id=AGENT_A,
        )

        hit_a = await svc.get_cached(
            "get_repo", PARAMS, org_id=ORG, mcp_server_id=SERVER, semantic=False, agent_id=AGENT_A
        )
        hit_b = await svc.get_cached(
            "get_repo", PARAMS, org_id=ORG, mcp_server_id=SERVER, semantic=False, agent_id=AGENT_B
        )
        hit_shared = await svc.get_cached(
            "get_repo", PARAMS, org_id=ORG, mcp_server_id=SERVER, semantic=False
        )

        assert hit_a == {"content": [{"type": "text", "text": "private to A"}]}
        assert hit_b is None
        assert hit_shared is None

    @pytest.mark.asyncio
    async def test_org_shared_entry_not_served_to_agent_scoped_lookup(self, fake_redis):
        captured: list = []
        svc = _service(fake_redis, captured)
        await svc.store_cached(
            "get_repo", PARAMS, {"shared": True}, org_id=ORG, mcp_server_id=SERVER, semantic=False
        )
        assert (
            await svc.get_cached(
                "get_repo",
                PARAMS,
                org_id=ORG,
                mcp_server_id=SERVER,
                semantic=False,
                agent_id=AGENT_A,
            )
            is None
        )


class TestPostgresTierFilters:
    @pytest.mark.asyncio
    async def test_exact_query_filters_by_agent(self, fake_redis):
        captured: list = []
        svc = _service(fake_redis, captured)
        await svc.get_cached(
            "get_repo", PARAMS, org_id=ORG, mcp_server_id=SERVER, semantic=False, agent_id=AGENT_A
        )
        assert "cache_entries.agent_id = " in _sql(captured[0])

    @pytest.mark.asyncio
    async def test_exact_query_for_shared_lookup_requires_null_agent(self, fake_redis):
        captured: list = []
        svc = _service(fake_redis, captured)
        await svc.get_cached("get_repo", PARAMS, org_id=ORG, mcp_server_id=SERVER, semantic=False)
        assert "cache_entries.agent_id IS NULL" in _sql(captured[0])

    @pytest.mark.asyncio
    async def test_semantic_query_filters_by_agent(self, fake_redis):
        captured: list = []
        svc = _service(fake_redis, captured)
        with patch.object(
            CacheService, "_compute_embedding_async", new=AsyncMock(return_value=[0.0] * 384)
        ):
            await svc.get_cached(
                "get_repo",
                PARAMS,
                org_id=ORG,
                mcp_server_id=SERVER,
                semantic=True,
                agent_id=AGENT_B,
            )
        assert len(captured) == 2  # exact miss, then semantic
        semantic_sql = _sql(captured[1])
        assert "<=>" in semantic_sql
        assert "cache_entries.agent_id = " in semantic_sql

    @pytest.mark.asyncio
    async def test_semantic_query_for_shared_lookup_requires_null_agent(self, fake_redis):
        captured: list = []
        svc = _service(fake_redis, captured)
        with patch.object(
            CacheService, "_compute_embedding_async", new=AsyncMock(return_value=[0.0] * 384)
        ):
            await svc.get_cached(
                "get_repo", {"repo": "acme/api"}, org_id=ORG, mcp_server_id=SERVER, semantic=True
            )
        assert "cache_entries.agent_id IS NULL" in _sql(captured[1])

    @pytest.mark.asyncio
    async def test_store_persists_agent_id_and_filters_upsert(self, fake_redis):
        captured: list = []
        svc = _service(fake_redis, captured)
        await svc.store_cached(
            "get_repo",
            PARAMS,
            {"ok": True},
            org_id=ORG,
            mcp_server_id=SERVER,
            semantic=False,
            agent_id=AGENT_A,
        )
        assert "cache_entries.agent_id = " in _sql(captured[0])
        added = svc.db.add.call_args.args[0]
        assert added.agent_id == AGENT_A
        assert added.input_hash == _exact_hash(ORG, SERVER, _canonical("get_repo", PARAMS), AGENT_A)
        # Redis value is the response, not leaked elsewhere.
        keys = [k async for k in fake_redis.scan_iter("cache:exact:*")]
        assert len(keys) == 1
        assert json.loads(await fake_redis.get(keys[0])) == {"ok": True}
