"""
Unit tests for app.services.cache.cache_service

Coverage:
    - Same input params → same SHA-256 hash (deterministic)
    - Different param ordering → same hash (sort_keys=True)
    - Hash is scoped by org id and MCP server id (no cross-tenant /
      cross-server collisions)
    - Exact-match lookups never return another server's cached entry
    - compute_embedding returns list of floats with length 384
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────

# Fixed scope constants so hash-determinism tests stay deterministic.
ORG_A = uuid.UUID("11111111-0000-0000-0000-000000000001")
ORG_B = uuid.UUID("11111111-0000-0000-0000-000000000002")
SERVER_A = uuid.UUID("22222222-0000-0000-0000-000000000001")
SERVER_B = uuid.UUID("22222222-0000-0000-0000-000000000002")


def _canonical(tool_name: str, input_payload: dict) -> str:
    return f"{tool_name}:{json.dumps(input_payload, sort_keys=True)}"


def _compute_hash(
    tool_name: str,
    input_payload: dict,
    org_id: Any = ORG_A,
    mcp_server_id: Any = SERVER_A,
) -> str:
    canonical = _canonical(tool_name, input_payload)
    return hashlib.sha256(f"{org_id}:{mcp_server_id}:{canonical}".encode()).hexdigest()


# We need settings to be importable; patch required env vars before importing.
_REQUIRED_ENV = {
    "APP_SECRET_KEY": "test-secret-key-1234567890abcdef",
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
    "REDIS_URL": "redis://localhost:6379/0",
    "VAULT_ENCRYPTION_KEY": "a" * 64,
}


# ── Tests: hash determinism ───────────────────────────────────────────────────


class TestCacheHashDeterminism:
    """
    Tests for the canonical hash used as the cache key.
    These tests exercise the same logic as CacheService.get_cached / store_cached
    without needing a live DB or Redis.
    """

    def test_same_params_same_hash(self):
        """Identical scope + tool name + params always produce the same hash."""
        h1 = _compute_hash("read_file", {"path": "/etc/hosts"})
        h2 = _compute_hash("read_file", {"path": "/etc/hosts"})
        assert h1 == h2

    def test_different_param_ordering_same_hash(self):
        """Dict key ordering must not affect the hash (sort_keys=True)."""
        params_a = {"b": 2, "a": 1, "c": "hello"}
        params_b = {"a": 1, "c": "hello", "b": 2}
        h_a = _compute_hash("my_tool", params_a)
        h_b = _compute_hash("my_tool", params_b)
        assert h_a == h_b, f"Hash changed with different param ordering: {h_a} != {h_b}"

    def test_different_tools_different_hash(self):
        h1 = _compute_hash("tool_a", {"x": 1})
        h2 = _compute_hash("tool_b", {"x": 1})
        assert h1 != h2

    def test_different_params_different_hash(self):
        h1 = _compute_hash("read_file", {"path": "/etc/hosts"})
        h2 = _compute_hash("read_file", {"path": "/etc/passwd"})
        assert h1 != h2

    def test_hash_is_64_hex_chars(self):
        h = _compute_hash("tool", {"k": "v"})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_nested_params_deterministic(self):
        params = {"outer": {"inner_b": 2, "inner_a": 1}, "top": "val"}
        h1 = _compute_hash("complex_tool", params)
        h2 = _compute_hash("complex_tool", params)
        assert h1 == h2

    def test_empty_params_consistent(self):
        h1 = _compute_hash("tool", {})
        h2 = _compute_hash("tool", {})
        assert h1 == h2


# ── Tests: tenant and server scoping ──────────────────────────────────────────


class TestCacheHashScoping:
    """
    Two MCP servers in the same org may expose tools with identical names
    ("search", "query", ...).  The exact-match hash must fold in both the org
    id and the server id so entries never collide across those boundaries.
    """

    def test_same_call_different_servers_different_hash(self):
        h_a = _compute_hash("search", {"q": "x"}, org_id=ORG_A, mcp_server_id=SERVER_A)
        h_b = _compute_hash("search", {"q": "x"}, org_id=ORG_A, mcp_server_id=SERVER_B)
        assert h_a != h_b, "Cache hash must not collide across MCP servers"

    def test_same_call_different_orgs_different_hash(self):
        h_a = _compute_hash("search", {"q": "x"}, org_id=ORG_A, mcp_server_id=SERVER_A)
        h_b = _compute_hash("search", {"q": "x"}, org_id=ORG_B, mcp_server_id=SERVER_A)
        assert h_a != h_b, "Cache hash must not collide across orgs"

    def test_service_hash_matches_test_helper(self):
        """The service's _exact_hash must agree with the helper used above."""
        with patch.dict(os.environ, _REQUIRED_ENV, clear=False):
            from app.services.cache.cache_service import _canonical as svc_canonical
            from app.services.cache.cache_service import _exact_hash as svc_exact_hash

        canonical = svc_canonical("search", {"q": "x"})
        assert svc_exact_hash(ORG_A, SERVER_A, canonical) == _compute_hash(
            "search", {"q": "x"}, org_id=ORG_A, mcp_server_id=SERVER_A
        )


