# Copyright 2026 Jaiden Sy
# SPDX-License-Identifier: Apache-2.0
"""
Dual-era MCP client used by ProxyService to talk to upstream MCP servers.

Era detection follows the 2026-07-28 Streamable HTTP "Backward Compatibility"
rules:

    1. Probe modern-first with ``server/discover`` (per-request ``_meta`` plus
       ``MCP-Protocol-Version`` / ``Mcp-Method`` headers).
    2. 2xx with a ``DiscoverResult`` -> modern, if it lists a version we speak.
    3. 4xx whose body is a recognized modern JSON-RPC error (-32020/-32021/
       -32022) -> modern server. On -32022 we pick a mutually supported
       version from ``error.data.supported`` (possibly a legacy one).
    4. Anything else -> legacy: ``initialize`` with our newest legacy version,
       ``notifications/initialized``, then ``Mcp-Session-Id`` +
       ``MCP-Protocol-Version`` on every request.

The era is a property of the server, so it is cached per server (and auth
config) in Redis. Legacy sessions are cached per caller-provided key. A
legacy request answered with 404 while carrying a session id means the
session expired: the caller asks ``recover()`` for a fresh target and
retries once. A cached-modern server that suddenly answers 4xx without a
modern error body is re-probed once.

This module deliberately mirrors the official ``mcp`` SDK's dual-era client
behaviour so it can be replaced by ``mcp.Client`` once the backend's pinned
dependencies (pydantic 2.9, httpx 0.27) allow the SDK.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace
from typing import Any, Literal

import httpx
from fastapi import HTTPException, status

from app.services.mcp import protocol as p

logger = logging.getLogger(__name__)

Era = Literal["modern", "legacy"]
MODERN: Era = "modern"
LEGACY: Era = "legacy"

CLIENT_INFO = {"name": "arbiter-gateway", "version": "0.5.0"}

_ERA_CACHE_TTL = 3600
_SESSION_CACHE_TTL = 3600
_FALLBACK_STATUSES = frozenset({400, 404, 405})


@dataclass(frozen=True)
class UpstreamTarget:
    """Everything needed to address one upstream request in the right era."""

    era: Era
    protocol_version: str | None
    base_headers: dict[str, str]
    session_id: str | None = None
    session_cache_key: str | None = None

    def build(
        self, method: str, params: dict[str, Any], req_id: str | int
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Return (JSON-RPC body, HTTP headers) for ``method`` in this era."""
        headers = dict(self.base_headers)
        body_params = dict(params)
        if self.era == MODERN:
            version = self.protocol_version or p.LATEST_MODERN_PROTOCOL_VERSION
            meta = dict(body_params.get("_meta") or {})
            meta[p.META_PROTOCOL_VERSION] = version
            meta.setdefault(p.META_CLIENT_INFO, CLIENT_INFO)
            meta.setdefault(p.META_CLIENT_CAPABILITIES, {})
            body_params["_meta"] = meta
            headers[p.HEADER_PROTOCOL_VERSION] = version
            headers[p.HEADER_METHOD] = method
            name_field = p.NAMED_METHODS.get(method)
            name_value = body_params.get(name_field) if name_field else None
            if isinstance(name_value, str):
                headers[p.HEADER_NAME] = p.encode_header_value(name_value)
        else:
            if self.protocol_version:
                headers[p.HEADER_PROTOCOL_VERSION] = self.protocol_version
            if self.session_id:
                headers[p.HEADER_SESSION_ID] = self.session_id
        body = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": body_params}
        return body, headers


def parse_response_body(resp: httpx.Response) -> dict[str, Any]:
    """Best-effort JSON-RPC body from a JSON or SSE response ({} if neither)."""
    try:
        if "text/event-stream" in resp.headers.get("content-type", ""):
            return p.extract_jsonrpc_from_sse(resp.text)
        body = resp.json()
        return body if isinstance(body, dict) else {}
    except Exception:
        return {}


def _best_legacy_version(versions: Any) -> str | None:
    if not isinstance(versions, list):
        return None
    for candidate in p.LEGACY_PROTOCOL_VERSIONS:  # newest first
        if candidate in versions:
            return candidate
    return None


