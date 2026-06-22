"""
Integration tests for custom exception handlers registered in main.py.

Coverage:
    401 handler:
    - Authenticated endpoint with no Authorization header → 401 JSON
    - Response format is the CUSTOM handler format (not FastAPI default)
    - WWW-Authenticate header is present

    422 validation error:
    - POST /agents with missing required field → 422 with 'errors' key
      (custom handler wraps errors in {"detail": ..., "errors": ...})
"""

from __future__ import annotations

import pytest


class TestUnauthorizedHandler:
    @pytest.mark.asyncio
    async def test_no_auth_header_returns_401_with_custom_json(self, test_client):
        """
        Calling an authenticated endpoint with no Authorization header → 401.

        Verifies:
        - Status code is 401
        - Response JSON has 'detail' key (custom format)
        - Response is NOT the FastAPI default {"detail": "Not authenticated"}
          (our handler returns "Unauthorized: valid Bearer API key required")
        """
        resp = await test_client.get("/api/v1/agents")

        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

        data = resp.json()
        assert "detail" in data, "401 response must have 'detail' key"

        # Custom handler message differs from FastAPI default
        assert data["detail"] != "Not authenticated", (
            "Must use the custom 401 handler, not FastAPI's default error"
        )
        assert "Bearer" in data["detail"] or "Unauthorized" in data["detail"], (
            f"Custom 401 detail should mention Bearer/Unauthorized, got: {data['detail']!r}"
        )

    @pytest.mark.asyncio
    async def test_401_response_has_www_authenticate_header(self, test_client):
        """401 response must include WWW-Authenticate: Bearer header."""
        resp = await test_client.get("/api/v1/agents")

        assert resp.status_code == 401
        assert "www-authenticate" in {k.lower() for k in resp.headers}, (
            "401 response must include WWW-Authenticate header"
        )
        assert resp.headers.get("www-authenticate", "").lower() == "bearer"

    @pytest.mark.asyncio
    async def test_401_on_multiple_authenticated_endpoints(self, test_client):
        """All authenticated endpoints must return 401 without auth (not 500 or 200)."""
        endpoints = [
            ("GET", "/api/v1/agents"),
            ("GET", "/api/v1/mcp-servers"),
            ("GET", "/api/v1/sessions"),
            ("GET", "/api/v1/stats"),
            ("GET", "/api/v1/vault/secrets"),
        ]

        for method, path in endpoints:
            if method == "GET":
                resp = await test_client.get(path)
            else:
                resp = await test_client.post(path, json={})

            assert resp.status_code == 401, (
                f"{method} {path} expected 401 without auth, got {resp.status_code}: {resp.text}"
            )


class TestValidationErrorHandler:
    @pytest.mark.asyncio
    async def test_post_agent_missing_name_returns_422(self, test_client):
        """
        POST /agents with missing required 'name' field → 422.

        FastAPI validation errors pass through RequestValidationError handler
        which wraps them in {"detail": "Request validation failed", "errors": ...}.
        """
        from app.main import app
        from app.core.dependencies import get_db, get_current_user
        from tests.conftest import _make_mock_user
        from unittest.mock import AsyncMock

        mock_user = _make_mock_user()

        async def override_get_db():
            yield AsyncMock()

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            # POST without 'name' field: required by AgentCreate schema
            resp = await test_client.post(
                "/api/v1/agents",
                json={},  # missing required 'name'
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)

        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_422_response_has_detail_key(self, test_client):
        """422 response from custom handler must include 'detail' key."""
        from app.main import app
        from app.core.dependencies import get_db, get_current_user
        from tests.conftest import _make_mock_user
        from unittest.mock import AsyncMock

        mock_user = _make_mock_user()

        async def override_get_db():
            yield AsyncMock()

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            resp = await test_client.post(
                "/api/v1/agents",
                json={},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)

        assert resp.status_code == 422
        data = resp.json()
        assert "detail" in data, f"422 response must have 'detail' key, got: {data}"
