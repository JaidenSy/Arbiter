# Copyright 2026 Jaiden Sy
# SPDX-License-Identifier: Apache-2.0
"""
Arbiter OpenTelemetry tracing (opt-in).

Tracing is OFF unless all of these hold:
    - ``OTEL_ENABLED=true`` (app setting, default false)
    - ``OTEL_SDK_DISABLED`` is not ``true`` (standard OTel kill switch)
    - ``OTEL_TRACES_EXPORTER`` is not ``none``
    - an OTLP endpoint is configured (``OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`` or
      ``OTEL_EXPORTER_OTLP_ENDPOINT``)

When off, the SDK is never imported, no global TracerProvider is installed,
and the API's no-op tracer is used: spans cost a function call, attributes are
never built (callers guard on ``span.is_recording()``), and no trace context is
extracted from or injected into MCP ``_meta`` (the wire format is unchanged).

When on, spans go to an OTLP/HTTP (protobuf) exporter through a
BatchSpanProcessor. The exporter reads the standard ``OTEL_EXPORTER_OTLP_*``
env vars itself (endpoint, headers, timeout, compression).

Semantic conventions
--------------------
Span names and attributes follow the OpenTelemetry GenAI + MCP semantic
conventions, which are **Development** status (no tagged release) and live in
https://github.com/open-telemetry/semantic-conventions-genai
Followed as of commit f3c6d0c9bb66ebd474668a3a0be25c61226f02c2 (2026-10-14),
docs/gen-ai/mcp.md and docs/gen-ai/gen-ai-spans.md, which reference core
semconv v1.44.0. Attribute names are string literals here (not imported from
``opentelemetry-semantic-conventions``) because the GenAI/MCP names are still
moving; re-check them against that repo when bumping.

Content capture: ``gen_ai.tool.call.arguments`` / ``.result`` are Opt-In per
the semconv and are only recorded when ``OTEL_CAPTURE_TOOL_CONTENT=true``.
Arguments are always the *client-supplied* values (vault placeholders such as
``{{GITHUB_TOKEN}}`` unresolved), never the secret-injected ones.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping, MutableMapping
from typing import Any

from opentelemetry import propagate, trace
from opentelemetry.context import Context
from opentelemetry.trace import Link, Span, Tracer

logger = logging.getLogger(__name__)

SEMCONV_GENAI_COMMIT = "f3c6d0c9bb66ebd474668a3a0be25c61226f02c2"
SEMCONV_CORE_VERSION = "1.44.0"

_INSTRUMENTATION_NAME = "arbiter.gateway"
_DEFAULT_SERVICE_NAME = "arbiter-gateway"
# Cap opt-in content attributes so one huge tool result can't blow the span.
_MAX_CONTENT_CHARS = 8192

_enabled = False
_capture_content = False
_provider: Any = None  # opentelemetry.sdk.trace.TracerProvider when enabled


def is_enabled() -> bool:
    """True when tracing was configured with a real exporter."""
    return _enabled


def capture_content() -> bool:
    """True when opt-in tool argument/result capture is on (and tracing is on)."""
    return _enabled and _capture_content


def get_tracer() -> Tracer:
    """
    Return the gateway tracer.

    Resolved on each call (not cached at import) so it always reflects the
    current global provider: the no-op proxy when disabled.
    """
    return trace.get_tracer(_INSTRUMENTATION_NAME)


def _env_true(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() == "true"


def tracing_requested(otel_enabled: bool) -> bool:
    """Decide from app config + standard OTel env vars whether to export traces."""
    if not otel_enabled or _env_true("OTEL_SDK_DISABLED"):
        return False
    if os.environ.get("OTEL_TRACES_EXPORTER", "").strip().lower() == "none":
        return False
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    if not endpoint:
        logger.warning(
            "otel: OTEL_ENABLED=true but no OTEL_EXPORTER_OTLP_ENDPOINT is set: tracing stays off"
        )
        return False
    return True


def configure_telemetry(
    otel_enabled: bool,
    capture_tool_content: bool = False,
    span_exporter: Any = None,
) -> bool:
    """
    Install the SDK TracerProvider if tracing is requested. Idempotent.

    Args:
        otel_enabled:          The ``OTEL_ENABLED`` app setting.
        capture_tool_content:  The ``OTEL_CAPTURE_TOOL_CONTENT`` app setting.
        span_exporter:         Override exporter (tests pass an
                               InMemorySpanExporter; it is wrapped in a
                               SimpleSpanProcessor and skips the endpoint check).

    Returns:
        True if tracing is now enabled.
    """
    global _enabled, _capture_content, _provider

    if _enabled:
        return True
    if span_exporter is None and not tracing_requested(otel_enabled):
        return False

    # Imported lazily so a disabled gateway never loads the SDK.
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

    # Resource.create() lets explicit attributes win over OTEL_RESOURCE_ATTRIBUTES,
    # so only supply the default service name when OTEL_SERVICE_NAME is unset.
    attrs: dict[str, Any] = {}
    if not os.environ.get("OTEL_SERVICE_NAME"):
        attrs["service.name"] = _DEFAULT_SERVICE_NAME
    provider = TracerProvider(resource=Resource.create(attrs))

    if span_exporter is not None:
        provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    else:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

    trace.set_tracer_provider(provider)
    _provider = provider
    _enabled = True
    _capture_content = capture_tool_content
    logger.info(
        "otel: tracing enabled (semconv-genai@%s, content capture %s)",
        SEMCONV_GENAI_COMMIT[:7],
        "on" if capture_tool_content else "off",
    )
    return True


def shutdown_telemetry() -> None:
    """Flush and shut down the provider (app shutdown)."""
    global _enabled, _provider
    if _provider is not None:
        try:
            _provider.shutdown()
        except Exception as exc:  # pragma: no cover - best effort on exit
            logger.warning("otel: provider shutdown failed: %s", exc)
    _provider = None
    _enabled = False


# ── Context propagation (MCP params._meta, W3C Trace Context) ─────────────────


def extract_mcp_context(meta: Any, headers: Mapping[str, str]) -> tuple[Context | None, list[Link]]:
    """
    Resolve the parent context for an MCP SERVER span.

    Per the MCP semconv the context in ``params._meta`` (traceparent /
    tracestate / baggage) is the parent; the HTTP transport context, if any,
    is attached as a span link. If ``_meta`` carries no trace context, the
    HTTP ``traceparent`` header is used as the parent instead.

    Returns (None, []) when tracing is disabled: nothing is parsed.
    """
    if not _enabled:
        return None, []

    header_ctx = propagate.extract({k.lower(): v for k, v in headers.items()})
    header_sc = trace.get_current_span(header_ctx).get_span_context()

    if isinstance(meta, dict) and "traceparent" in meta:
        carrier = {k: v for k, v in meta.items() if isinstance(v, str)}
        meta_ctx = propagate.extract(carrier)
        meta_sc = trace.get_current_span(meta_ctx).get_span_context()
        if meta_sc.is_valid:
            links: list[Link] = []
            if header_sc.is_valid and header_sc.span_id != meta_sc.span_id:
                links.append(Link(header_sc))
            return meta_ctx, links

    if header_sc.is_valid:
        return header_ctx, []
    return None, []


def inject_mcp_meta(meta: MutableMapping[str, Any]) -> None:
    """Write the current trace context into an outbound MCP ``_meta`` bag (no-op when off)."""
    if _enabled:
        propagate.inject(meta)


def current_trace_id_hex() -> str | None:
    """Hex trace id of the active span, or None when there is no recording span."""
    if not _enabled:
        return None
    sc = trace.get_current_span().get_span_context()
    return format(sc.trace_id, "032x") if sc.is_valid else None


def set_content_attribute(span: Span, key: str, value: Any) -> None:
    """Record an opt-in content attribute as a (truncated) JSON string, if capture is on."""
    if not capture_content() or not span.is_recording():
        return
    try:
        text = json.dumps(value, default=str)
    except (TypeError, ValueError):
        return
    if len(text) > _MAX_CONTENT_CHARS:
        text = text[:_MAX_CONTENT_CHARS] + "...[truncated]"
    span.set_attribute(key, text)