class UpstreamMCPClient:
    """Era detection, legacy handshake and session recovery for one ProxyService."""

    def __init__(self, redis: Any, timeout: httpx.Timeout) -> None:
        self.redis = redis
        self.timeout = timeout

    # ── Public API ────────────────────────────────────────────────────────────

    async def prepare(
        self,
        base_url: str,
        server_key: str,
        extra_headers: dict[str, str] | None,
        session_cache_key: str | None,
    ) -> UpstreamTarget:
        """
        Resolve the upstream's era (cached) and, for legacy servers, a session.

        ``server_key`` identifies the server + auth config for the era cache.
        Never raises for transport problems: a failed probe or handshake
        degrades to "legacy, no session" so the real request surfaces the
        error through the caller's normal retry/502 path.
        """
        base = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **(extra_headers or {}),
        }
        era, version = await self._resolve_era(base_url, server_key, base)
        if era == MODERN:
            return UpstreamTarget(MODERN, version, base)

        if session_cache_key:
            stored = await self._load_session(session_cache_key)
            if stored is not None:
                stored_sid, stored_version = stored
                return UpstreamTarget(LEGACY, stored_version, base, stored_sid, session_cache_key)

        sid, negotiated = await self._initialize(base_url, base, version)
        target = UpstreamTarget(LEGACY, negotiated, base, sid, session_cache_key)
        if sid:
            await self._store_session(target)
        return target

    async def recover(
        self,
        base_url: str,
        server_key: str,
        target: UpstreamTarget,
        resp: httpx.Response,
    ) -> UpstreamTarget | None:
        """
        Decide whether a failed upstream response deserves one retry.

        Returns a fresh target to retry with, or None to surface the error.
        """
        if target.era == LEGACY and target.session_id and resp.status_code == 404:
            # Legacy Streamable HTTP: 404 on a request carrying Mcp-Session-Id
            # means the session expired; the client MUST start a new one.
            logger.info("mcp upstream: session expired at %s; re-initializing", base_url)
            await self._delete(target.session_cache_key)
            sid, negotiated = await self._initialize(
                base_url, target.base_headers, target.protocol_version
            )
            fresh = replace(target, session_id=sid, protocol_version=negotiated)
            if sid:
                await self._store_session(fresh)
            return fresh

        if target.era == MODERN and resp.status_code in _FALLBACK_STATUSES:
            body = parse_response_body(resp)
            error = body.get("error") if isinstance(body.get("error"), dict) else None
            if p.modern_error_code(body) is not None:
                return None
            if resp.status_code == 404 and error and error.get("code") == p.METHOD_NOT_FOUND:
                return None  # modern server, method genuinely missing
            # Cached modern assumption no longer holds: re-probe once.
            logger.info("mcp upstream: %s no longer answers as modern; re-probing", base_url)
            await self._delete(_era_cache_key(server_key))
            fresh = await self.prepare(
                base_url, server_key, _auth_headers(target.base_headers), target.session_cache_key
            )
            return fresh if fresh.era != MODERN else None
        return None

    async def remember_session_id(self, target: UpstreamTarget, session_id: str | None) -> None:
        """Persist a session id the upstream (re)assigned on a legacy response."""
        if target.era != LEGACY or not session_id or session_id == target.session_id:
            return
        await self._store_session(replace(target, session_id=session_id))

    # ── Era detection ─────────────────────────────────────────────────────────

    async def _resolve_era(
        self, base_url: str, server_key: str, base_headers: dict[str, str]
    ) -> tuple[Era, str | None]:
        cache_key = _era_cache_key(server_key)
        cached = await self._get_json(cache_key)
        if cached and cached.get("era") in (MODERN, LEGACY):
            return cached["era"], cached.get("version")

        try:
            era, version, cacheable = await self._probe(base_url, base_headers)
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("mcp upstream: discover probe failed for %s: %s", base_url, exc)
            return LEGACY, None
        if cacheable:
            try:
                await self.redis.set(
                    cache_key, json.dumps({"era": era, "version": version}), ex=_ERA_CACHE_TTL
                )
            except Exception as exc:
                logger.warning("mcp upstream: era cache write failed: %s", exc)
        return era, version

    async def _probe(
        self, base_url: str, base_headers: dict[str, str]
    ) -> tuple[Era, str | None, bool]:
        """Modern-first probe. Returns (era, version, cacheable)."""
        probe = UpstreamTarget(MODERN, p.LATEST_MODERN_PROTOCOL_VERSION, base_headers)
        body, headers = probe.build("server/discover", {}, "arbiter-discover")
        resp = await self._post(base_url, body, headers)
        parsed = parse_response_body(resp)

        if resp.status_code < 300:
            result = parsed.get("result")
            if isinstance(result, dict) and isinstance(result.get("supportedVersions"), list):
                supported = result["supportedVersions"]
                if p.LATEST_MODERN_PROTOCOL_VERSION in supported:
                    return MODERN, p.LATEST_MODERN_PROTOCOL_VERSION, True
                return LEGACY, _best_legacy_version(supported), True
            # 2xx with a JSON-RPC error (e.g. method not found) -> legacy server.
            return LEGACY, None, True

        if resp.status_code in (401, 403):
            # Auth problem, not an era signal. Don't cache a guess.
            return LEGACY, None, False

        code = p.modern_error_code(parsed)
        if code == p.UNSUPPORTED_PROTOCOL_VERSION:
            data = parsed["error"].get("data") or {}
            supported = data.get("supported") if isinstance(data, dict) else None
            legacy = _best_legacy_version(supported)
            if legacy is None:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=(
                        "Upstream MCP server supports no protocol version Arbiter speaks "
                        f"(server supports {supported!r})"
                    ),
                )
            return LEGACY, legacy, True
        if code is not None:
            # Modern server that rejected the probe itself (header/capability
            # validation). It is still modern; don't fall back to initialize.
            return MODERN, p.LATEST_MODERN_PROTOCOL_VERSION, True
        return LEGACY, None, resp.status_code < 500

    # ── Legacy handshake ──────────────────────────────────────────────────────

    async def _initialize(
        self, base_url: str, base_headers: dict[str, str], preferred_version: str | None
    ) -> tuple[str | None, str | None]:
        """
        ``initialize`` + ``notifications/initialized``.

        Returns (session_id, negotiated_version). Failures are logged and
        yield (None, None) so the caller still attempts the real request
        (pre-existing behaviour for servers that don't need a handshake).
        """
        requested = preferred_version or p.LATEST_LEGACY_PROTOCOL_VERSION
        init_body = {
            "jsonrpc": "2.0",
            "id": "arbiter-init",
            "method": "initialize",
            "params": {
                "protocolVersion": requested,
                "capabilities": {},
                "clientInfo": CLIENT_INFO,
            },
        }
        try:
            resp = await self._post(base_url, init_body, dict(base_headers))
            parsed = parse_response_body(resp)
            raw_result = parsed.get("result")
            result: dict[str, Any] = raw_result if isinstance(raw_result, dict) else {}
            negotiated = result.get("protocolVersion")
            if not isinstance(negotiated, str):
                negotiated = requested if resp.status_code < 400 else None
            elif negotiated not in p.LEGACY_PROTOCOL_VERSIONS:
                logger.warning(
                    "mcp upstream: %s negotiated unknown protocol version %r",
                    base_url,
                    negotiated,
                )
            session_id = resp.headers.get(p.HEADER_SESSION_ID)

            if resp.status_code < 400:
                notif_headers = dict(base_headers)
                if negotiated:
                    notif_headers[p.HEADER_PROTOCOL_VERSION] = negotiated
                if session_id:
                    notif_headers[p.HEADER_SESSION_ID] = session_id
                notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
                notif_resp = await self._post(base_url, notif, notif_headers)
                if notif_resp.status_code >= 400:
                    logger.warning(
                        "mcp upstream: notifications/initialized rejected by %s (HTTP %s)",
                        base_url,
                        notif_resp.status_code,
                    )
            logger.debug("mcp upstream: initialized %s (session=%r)", base_url, session_id)
            return session_id, negotiated
        except Exception as exc:
            logger.warning("mcp upstream: initialize handshake failed for %s: %s", base_url, exc)
            return None, None

    # ── Plumbing ──────────────────────────────────────────────────────────────

    async def _post(
        self, url: str, body: dict[str, Any], headers: dict[str, str]
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await client.post(url, json=body, headers=headers)

    async def _load_session(self, key: str) -> tuple[str, str | None] | None:
        try:
            raw = await self.redis.get(key)
        except Exception as exc:
            logger.warning("mcp upstream: session lookup failed: %s", exc)
            return None
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            data = None
        if isinstance(data, dict) and isinstance(data.get("sid"), str):
            version = data.get("v")
            return data["sid"], version if isinstance(version, str) else None
        # Pre-dual-era cache entries stored the bare session id.
        return (raw, None) if isinstance(raw, str) else None

    async def _store_session(self, target: UpstreamTarget) -> None:
        if not target.session_cache_key or not target.session_id:
            return
        try:
            await self.redis.set(
                target.session_cache_key,
                json.dumps({"sid": target.session_id, "v": target.protocol_version}),
                ex=_SESSION_CACHE_TTL,
            )
        except Exception as exc:
            logger.warning("mcp upstream: session store failed: %s", exc)

    async def _get_json(self, key: str) -> dict[str, Any] | None:
        try:
            raw = await self.redis.get(key)
            if not raw:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode()
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    async def _delete(self, key: str | None) -> None:
        if not key:
            return
        try:
            await self.redis.delete(key)
        except Exception as exc:
            logger.warning("mcp upstream: cache delete failed: %s", exc)


def _era_cache_key(server_key: str) -> str:
    return f"mcp_upstream_era:{server_key}"


def _auth_headers(base_headers: dict[str, str]) -> dict[str, str]:
    """Strip the transport headers prepare() adds, leaving caller-supplied ones."""
    return {k: v for k, v in base_headers.items() if k not in ("Content-Type", "Accept")}
