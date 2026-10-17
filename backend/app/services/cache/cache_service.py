# Copyright 2026 Jaiden Sy
# SPDX-License-Identifier: Apache-2.0
"""
Arbiter CacheService.

Implements a two-phase semantic cache for MCP tool calls:

    Phase 1: Exact match:
        SHA-256 hash of org id + MCP server id + the canonical (sorted-key)
        JSON of the input.  O(1) lookup in Redis (and Postgres fallback).

    Phase 2: Semantic match:
        sentence-transformers/all-MiniLM-L6-v2 embedding of the input.
        pgvector cosine-distance ANN search (single SQL query, no Python loop).
        Threshold controlled by CACHE_SIMILARITY_THRESHOLD env var (default 0.95).

Scoping: every lookup and store is keyed by (org_id, mcp_server_id).  Two
servers in the same org may expose tools with identical names ("search",
"query", ...); without the server id in the key, one server's cached response
would be served for the other server's call.

Agent scoping: the key is computed over the *pre-injection* arguments, so a
``{{SECRET}}`` placeholder looks identical for every agent even when it
resolves to a different, agent-scoped secret.  Callers pass ``agent_id`` for
such calls (ProxyService does so whenever the arguments reference any vault
placeholder) and the entry is then private to that agent in all three tiers:
the Redis key, the Postgres exact match and the pgvector semantic search.
``agent_id=None`` keeps the entry org-shared, and the hash for that case is
unchanged so existing org-shared entries stay valid.

Design decisions:
    - Embeddings stored as vector(384) using pgvector; cosine distance (<=>)
      is computed in Postgres, replacing the previous O(n) Python loop.
    - Redis is used as an L1 exact-hash cache to avoid hitting Postgres on
      every repeated identical call.
    - Embedding computation is synchronous (CPU-bound); model is a module-level
      singleton loaded once at startup.
    - Semantic search runs only on cache miss to avoid embedding overhead on
      common exact-match cases.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.cache import CacheEntry

logger = logging.getLogger(__name__)

# ── Embedding model singleton ─────────────────────────────────────────────────
# Loaded lazily on first call to compute_embedding(); avoids import-time
# download and allows the app to start even if the model is not cached yet.

_embedding_model = None


def _get_model():
    """Return the cached sentence-transformer model, loading it on first call."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            _embedding_model = SentenceTransformer(settings.cache_embedding_model)
            logger.info("cache: loaded embedding model %r", settings.cache_embedding_model)
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for semantic caching. "
                "Run: pip install sentence-transformers"
            ) from exc
    return _embedding_model


def _canonical(tool_name: str, input_payload: dict[str, Any]) -> str:
    """Return the canonical string embedded for semantic lookups."""
    return f"{tool_name}:{json.dumps(input_payload, sort_keys=True)}"


def _exact_hash(org_id: Any, mcp_server_id: Any, canonical: str, agent_id: Any = None) -> str:
    """
    SHA-256 over org id, MCP server id, optional agent id, and the canonical input.

    Folding the tenant and server into the hash guarantees exact-match keys
    never collide across orgs (uq_cache_entry_tool_hash spans all tenants)
    or across two servers that expose a tool with the same name.  When
    ``agent_id`` is set the entry is agent-private; when it is None the
    pre-existing org-shared hash format is kept.
    """
    if agent_id is None:
        return hashlib.sha256(f"{org_id}:{mcp_server_id}:{canonical}".encode()).hexdigest()
    return hashlib.sha256(
        f"{org_id}:{mcp_server_id}:agent:{agent_id}:{canonical}".encode()
    ).hexdigest()


def _redis_key(org_id: Any, mcp_server_id: Any, tool_name: str, input_hash: str) -> str:
    """Redis L1 key; the agent scope is already folded into ``input_hash``."""
    return f"cache:exact:{org_id}:{mcp_server_id}:{tool_name}:{input_hash}"


