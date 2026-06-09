# Copyright (c) 2026 Jaiden Sy. All rights reserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""SSRF guard — shared async DNS validation for MCP server URLs.

Called at registration time (mcp_servers.py) AND at proxy request time
(proxy_service.py) to guard against DNS rebinding attacks where a hostname
initially resolves to a public IP but is re-pointed to a private address
after the registration check passes.
"""

from __future__ import annotations

import asyncio
import ipaddress
from urllib.parse import urlparse

from fastapi import HTTPException, status

_PRIVATE_NETS = [
    ipaddress.ip_network(cidr)
    for cidr in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "::1/128",
        "fc00::/7",
    )
]


async def assert_ssrf_safe(
    url: str, *, error_status: int = status.HTTP_422_UNPROCESSABLE_ENTITY
) -> None:
    """Raise HTTPException if *url* resolves to a private/loopback address.

    Performs an async DNS lookup so the event loop is not blocked.
    Pass error_status=502 when calling from proxy context so callers see
    a gateway error rather than a validation error.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(
            status_code=error_status,
            detail="MCP server URL must contain a valid hostname",
        )
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(hostname, None)
    except OSError:
        raise HTTPException(
            status_code=error_status,
            detail=f"MCP server hostname {hostname!r} could not be resolved",
        )
    for _family, _type, _proto, _canonname, sockaddr in infos:
        addr = ipaddress.ip_address(sockaddr[0])
        if any(addr in net for net in _PRIVATE_NETS):
            raise HTTPException(
                status_code=error_status,
                detail=(
                    f"MCP server URL resolves to a private/reserved address ({addr}) — "
                    "requests to internal hosts are not allowed"
                ),
            )
