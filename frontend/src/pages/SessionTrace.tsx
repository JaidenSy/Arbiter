/**
 * NexusAI — Session Trace View.
 *
 * Full waterfall timeline for a single session.
 * Route: /sessions/:id
 *
 * Shows:
 *   - Session header with stat pills
 *   - Summary strip with aggregate metrics
 *   - Per-event waterfall timeline with expandable request/response detail
 */

import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { authClient } from "../api/client";
import type { Agent, Session, SessionEvent } from "../api/types";
import JsonViewer from "../components/JsonViewer";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function hasSecretPlaceholder(payload: Record<string, unknown> | null): boolean {
  return JSON.stringify(payload ?? {}).includes("{{");
}

// ── Stat pill ─────────────────────────────────────────────────────────────────

interface StatPillProps {
  label: string;
  colorClass?: string;
}

function StatPill({ label, colorClass = "text-secondary" }: StatPillProps): React.ReactElement {
  return (
    <span
      className={`font-mono text-xs px-2 py-1 border border-white/[0.07] bg-surface ${colorClass}`}
    >
      {label}
    </span>
  );
}

// ── Trace row ─────────────────────────────────────────────────────────────────

interface TraceRowProps {
  event: SessionEvent;
  barLeftPct: number;
  barWidthPct: number;
  isExpanded: boolean;
  onToggle: () => void;
}

