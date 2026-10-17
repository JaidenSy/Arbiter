# Copyright 2026 Jaiden Sy
# SPDX-License-Identifier: Apache-2.0
"""
MCP protocol constants and pure helpers shared by the inbound ``/mcp``
endpoint and the upstream client.

Arbiter is a *dual-era* MCP implementation (spec 2026-07-28 terminology):

    - **Modern** (2026-07-28+): stateless. Every request carries
      ``params._meta["io.modelcontextprotocol/protocolVersion"]`` and
      ``io.modelcontextprotocol/clientCapabilities``; there is no
      ``initialize`` and no ``Mcp-Session-Id``. Streamable HTTP POSTs also
      carry ``MCP-Protocol-Version``, ``Mcp-Method`` and (for named methods)
      ``Mcp-Name`` headers that must match the body.
    - **Legacy** (2025-11-25 and earlier): ``initialize`` handshake, optional
      ``Mcp-Session-Id``.

Names and codes below mirror ``schema/2026-07-28/schema.ts`` so a later move
to the official ``mcp`` SDK (whose ``mcp-types`` package exports the same
names) is a mechanical swap. Nothing in this module does I/O.
"""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any

# ── Protocol versions ─────────────────────────────────────────────────────────

MODERN_PROTOCOL_VERSIONS: tuple[str, ...] = ("2026-07-28",)
LATEST_MODERN_PROTOCOL_VERSION = "2026-07-28"

# Initialize-based versions, newest first.
LEGACY_PROTOCOL_VERSIONS: tuple[str, ...] = (
    "2025-11-25",
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
)
LATEST_LEGACY_PROTOCOL_VERSION = "2025-11-25"

# Spec: a server that supports pre-2025-06-18 clients MAY treat a request
# without MCP-Protocol-Version as 2025-03-26.
DEFAULT_LEGACY_HEADER_VERSION = "2025-03-26"

SUPPORTED_PROTOCOL_VERSIONS: tuple[str, ...] = MODERN_PROTOCOL_VERSIONS + LEGACY_PROTOCOL_VERSIONS

# ── _meta keys (RequestMetaObject / ResultMetaObject) ─────────────────────────

META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CLIENT_INFO = "io.modelcontextprotocol/clientInfo"
META_CLIENT_CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"
META_SERVER_INFO = "io.modelcontextprotocol/serverInfo"

# Arbiter-specific session handle. The 2026-07-28 spec removes protocol
# sessions and says state spanning requests MUST be referenced by an explicit
# identifier the client passes on each request; Arbiter's audit session is
# that state. Prefix follows the _meta reverse-DNS naming rules
# (arbiterai.dev -> dev.arbiterai/).
META_ARBITER_SESSION_ID = "dev.arbiterai/sessionId"

# ── HTTP headers (Streamable HTTP) ────────────────────────────────────────────

HEADER_PROTOCOL_VERSION = "MCP-Protocol-Version"
HEADER_METHOD = "Mcp-Method"
HEADER_NAME = "Mcp-Name"
HEADER_SESSION_ID = "Mcp-Session-Id"  # legacy era only
HEADER_ARBITER_SESSION_ID = "X-Arbiter-Session-Id"  # modern-era alternative to the _meta key

# Methods whose params.name / params.uri is mirrored in Mcp-Name.
NAMED_METHODS: dict[str, str] = {
    "tools/call": "name",
    "prompts/get": "name",
    "resources/read": "uri",
}

# ── JSON-RPC error codes ──────────────────────────────────────────────────────

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
# -32000..-32019 is the legacy implementation-defined sub-range. Arbiter has
# always used -32000 for upstream proxy failures; kept for legacy clients.
SERVER_ERROR = -32000
# -32020..-32099 is reserved for the MCP spec; only these are defined.
HEADER_MISMATCH = -32020
MISSING_REQUIRED_CLIENT_CAPABILITY = -32021
UNSUPPORTED_PROTOCOL_VERSION = -32022

MODERN_ERROR_CODES = frozenset(
    {HEADER_MISMATCH, MISSING_REQUIRED_CLIENT_CAPABILITY, UNSUPPORTED_PROTOCOL_VERSION}
)

# ── Result fields ─────────────────────────────────────────────────────────────

