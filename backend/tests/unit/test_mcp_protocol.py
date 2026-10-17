"""
Unit tests for app.services.mcp.protocol: pure helpers shared by the inbound
endpoint and the upstream client.

Expected values (error codes, sentinel format, examples) are taken from the
MCP 2026-07-28 spec: basic/index (error codes), basic/transports/
streamable-http (Value Encoding table), schema.ts (UnsupportedProtocolVersion).
"""

from __future__ import annotations

import pytest

from app.services.mcp import protocol as p


class TestErrorCodes:
    def test_spec_reserved_codes(self):
        assert p.HEADER_MISMATCH == -32020
        assert p.MISSING_REQUIRED_CLIENT_CAPABILITY == -32021
        assert p.UNSUPPORTED_PROTOCOL_VERSION == -32022

    def test_unsupported_version_error_shape(self):
        err = p.unsupported_version_error(1, "1900-01-01")
        assert err["id"] == 1
        assert err["error"]["code"] == -32022
        assert err["error"]["data"]["requested"] == "1900-01-01"
        assert err["error"]["data"]["supported"][0] == "2026-07-28"

    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            ({"error": {"code": -32020}}, -32020),
            ({"error": {"code": -32022, "data": {}}}, -32022),
            ({"error": {"code": -32601}}, None),
            ({"error": {"code": -32000}}, None),
            ({"result": {}}, None),
            ("not a dict", None),
        ],
    )
    def test_modern_error_code(self, body, expected):
        assert p.modern_error_code(body) == expected


class TestHeaderValueEncoding:
    @pytest.mark.parametrize(
        ("value", "encoded"),
        [
            ("us-west1", "us-west1"),
            ("Hello, 世界", "=?base64?SGVsbG8sIOS4lueVjA==?="),
            (" padded ", "=?base64?IHBhZGRlZCA=?="),
            ("line1\nline2", "=?base64?bGluZTEKbGluZTI=?="),
            ("=?base64?literal?=", "=?base64?PT9iYXNlNjQ/bGl0ZXJhbD89?="),
        ],
    )
    def test_spec_examples_round_trip(self, value, encoded):
        assert p.encode_header_value(value) == encoded
        assert p.decode_header_value(encoded) == value

    def test_invalid_characters_rejected(self):
        assert p.decode_header_value("bad\x00value") is None

    def test_malformed_base64_rejected(self):
        assert p.decode_header_value("=?base64?***?=") is None


class TestEraDetection:
    def test_modern_version_from_meta(self):
        params = {"_meta": {p.META_PROTOCOL_VERSION: "2026-07-28"}}
        assert p.modern_protocol_version(params) == "2026-07-28"
        assert p.is_modern_version("2026-07-28")

    def test_legacy_request_has_no_modern_version(self):
        assert p.modern_protocol_version({"protocolVersion": "2025-06-18"}) is None
        assert p.modern_protocol_version({"_meta": "nope"}) is None
        assert not p.is_modern_version("2025-11-25")


class TestSse:
    def test_last_result_frame_wins(self):
        text = (
            ": keepalive\n"
            'data: {"jsonrpc":"2.0","method":"notifications/progress"}\n\n'
            'data: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n\n'
        )
        assert p.extract_jsonrpc_from_sse(text) == {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"ok": True},
        }

    def test_data_without_space_is_parsed(self):
        assert p.extract_jsonrpc_from_sse('data:{"id":1,"error":{"code":-1}}')["error"] == {
            "code": -1
        }
