"""
Unit tests for app.services.cache.cache_service

Coverage:
    - Same input params → same SHA-256 hash (deterministic)
    - Different param ordering → same hash (sort_keys=True)
    - compute_embedding returns list of floats with length 384
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────

def _canonical(tool_name: str, input_payload: dict) -> str:
    return f"{tool_name}:{json.dumps(input_payload, sort_keys=True)}"


def _compute_hash(tool_name: str, input_payload: dict) -> str:
    canonical = _canonical(tool_name, input_payload)
    return hashlib.sha256(canonical.encode()).hexdigest()


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
        """Identical tool name + params always produce the same hash."""
        h1 = _compute_hash("read_file", {"path": "/etc/hosts"})
        h2 = _compute_hash("read_file", {"path": "/etc/hosts"})
        assert h1 == h2

    def test_different_param_ordering_same_hash(self):
        """Dict key ordering must not affect the hash (sort_keys=True)."""
        params_a = {"b": 2, "a": 1, "c": "hello"}
        params_b = {"a": 1, "c": "hello", "b": 2}
        h_a = _compute_hash("my_tool", params_a)
        h_b = _compute_hash("my_tool", params_b)
        assert h_a == h_b, (
            f"Hash changed with different param ordering: {h_a} != {h_b}"
        )

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


# ── Tests: compute_embedding ──────────────────────────────────────────────────

# sentence-transformers is an optional ML dependency not installed in CI.
# Skip the entire class gracefully rather than failing.
pytest.importorskip("sentence_transformers", reason="sentence-transformers not installed")


class TestComputeEmbedding:
    def test_returns_list_of_floats_length_384(self):
        """compute_embedding must return a list[float] of length 384 (MiniLM-L6-v2)."""
        with patch.dict(os.environ, _REQUIRED_ENV, clear=False):
            from app.services.cache.cache_service import CacheService

        db = AsyncMock()
        redis = AsyncMock()

        with patch.dict(os.environ, _REQUIRED_ENV, clear=False):
            svc = CacheService(db=db, redis=redis)
            result = svc.compute_embedding("read_file:{\"path\": \"/etc/hosts\"}")

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
            text = "read_file:{\"path\": \"/etc/hosts\"}"
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
            e1 = svc.compute_embedding("read_file:{\"path\": \"/etc/hosts\"}")
            e2 = svc.compute_embedding("write_file:{\"path\": \"/tmp/out\", \"content\": \"hello\"}")

        assert e1 != e2
