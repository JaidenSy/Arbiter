"""
NexusAI — pytest fixtures (conftest.py).

Shared fixtures available to all test modules.  Provides:
    - test_client:  Async HTTPX client wired to the FastAPI app with mocked deps
    - fake_redis:   In-memory fakeredis async client
    - mock_db:      AsyncMock standing in for the SQLAlchemy AsyncSession
    - agent_headers: Auth headers for a pre-created test agent

Strategy:
    Integration tests use FastAPI's dependency_overrides to inject mock DB and
    fake Redis instead of live Postgres / Redis.  This allows the full HTTP
    request/response cycle to be exercised without external infrastructure.
"""

from __future__ import annotations

import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

# ── Patch required env vars before any app import ─────────────────────────────
# Settings are validated at import time, so we must set env vars first.
_TEST_VAULT_KEY = "b" * 64  # 64 hex chars — valid for pydantic validator
os.environ.setdefault("APP_SECRET_KEY", "nexusai-test-secret-key-12345678")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/nexusai_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("VAULT_ENCRYPTION_KEY", _TEST_VAULT_KEY)

# ── Shared test constants ─────────────────────────────────────────────────────
TEST_AGENT_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
TEST_AGENT_NAME = "test-agent"
TEST_RAW_API_KEY: str = ""  # filled by fixture
TEST_AGENT_HASH: str = ""   # filled by fixture


def _make_mock_agent(raw_key: str) -> MagicMock:
    """Build a mock Agent ORM object matching a raw API key."""
    from app.core.security import hash_api_key

    agent = MagicMock()
    agent.id = TEST_AGENT_ID
    agent.name = TEST_AGENT_NAME
    agent.description = "Integration test agent"
    agent.is_active = True
    agent.api_key_hash = hash_api_key(raw_key)
    agent.created_at = datetime.now(tz=timezone.utc)
    agent.updated_at = datetime.now(tz=timezone.utc)
    return agent


def _make_mock_user() -> MagicMock:
    """Build a mock User ORM object for JWT-authenticated endpoints."""
    user = MagicMock()
    user.id = uuid.UUID("cccccccc-0000-0000-0000-000000000001")
    user.email = "test@nexusai.test"
    user.is_active = True
    return user


def _make_mock_org() -> MagicMock:
    """Build a mock Organization ORM object with a valid plan_tier for quota checks."""
    org = MagicMock()
    org.id = uuid.UUID("dddddddd-0000-0000-0000-000000000001")
    org.plan_tier = "free"
    return org


# ── fakeredis fixture ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def fake_redis():
    """
    In-memory async Redis client via fakeredis.

    Yields:
        fakeredis.aioredis.FakeRedis: ready to use, no server required.
    """
    import fakeredis.aioredis as fakeredis_aioredis
    redis = fakeredis_aioredis.FakeRedis(decode_responses=False)
    yield redis
    await redis.aclose()


# ── mock_db fixture ───────────────────────────────────────────────────────────

@pytest.fixture
def mock_db() -> AsyncMock:
    """
    A minimal AsyncMock that stands in for SQLAlchemy AsyncSession.
    Tests that need specific query results override execute() themselves.
    """
    db = AsyncMock()
    return db


# ── test_client factory ───────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_client(fake_redis) -> AsyncGenerator:
    """
    Async HTTPX test client with DB and Redis dependencies overridden.

    - get_db → yields a fresh AsyncMock per request
    - get_redis → returns fake_redis
    - get_current_agent → raises 401 by default (individual tests override)

    Yields:
        httpx.AsyncClient: pointed at the FastAPI test app.
    """
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.dependencies import get_db, get_redis

    mock_org = _make_mock_org()

    async def _override_get_db():
        db = AsyncMock()
        db.get = AsyncMock(return_value=mock_org)
        yield db

    async def _override_get_redis(request=None):
        return fake_redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ── authenticated client fixture ──────────────────────────────────────────────

@pytest_asyncio.fixture
async def authed_client(fake_redis) -> AsyncGenerator:
    """
    Async HTTPX client with a valid mock agent injected via dependency override.

    The get_current_agent dependency is replaced with one that always returns
    a mock agent — no real DB lookup occurs.

    Yields:
        tuple[AsyncClient, str, MagicMock]: (client, raw_api_key, mock_agent)
    """
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.dependencies import get_db, get_redis, get_current_agent, get_current_user
    from app.core.security import generate_api_key

    raw_key = generate_api_key()
    mock_agent = _make_mock_agent(raw_key)
    mock_user = _make_mock_user()
    mock_org = _make_mock_org()

    async def _override_get_db():
        db = AsyncMock()
        db.get = AsyncMock(return_value=mock_org)
        yield db

    async def _override_get_redis(request=None):
        return fake_redis

    async def _override_get_current_agent():
        return mock_agent

    async def _override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis
    app.dependency_overrides[get_current_agent] = _override_get_current_agent
    app.dependency_overrides[get_current_user] = _override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, raw_key, mock_agent

    app.dependency_overrides.clear()