RESULT_TYPE_COMPLETE = "complete"
CACHE_SCOPE_PUBLIC = "public"
CACHE_SCOPE_PRIVATE = "private"

_B64_PREFIX = "=?base64?"
_B64_SUFFIX = "?="


# ── Builders ──────────────────────────────────────────────────────────────────


def rpc_error(req_id: Any, code: int, message: str, data: Any | None = None) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 error response object."""
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": error}


def rpc_result(req_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 success response object."""
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def unsupported_version_error(req_id: Any, requested: Any) -> dict[str, Any]:
    """UnsupportedProtocolVersionError (-32022) listing every version we speak."""
    return rpc_error(
        req_id,
        UNSUPPORTED_PROTOCOL_VERSION,
        "Unsupported protocol version",
        {"supported": list(SUPPORTED_PROTOCOL_VERSIONS), "requested": requested},
    )


# ── Header value encoding (Streamable HTTP "Value Encoding") ──────────────────


def _is_plain_header_safe(value: str) -> bool:
    if not value or value != value.strip():
        return False
    if value.startswith(_B64_PREFIX) and value.endswith(_B64_SUFFIX):
        return False
    return all(0x20 <= ord(ch) <= 0x7E for ch in value)


def encode_header_value(value: str) -> str:
    """Encode a value for Mcp-Name / Mcp-Param-*: plain ASCII or the Base64 sentinel."""
    if _is_plain_header_safe(value):
        return value
    encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
    return f"{_B64_PREFIX}{encoded}{_B64_SUFFIX}"


def decode_header_value(raw: str) -> str | None:
    """
    Decode an Mcp-Name / Mcp-Param-* header value.

    Returns None when the value contains characters not allowed in an HTTP
    field value or carries a malformed Base64 sentinel; callers treat that as
    a HeaderMismatch.
    """
    if any(not (ch == "\t" or 0x20 <= ord(ch) <= 0x7E) for ch in raw):
        return None
    if raw.startswith(_B64_PREFIX) and raw.endswith(_B64_SUFFIX) and len(raw) >= 11:
        payload = raw[len(_B64_PREFIX) : -len(_B64_SUFFIX)]
        try:
            return base64.b64decode(payload, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return None
    return raw


# ── Era detection ─────────────────────────────────────────────────────────────


def request_meta(params: Any) -> dict[str, Any] | None:
    """Return params._meta when it is an object, else None."""
    if not isinstance(params, dict):
        return None
    meta = params.get("_meta")
    return meta if isinstance(meta, dict) else None


def modern_protocol_version(params: Any) -> Any | None:
    """
    The per-request protocol version from ``params._meta``, or None.

    A non-None value marks the request as modern-era (the dual-era server
    rule: "a request carrying modern per-request _meta is served statelessly").
    The value is returned unvalidated; callers check type and support.
    """
    meta = request_meta(params)
    if meta is None:
        return None
    return meta.get(META_PROTOCOL_VERSION)


def is_modern_version(version: Any) -> bool:
    return isinstance(version, str) and version in MODERN_PROTOCOL_VERSIONS


# ── Response parsing ──────────────────────────────────────────────────────────


def extract_jsonrpc_from_sse(text: str) -> dict[str, Any]:
    """
    Return the last complete JSON-RPC message from an SSE response body.

    Upstream servers may emit keepalives or partial events before the final
    response: breaking on the first event silently drops data, so we keep
    the last frame that carries a ``result`` or ``error``.
    """
    json_body: dict[str, Any] = {}
    for line in text.splitlines():
        if line.startswith("data:"):
            data = line[5:].lstrip(" ")
            try:
                candidate = json.loads(data)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and ("result" in candidate or "error" in candidate):
                json_body = candidate
    return json_body


def modern_error_code(body: Any) -> int | None:
    """
    Return the error code if ``body`` is a recognized *modern* JSON-RPC error.

    Per the 2026-07-28 backward-compatibility rules, a 4xx whose body carries
    one of these codes identifies a modern server (don't fall back to
    ``initialize``); anything else identifies a legacy server.
    """
    if not isinstance(body, dict):
        return None
    error = body.get("error")
    if not isinstance(error, dict):
        return None
    code = error.get("code")
    return code if isinstance(code, int) and code in MODERN_ERROR_CODES else None
