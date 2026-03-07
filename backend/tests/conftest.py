"""
NexusAI — pytest fixtures (conftest.py).

Shared fixtures available to all test modules.  Provides:
    - test_client:  Async HTTPX client wired to the FastAPI app
    - test_db:      In-memory / test-schema async SQLAlchemy session
    - test_redis:   Fake Redis client (fakeredis or test Redis instance)
    - agent_headers: Auth headers for a pre-created test agent

Usage in tests:
    async def test_health(test_client):
        response = await test_client.get("/health")
        assert response.status_code == 200
"""

from __future__ import annotations

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient

# ── App import (deferred to avoid triggering DB engine at import time) ─────────
# from app.main import app


@pytest_asyncio.fixture
async def test_client() -> AsyncGenerator[AsyncClient, None]:
    """
    Provide an async HTTPX test client for the FastAPI application.

    Uses ``app.router`` transport so no real HTTP server is started.
    Database and Redis dependencies are overridden via ``app.dependency_overrides``.

    Yields:
        AsyncClient: configured for the test app, with base_url="http://test".
    """
    # TODO: from app.main import app
    # TODO: app.dependency_overrides[get_db] = override_get_db
    # TODO: app.dependency_overrides[get_redis] = override_get_redis
    # TODO: async with AsyncClient(app=app, base_url="http://test") as client:
    #           yield client
    raise NotImplementedError("test_client fixture not yet implemented")
    yield  # type: ignore[misc]


@pytest_asyncio.fixture
async def test_db():  # type: ignore[return]
    """
    Provide an async SQLAlchemy session connected to the test database.

    Creates all tables before the test and drops them after.  Uses a
    separate test DATABASE_URL (e.g. nexusai_test schema) so it never
    touches production data.

    Yields:
        AsyncSession: bound to the test database.
    """
    # TODO: create test engine from TEST_DATABASE_URL
    # TODO: async with engine.begin() as conn:
    #           await conn.run_sync(Base.metadata.create_all)
    # TODO: yield session
    # TODO: drop all tables after test
    raise NotImplementedError("test_db fixture not yet implemented")
    yield  # type: ignore[misc]


@pytest_asyncio.fixture
async def test_redis():  # type: ignore[return]
    """
    Provide a fake Redis client for unit/integration tests.

    Uses ``fakeredis.aioredis.FakeRedis`` so tests run without a real
    Redis instance.

    Yields:
        FakeRedis: in-memory async Redis client.
    """
    # TODO: import fakeredis.aioredis as fakeredis
    # TODO: async with fakeredis.FakeRedis() as redis:
    #           yield redis
    raise NotImplementedError("test_redis fixture not yet implemented")
    yield  # type: ignore[misc]


@pytest.fixture
def agent_headers() -> dict[str, str]:
    """
    Return HTTP headers with a valid test agent API key.

    The test agent is seeded in test_db.  Use these headers with
    test_client to make authenticated requests.

    Returns:
        dict: ``{"Authorization": "Bearer nxai_test_..."}``
    """
    # TODO: return {"Authorization": f"Bearer {TEST_API_KEY}"}
    raise NotImplementedError("agent_headers fixture not yet implemented")