function TraceRow({
  event,
  barLeftPct,
  barWidthPct,
  isExpanded,
  onToggle,
}: TraceRowProps): React.ReactElement {
  const isError = !!event.error;
  const isCacheHit = event.cache_hit;

  const dotColor = isError
    ? "text-red-400"
    : isCacheHit
    ? "text-green-400"
    : "text-violet-400";

  const barColor = isError
    ? "bg-red-500/60"
    : isCacheHit
    ? "bg-green-800"
    : "bg-violet-600/60";

  return (
    <>
      <tr
        className={`border-b border-white/[0.07] cursor-pointer group transition-colors ${
          isError ? "bg-red-950/20" : "hover:bg-elevated"
        }`}
        onClick={onToggle}
      >
        {/* Column 1: tool name */}
        <td className="py-2 pr-4 pl-0 w-[200px]">
          <span
            className={`font-mono text-xs flex items-center gap-1.5 ${
              isError ? "text-red-400" : "text-violet-300"
            }`}
            title={event.tool_name}
          >
            <span className={dotColor}>●</span>
            <span className="truncate max-w-[168px] block">{event.tool_name}</span>
          </span>
        </td>

        {/* Column 2: server name */}
        <td className="py-2 pr-4 w-[140px]">
          <span className="text-muted text-xs truncate block max-w-[128px]" title={event.mcp_server_name ?? "unknown"}>
            {event.mcp_server_name ?? "unknown"}
          </span>
        </td>

        {/* Column 3: waterfall bar + badges + duration */}
        <td className="py-2">
          <div className="flex items-center gap-2">
            {/* Waterfall bar */}
            <div className="relative h-5 flex-1">
              {/* Track */}
              <div className="absolute inset-0 bg-white/5 rounded-sm" />
              {/* Bar */}
              <div
                className={`absolute top-0.5 bottom-0.5 rounded-sm ${barColor}`}
                style={{
                  left: `${barLeftPct}%`,
                  width: `${barWidthPct}%`,
                }}
              />
            </div>

            {/* Cache badge */}
            <span
              className={`font-mono text-[10px] px-1.5 py-0.5 border ${
                isCacheHit
                  ? "bg-green-900/50 border-green-700/50 text-green-400"
                  : "bg-white/5 border-white/10 text-muted"
              }`}
            >
              {isCacheHit ? "HIT" : "MISS"}
            </span>

            {/* Secret placeholder indicator */}
            {hasSecretPlaceholder(event.request_payload) && (
              <span title="Secret injected" className="text-amber-400 text-xs select-none">
                🔑
              </span>
            )}

            {/* Duration */}
            <span className="font-mono text-xs text-muted ml-1 whitespace-nowrap">
              {event.duration_ms !== null ? `${event.duration_ms}ms` : "—"}
            </span>
          </div>
        </td>
      </tr>

      {/* Expanded detail */}
      {isExpanded && (
        <tr className="border-b border-white/[0.07]">
          <td colSpan={3} className="p-0">
            <div className="grid grid-cols-2 gap-4 p-4 bg-surface">
              <div>
                <p className="text-muted text-[10px] font-mono uppercase tracking-widest mb-2">
                  Request
                </p>
                <JsonViewer data={event.request_payload} />
              </div>
              <div>
                <p className="text-muted text-[10px] font-mono uppercase tracking-widest mb-2">
                  Response
                </p>
                <JsonViewer data={event.response_payload} />
              </div>
              {event.error && (
                <div className="col-span-2">
                  <p className="text-red-400 text-xs font-mono">
                    Error: {event.error}
                  </p>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function SessionTrace(): React.ReactElement {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);

  const { data: session, isLoading } = useQuery<Session>({
    queryKey: ["session", id],
    queryFn: () => authClient.get<Session>(`/sessions/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  const { data: agents } = useQuery<Agent[]>({
    queryKey: ["agents"],
    queryFn: () => authClient.get<Agent[]>("/agents").then((r) => r.data),
  });

  const agent = agents?.find((a) => a.id === session?.agent_id);
  const events: SessionEvent[] = session?.events ?? [];

  // ── Derived stats ────────────────────────────────────────────────────────────

  const errorCount = events.filter((e) => !!e.error).length;
  const cacheHits = events.filter((e) => e.cache_hit).length;
  const cacheHitRate =
    events.length > 0 ? Math.round((cacheHits / events.length) * 100) : 0;
  const totalDuration = events.reduce((sum, e) => sum + (e.duration_ms ?? 0), 0);
  const cacheSavingsMs = events
    .filter((e) => e.cache_hit)
    .reduce((sum, e) => sum + (e.duration_ms ?? 0), 0);

  // ── Waterfall calculations ────────────────────────────────────────────────────

  const timestamps = events.map((e) => new Date(e.occurred_at).getTime());
  const t0 = timestamps.length > 0 ? Math.min(...timestamps) : 0;

  const waterfallData = events.map((e) => {
    const barLeft = new Date(e.occurred_at).getTime() - t0;
    const barWidth = e.duration_ms ?? 1;
    return { barLeft, barWidth };
  });

  const maxTime =
    waterfallData.length > 0
      ? Math.max(...waterfallData.map((d) => d.barLeft + d.barWidth))
      : 1;

  // ── Color helpers ─────────────────────────────────────────────────────────────

  const cacheRateColor =
    cacheHitRate >= 70
      ? "text-green-400"
      : cacheHitRate >= 40
      ? "text-amber-400"
      : "text-red-400";

  const errorColor = errorCount > 0 ? "text-red-400" : "text-muted";

  // ── Loading skeleton ─────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="mb-6">
          <div className="animate-pulse bg-elevated h-4 w-32 rounded mb-8" />
        </div>
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="animate-pulse bg-elevated h-6 rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="p-8">
        <p className="text-secondary text-sm font-mono">Session not found.</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Back button */}
      <button
        onClick={() => navigate("/sessions")}
        className="text-secondary text-xs font-mono hover:text-primary transition-colors mb-8 flex items-center gap-1"
      >
        ← Back to Sessions
      </button>

      {/* Session header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <p className="font-mono text-xs text-muted mb-1">{session.id}</p>
          <p className="text-primary text-sm">
            Agent:{" "}
            <span className="font-semibold">{agent?.name ?? session.agent_id.slice(0, 8)}</span>
          </p>
          <p className="text-secondary text-xs mt-1">
            Started: {formatDateTime(session.started_at)}
            <span className="ml-2 text-muted">({relativeTime(session.started_at)})</span>
          </p>
        </div>

        {/* Stat pills */}
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <StatPill label={`${events.length} calls`} />
          <StatPill label={`${errorCount} errors`} colorClass={errorColor} />
          <StatPill label={`${cacheHitRate}% cached`} colorClass={cacheRateColor} />
          <StatPill label={`${totalDuration}ms total`} />
        </div>
      </div>

      {/* Summary strip */}
      <div className="bg-surface border-y border-white/[0.07] px-6 py-3 mb-8">
        <p className="font-mono text-xs text-secondary">
          Total: {totalDuration}ms
          <span className="mx-2 text-muted">·</span>
          Cached: {cacheHits}/{events.length}
          <span className="mx-2 text-muted">·</span>
          Cache saved: ~{cacheSavingsMs}ms
          <span className="mx-2 text-muted">·</span>
          Errors: {errorCount}
        </p>
      </div>

      {/* Timeline */}
      <p className="text-secondary text-xs uppercase tracking-widest mb-4">Timeline</p>

      {events.length === 0 ? (
        <div className="text-secondary text-sm py-12 text-center">
          No events recorded for this session.
        </div>
      ) : (
        <table className="w-full table-fixed">
          <colgroup>
            <col className="w-[200px]" />
            <col className="w-[140px]" />
            <col />
          </colgroup>
          <tbody>
            {events.map((event, i) => {
              const { barLeft, barWidth } = waterfallData[i];
              const barLeftPct = maxTime > 0 ? (barLeft / maxTime) * 100 : 0;
              const barWidthPct = maxTime > 0 ? Math.max((barWidth / maxTime) * 100, 0.5) : 0.5;

              return (
                <TraceRow
                  key={event.id}
                  event={event}
                  barLeftPct={barLeftPct}
                  barWidthPct={barWidthPct}
                  isExpanded={expandedEventId === event.id}
                  onToggle={() =>
                    setExpandedEventId((prev) =>
                      prev === event.id ? null : event.id
                    )
                  }
                />
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default SessionTrace;