class CacheService:
    """
    Two-phase semantic cache backed by Redis (L1) and PostgreSQL (L2).
    """

    def __init__(self, db: AsyncSession, redis: Any) -> None:
        """
        Initialise with injected DB session and Redis client.

        Args:
            db:    Async SQLAlchemy session.
            redis: Async Redis client (redis.asyncio.Redis).
        """
        self.db = db
        self.redis = redis

    def compute_embedding(self, text: str) -> list[float]:
        """Synchronous embedding: call via _compute_embedding_async from async context."""
        model = _get_model()
        return model.encode(text).tolist()

    async def _compute_embedding_async(self, text: str) -> list[float]:
        """Offload CPU-bound embedding to thread pool to avoid blocking the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.compute_embedding, text)

    async def get_cached(
        self,
        tool_name: str,
        input_payload: dict[str, Any],
        org_id: Any = None,
        mcp_server_id: Any = None,
        semantic: bool = True,
        agent_id: Any = None,
    ) -> dict[str, Any] | None:
        """
        Attempt to retrieve a cached response for a tool call.

        Lookup order:
            1. Redis L1 cache (exact hash key): O(1), no DB hit
            2. Postgres exact-hash match: fallback if Redis miss
            3. Postgres semantic similarity match (embedding cosine search): Pro/Enterprise only

        Args:
            tool_name:     Name of the MCP tool being called.
            input_payload: The tool call arguments dict.
            org_id:        Organization UUID for tenant isolation.
            mcp_server_id: MCP server UUID: entries never cross server boundaries.
            semantic:      When False, skip embedding and pgvector search (free tier).
            agent_id:      Set for calls whose result may depend on agent-scoped
                           secrets: only that agent's entries can match.  None
                           matches org-shared entries only.
        """
        canonical = _canonical(tool_name, input_payload)
        input_hash = _exact_hash(org_id, mcp_server_id, canonical, agent_id)
        redis_key = _redis_key(org_id, mcp_server_id, tool_name, input_hash)

        # ── Phase 1a: Redis exact match ────────────────────────────────────────
        if self.redis is not None:
            cached_bytes = await self.redis.get(redis_key)
            if cached_bytes is not None:
                logger.debug("cache: L1 Redis hit tool=%r hash=%s", tool_name, input_hash[:8])
                try:
                    return json.loads(cached_bytes)
                except json.JSONDecodeError:
                    logger.warning("cache: Redis value for %s was not valid JSON", redis_key)

        # ── Phase 1b: Postgres exact match ────────────────────────────────────
        now = datetime.now(tz=UTC)
        result = await self.db.execute(
            select(CacheEntry).where(
                CacheEntry.tool_name == tool_name,
                CacheEntry.input_hash == input_hash,
                CacheEntry.org_id == org_id,
                CacheEntry.mcp_server_id == mcp_server_id,
                CacheEntry.agent_id == agent_id,  # None compiles to IS NULL
                CacheEntry.expires_at > now,
            )
        )
        entry = result.scalar_one_or_none()
        if entry is not None:
            logger.debug("cache: L2 Postgres exact hit tool=%r", tool_name)
            # Backfill Redis with remaining TTL.
            if self.redis is not None:
                remaining_ttl = int((entry.expires_at.replace(tzinfo=UTC) - now).total_seconds())
                if remaining_ttl > 0:
                    await self.redis.setex(
                        redis_key,
                        remaining_ttl,
                        json.dumps(entry.response_payload),
                    )
            await self._increment_hit_count(entry.id)
            return entry.response_payload

        # ── Phase 2: pgvector ANN cosine-distance search (Pro/Enterprise only) ──
        if not semantic:
            logger.debug(
                "cache: miss tool=%r (semantic search not available on free tier)", tool_name
            )
            return None

        try:
            query_embedding = await self._compute_embedding_async(canonical)
        except Exception as exc:
            logger.warning("cache: embedding failed, skipping semantic search: %s", exc)
            return None

        # cosine_distance = 1 - cosine_similarity; similarity >= threshold means
        # distance <= 1 - threshold. pgvector's <=> operator returns cosine distance.
        threshold = settings.cache_similarity_threshold
        max_distance = 1.0 - threshold

        result = await self.db.execute(
            select(CacheEntry)
            .where(
                CacheEntry.tool_name == tool_name,
                CacheEntry.org_id == org_id,
                CacheEntry.mcp_server_id == mcp_server_id,
                # A near-match must never cross the agent boundary either.
                CacheEntry.agent_id == agent_id,
                CacheEntry.input_embedding.is_not(None),
                CacheEntry.expires_at > now,
                CacheEntry.input_embedding.op("<=>")(query_embedding) <= max_distance,
            )
            .order_by(CacheEntry.input_embedding.op("<=>")(query_embedding))
            .limit(1)
        )
        entry = result.scalar_one_or_none()
        if entry is not None:
            logger.debug("cache: L3 pgvector semantic hit tool=%r", tool_name)
            await self._increment_hit_count(entry.id)
            return entry.response_payload

        logger.debug("cache: miss tool=%r", tool_name)
        return None

    async def store_cached(
        self,
        tool_name: str,
        input_payload: dict[str, Any],
        response_payload: dict[str, Any],
        org_id: Any = None,
        mcp_server_id: Any = None,
        ttl_override: int | None = None,
        semantic: bool = True,
        agent_id: Any = None,
    ) -> None:
        """
        Store a tool call result in both Redis (L1) and Postgres (L2).

        Also computes and stores the input embedding for future semantic lookups.
        Existing entries with the same (tool_name, input_hash) are updated in-place
        (the result may have changed; refresh the entry and reset the TTL).

        Args:
            tool_name:        Name of the MCP tool.
            input_payload:    The tool call arguments dict.
            response_payload: The response from the MCP server.
            org_id:           Organization UUID for tenant isolation.
            mcp_server_id:    MCP server UUID: entries never cross server boundaries.
            agent_id:         Agent UUID for agent-private entries (see get_cached).
        """
        canonical = _canonical(tool_name, input_payload)
        input_hash = _exact_hash(org_id, mcp_server_id, canonical, agent_id)
        redis_key = _redis_key(org_id, mcp_server_id, tool_name, input_hash)
        ttl_seconds = ttl_override if ttl_override is not None else settings.cache_ttl_seconds
        expires_at = datetime.now(tz=UTC) + timedelta(seconds=ttl_seconds)

        # Compute embedding only for Pro/Enterprise: free tier uses exact-match only.
        embedding: list[float] | None = None
        if semantic:
            try:
                embedding = await self._compute_embedding_async(canonical)
            except Exception as exc:
                logger.warning("cache: embedding failed during store: %s", exc)

        # ── Write to Redis ─────────────────────────────────────────────────────
        if self.redis is not None:
            await self.redis.setex(
                redis_key,
                ttl_seconds,
                json.dumps(response_payload),
            )

        # ── Write to Postgres (upsert) ─────────────────────────────────────────
        now = datetime.now(tz=UTC)
        result = await self.db.execute(
            select(CacheEntry).where(
                CacheEntry.tool_name == tool_name,
                CacheEntry.input_hash == input_hash,
                CacheEntry.org_id == org_id,
                CacheEntry.mcp_server_id == mcp_server_id,
                CacheEntry.agent_id == agent_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.response_payload = response_payload
            existing.expires_at = expires_at
            if embedding is not None:
                existing.input_embedding = embedding
        else:
            entry = CacheEntry(
                tool_name=tool_name,
                input_hash=input_hash,
                input_embedding=embedding,
                response_payload=response_payload,
                expires_at=expires_at,
                org_id=org_id,
                mcp_server_id=mcp_server_id,
                agent_id=agent_id,
            )
            self.db.add(entry)

        await self.db.commit()
        logger.debug("cache: stored tool=%r hash=%s", tool_name, input_hash[:8])

    async def _increment_hit_count(self, entry_id) -> None:
        """Increment hit_count on a cache entry without blocking the response."""
        try:
            await self.db.execute(
                update(CacheEntry)
                .where(CacheEntry.id == entry_id)
                .values(hit_count=CacheEntry.hit_count + 1)
            )
            await self.db.commit()
        except Exception as exc:
            logger.warning("cache: failed to increment hit_count: %s", exc)
