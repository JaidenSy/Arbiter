# Copyright (c) 2026 Jaiden Sy. All rights reserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Arbiter — Request utility helpers.
"""

from __future__ import annotations

import os

from fastapi import Request

# Number of trusted reverse proxies in front of this app.
# Railway sits behind 1 LB; adjust via env var for other deployments.
_TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "1"))


def get_client_ip(request: Request) -> str:
    """Return the real client IP, accounting for trusted reverse proxies.

    Takes the Nth-from-right value in X-Forwarded-For (where N =
    TRUSTED_PROXY_COUNT) — the IP appended by the last trusted proxy and
    therefore not spoofable by the client.  Falls back to request.client.host
    when the header is absent.
    """
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if len(parts) > _TRUSTED_PROXY_COUNT:
            return parts[-_TRUSTED_PROXY_COUNT - 1]
        return parts[0]
    return request.client.host if request.client else "unknown"
