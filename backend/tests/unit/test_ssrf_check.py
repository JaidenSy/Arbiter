"""
Unit tests for assert_ssrf_safe (app.core.ssrf, issue #195 / #182).

Tests that the async DNS-based SSRF check correctly:
- Blocks private/loopback addresses
- Blocks unresolvable hostnames
- Allows public IP addresses
- Blocks invalid URLs with no hostname
- Respects the error_status override (used by proxy_service for 502)
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.core.ssrf import assert_ssrf_safe


class TestAssertSsrfSafe:
    @pytest.mark.asyncio
    async def test_private_ipv4_blocked(self):
        """URL resolving to RFC-1918 private IPv4 raises 422."""
        loop = asyncio.get_running_loop()
        with pytest.MonkeyPatch().context() as mp:

            async def _mock_getaddrinfo(host, port, *a, **kw):
                return [(2, 1, 6, "", ("192.168.1.100", 0))]

            mp.setattr(loop, "getaddrinfo", _mock_getaddrinfo)
            with pytest.raises(HTTPException) as exc_info:
                await assert_ssrf_safe("http://internal.example.com")

        assert exc_info.value.status_code == 422
        assert "private" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_loopback_blocked(self):
        """URL resolving to 127.0.0.1 raises 422."""
        loop = asyncio.get_running_loop()
        with pytest.MonkeyPatch().context() as mp:

            async def _mock_getaddrinfo(host, port, *a, **kw):
                return [(2, 1, 6, "", ("127.0.0.1", 0))]

            mp.setattr(loop, "getaddrinfo", _mock_getaddrinfo)
            with pytest.raises(HTTPException) as exc_info:
                await assert_ssrf_safe("http://localhost")

        assert exc_info.value.status_code == 422
        assert "private" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_link_local_blocked(self):
        """URL resolving to 169.254.x.x (AWS metadata) raises 422."""
        loop = asyncio.get_running_loop()
        with pytest.MonkeyPatch().context() as mp:

            async def _mock_getaddrinfo(host, port, *a, **kw):
                return [(2, 1, 6, "", ("169.254.169.254", 0))]

            mp.setattr(loop, "getaddrinfo", _mock_getaddrinfo)
            with pytest.raises(HTTPException) as exc_info:
                await assert_ssrf_safe("http://metadata.example.com")

        assert exc_info.value.status_code == 422
        assert "private" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_public_ip_allowed(self):
        """URL resolving to a public IP passes without raising."""
        loop = asyncio.get_running_loop()
        with pytest.MonkeyPatch().context() as mp:

            async def _mock_getaddrinfo(host, port, *a, **kw):
                return [(2, 1, 6, "", ("93.184.216.34", 0))]

            mp.setattr(loop, "getaddrinfo", _mock_getaddrinfo)
            await assert_ssrf_safe("http://example.com")

    @pytest.mark.asyncio
    async def test_unresolvable_hostname_blocked(self):
        """URL whose hostname cannot be resolved raises 422."""
        loop = asyncio.get_running_loop()
        with pytest.MonkeyPatch().context() as mp:

            async def _mock_getaddrinfo(host, port, *a, **kw):
                raise OSError("Name or service not known")

            mp.setattr(loop, "getaddrinfo", _mock_getaddrinfo)
            with pytest.raises(HTTPException) as exc_info:
                await assert_ssrf_safe("http://this.does.not.resolve.invalid")

        assert exc_info.value.status_code == 422
        assert "could not be resolved" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_url_without_hostname_blocked(self):
        """URL with no valid hostname raises 422 before DNS lookup."""
        with pytest.raises(HTTPException) as exc_info:
            await assert_ssrf_safe("http://")

        assert exc_info.value.status_code == 422
        assert "hostname" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_error_status_override(self):
        """Proxy context passes error_status=502 so the caller sees a gateway error."""
        loop = asyncio.get_running_loop()
        with pytest.MonkeyPatch().context() as mp:

            async def _mock_getaddrinfo(host, port, *a, **kw):
                return [(2, 1, 6, "", ("10.0.0.1", 0))]

            mp.setattr(loop, "getaddrinfo", _mock_getaddrinfo)
            with pytest.raises(HTTPException) as exc_info:
                await assert_ssrf_safe("http://internal.example.com", error_status=502)

        assert exc_info.value.status_code == 502
        assert "private" in exc_info.value.detail