class TestCacheServerIsolation:
    """
    Behavioral regression test for the cross-server cache poisoning bug:
    a response stored for server A must never be served for server B, even
    for an identical tool name and identical arguments.
    """

    @staticmethod
    def _make_service(fake_redis) -> Any:
        with patch.dict(os.environ, _REQUIRED_ENV, clear=False):
            from app.services.cache.cache_service import CacheService

        db = AsyncMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None  # Postgres always misses
        db.execute = AsyncMock(return_value=exec_result)
        db.add = MagicMock()
        return CacheService(db=db, redis=fake_redis)

    async def test_exact_hit_does_not_cross_servers(self, fake_redis):
        svc = self._make_service(fake_redis)

        await svc.store_cached(
            tool_name="search",
            input_payload={"q": "x"},
            response_payload={"answer": "from-server-a"},
            org_id=ORG_A,
            mcp_server_id=SERVER_A,
            semantic=False,
        )

        hit_same_server = await svc.get_cached(
            "search", {"q": "x"}, org_id=ORG_A, mcp_server_id=SERVER_A, semantic=False
        )
        assert hit_same_server == {"answer": "from-server-a"}

        miss_other_server = await svc.get_cached(
            "search", {"q": "x"}, org_id=ORG_A, mcp_server_id=SERVER_B, semantic=False
        )
        assert miss_other_server is None, "Cache entry stored for server A was served for server B"

    async def test_exact_hit_does_not_cross_orgs(self, fake_redis):
        svc = self._make_service(fake_redis)

        await svc.store_cached(
            tool_name="search",
            input_payload={"q": "x"},
            response_payload={"answer": "from-org-a"},
            org_id=ORG_A,
            mcp_server_id=SERVER_A,
            semantic=False,
        )

        miss_other_org = await svc.get_cached(
            "search", {"q": "x"}, org_id=ORG_B, mcp_server_id=SERVER_A, semantic=False
        )
        assert miss_other_org is None, "Cache entry stored for org A was served for org B"


# ── Tests: compute_embedding ──────────────────────────────────────────────────

# sentence-transformers is an optional ML dependency not installed in CI.
# Skip only the embedding tests (a module-level importorskip would skip the
# hash and isolation tests above as well).
_HAS_SENTENCE_TRANSFORMERS = importlib.util.find_spec("sentence_transformers") is not None


@pytest.mark.skipif(not _HAS_SENTENCE_TRANSFORMERS, reason="sentence-transformers not installed")
class TestComputeEmbedding:
    def test_returns_list_of_floats_length_384(self):
        """compute_embedding must return a list[float] of length 384 (MiniLM-L6-v2)."""
        with patch.dict(os.environ, _REQUIRED_ENV, clear=False):
            from app.services.cache.cache_service import CacheService

        db = AsyncMock()
        redis = AsyncMock()

        with patch.dict(os.environ, _REQUIRED_ENV, clear=False):
            svc = CacheService(db=db, redis=redis)
            result = svc.compute_embedding('read_file:{"path": "/etc/hosts"}')

        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert len(result) == 384, f"Expected 384-dim embedding, got {len(result)}"
        assert all(isinstance(x, float) for x in result), "Embedding values must be floats"

    def test_same_input_same_embedding(self):
        """Embedding is deterministic for the same input text."""
        with patch.dict(os.environ, _REQUIRED_ENV, clear=False):
            from app.services.cache.cache_service import CacheService

        db = AsyncMock()
        redis = AsyncMock()

        with patch.dict(os.environ, _REQUIRED_ENV, clear=False):
            svc = CacheService(db=db, redis=redis)
            text = 'read_file:{"path": "/etc/hosts"}'
            e1 = svc.compute_embedding(text)
            e2 = svc.compute_embedding(text)

        assert e1 == e2, "compute_embedding is not deterministic"

    def test_different_inputs_different_embeddings(self):
        """Different texts should produce different embeddings."""
        with patch.dict(os.environ, _REQUIRED_ENV, clear=False):
            from app.services.cache.cache_service import CacheService

        db = AsyncMock()
        redis = AsyncMock()

        with patch.dict(os.environ, _REQUIRED_ENV, clear=False):
            svc = CacheService(db=db, redis=redis)
            e1 = svc.compute_embedding('read_file:{"path": "/etc/hosts"}')
            e2 = svc.compute_embedding('write_file:{"path": "/tmp/out", "content": "hello"}')

        assert e1 != e2
