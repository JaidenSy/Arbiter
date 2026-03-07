"""
Unit tests for app.core.security

Coverage:
    - generate_api_key() returns a string starting with "nxai_"
    - hash_api_key() returns consistent SHA-256 hex
    - verify_api_key() returns True for matching pair, False for wrong key
    - Timing attack: verify takes same time for match vs no-match (statistical)
"""

from __future__ import annotations

import hashlib
import statistics
import time

import pytest

from app.core.security import generate_api_key, hash_api_key, verify_api_key


class TestGenerateApiKey:
    def test_returns_string(self):
        key = generate_api_key()
        assert isinstance(key, str)

    def test_starts_with_nxai_prefix(self):
        key = generate_api_key()
        assert key.startswith("nxai_"), f"Key {key!r} does not start with 'nxai_'"

    def test_format_nxai_then_64_hex_chars(self):
        key = generate_api_key()
        # Format: nxai_<64 hex chars>
        parts = key.split("_", 1)
        assert parts[0] == "nxai"
        assert len(parts[1]) == 64, f"Hex portion length is {len(parts[1])}, expected 64"
        assert all(c in "0123456789abcdef" for c in parts[1]), "Hex portion is not valid hex"

    def test_uniqueness(self):
        """Each call should produce a different key (cryptographically random)."""
        keys = {generate_api_key() for _ in range(20)}
        assert len(keys) == 20, "Duplicate keys generated — RNG is not random"

    def test_custom_prefix(self):
        key = generate_api_key(prefix="test")
        assert key.startswith("test_")


class TestHashApiKey:
    def test_returns_64_char_hex_string(self):
        h = hash_api_key("nxai_abc123")
        assert isinstance(h, str)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self):
        key = "nxai_deadbeef" * 4
        h1 = hash_api_key(key)
        h2 = hash_api_key(key)
        assert h1 == h2, "hash_api_key is not deterministic"

    def test_matches_sha256(self):
        """Output must equal hashlib.sha256(key.encode()).hexdigest()."""
        key = generate_api_key()
        expected = hashlib.sha256(key.encode()).hexdigest()
        assert hash_api_key(key) == expected

    def test_different_inputs_produce_different_hashes(self):
        h1 = hash_api_key("nxai_aaaa")
        h2 = hash_api_key("nxai_bbbb")
        assert h1 != h2


class TestVerifyApiKey:
    def test_returns_true_for_matching_pair(self):
        key = generate_api_key()
        h = hash_api_key(key)
        assert verify_api_key(key, h) is True

    def test_returns_false_for_wrong_key(self):
        key = generate_api_key()
        h = hash_api_key(key)
        other_key = generate_api_key()
        assert verify_api_key(other_key, h) is False

    def test_returns_false_for_tampered_hash(self):
        key = generate_api_key()
        h = hash_api_key(key)
        bad_hash = "a" * 64
        assert verify_api_key(key, bad_hash) is False

    def test_returns_false_for_empty_key(self):
        key = generate_api_key()
        h = hash_api_key(key)
        assert verify_api_key("", h) is False

    def test_timing_constant_time(self):
        """
        verify_api_key should take approximately the same time for a match
        vs a non-match (constant-time via hmac.compare_digest).

        We measure 200 iterations each and compare medians. The difference
        must be < 0.5 ms to pass (generous threshold for CI noise).
        """
        key = generate_api_key()
        stored_hash = hash_api_key(key)
        wrong_key = generate_api_key()

        ITERATIONS = 200

        match_times: list[float] = []
        for _ in range(ITERATIONS):
            t0 = time.perf_counter()
            verify_api_key(key, stored_hash)
            match_times.append(time.perf_counter() - t0)

        nomatch_times: list[float] = []
        for _ in range(ITERATIONS):
            t0 = time.perf_counter()
            verify_api_key(wrong_key, stored_hash)
            nomatch_times.append(time.perf_counter() - t0)

        median_match = statistics.median(match_times)
        median_nomatch = statistics.median(nomatch_times)
        diff_ms = abs(median_match - median_nomatch) * 1000

        # Allow up to 0.5 ms difference — both paths do the same SHA-256 + compare_digest
        assert diff_ms < 0.5, (
            f"Timing difference too large: {diff_ms:.3f} ms "
            f"(match={median_match*1000:.3f}ms, nomatch={median_nomatch*1000:.3f}ms). "
            "Possible timing oracle."
        )
