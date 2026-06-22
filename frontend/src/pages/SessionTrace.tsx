/**
 * Arbiter: Session Trace View.
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
import { Link } from "react-router-dom";
import { authClient } from "../api/client";
import type { Agent, ChainNode, Session, SessionEvent, Page } from "../api/types";
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
      className={`font-mono text-xs px-2 py-1 border border-border bg-surface ${colorClass}`}
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
  isSelected: boolean;
  onToggle: () => void;
}

function TraceRow({
  event,
  barLeftPct,
  barWidthPct,
  isExpanded,
  isSelected,
  onToggle,
}: TraceRowProps): React.ReactElement {
  const isError = !!event.error;
  const isCacheHit = event.cache_hit;

  const dotColor = isError
    ? "text-error"
    : isCacheHit
    ? "text-success"
    : "text-accent-light";

  const barColor = isError
    ? "bg-error/60"
    : isCacheHit
    ? "bg-success/40"
    : "bg-accent/60";

  return (
    <>
      <tr
        className={`border-b border-border cursor-pointer group transition-colors ${
          isSelected
            ? "bg-accent/10 border-accent/30"
            : isError
            ? "bg-error/8"
            : "hover:bg-elevated"
        }`}
        onClick={onToggle}
      >
        {/* Column 1: tool name */}
        <td className="py-2 pr-4 pl-0 w-[200px]">
          <span
            className={`font-mono text-xs flex items-center gap-1.5 ${
              isError ? "text-error" : "text-accent-light"
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
                  ? "bg-success/10 border-success/20 text-success"
                  : "bg-elevated border-border text-muted"
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
        <tr className="border-b border-border">
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
                  <p className="text-error text-xs font-mono">
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

// ── Diff helpers ──────────────────────────────────────────────────────────────

function diffLines(a: string, b: string): Array<{ type: "same" | "add" | "remove"; text: string }> {
  const la = a.split("\n");
  const lb = b.split("\n");
  const result: Array<{ type: "same" | "add" | "remove"; text: string }> = [];
  const maxLen = Math.max(la.length, lb.length);
  for (let i = 0; i < maxLen; i++) {
    const lineA = la[i];
    const lineB = lb[i];
    if (lineA === lineB) {
      result.push({ type: "same", text: lineA ?? "" });
    } else {
      if (lineA !== undefined) result.push({ type: "remove", text: lineA });
      if (lineB !== undefined) result.push({ type: "add", text: lineB });
    }
  }
  return result;
}

interface DiffPanelProps {
  eventA: SessionEvent;
  eventB: SessionEvent;
  onClose: () => void;
}

function DiffPanel({ eventA, eventB, onClose }: DiffPanelProps): React.ReactElement {
  const [field, setField] = useState<"request" | "response">("request");

  const aStr = JSON.stringify(field === "request" ? eventA.request_payload : eventA.response_payload, null, 2) ?? "null";
  const bStr = JSON.stringify(field === "request" ? eventB.request_payload : eventB.response_payload, null, 2) ?? "null";
  const lines = diffLines(aStr, bStr);
  const hasChanges = lines.some((l) => l.type !== "same");

  return (
    <div className="mt-6 border border-border rounded-xl overflow-hidden bg-surface">
      <div className="flex items-center justify-between px-5 py-3 border-b border-border">
        <div className="flex items-center gap-3">
          <span className="text-primary text-xs font-semibold">Compare Events</span>
          <span className="text-muted text-xs font-mono">{eventA.tool_name}</span>
          <span className="text-muted text-xs">vs</span>
          <span className="text-muted text-xs font-mono">{eventB.tool_name}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="inline-flex border border-border rounded-lg overflow-hidden">
            {(["request", "response"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setField(f)}
                className={`px-3 py-1 text-xs font-medium transition-all ${
                  field === f ? "bg-accent/15 text-accent-light" : "text-muted hover:text-secondary"
                }`}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
          <button onClick={onClose} className="text-muted hover:text-secondary text-xs px-2 py-1 rounded hover:bg-elevated transition-all">
            Close
          </button>
        </div>
      </div>

      {!hasChanges ? (
        <div className="py-8 text-center text-secondary text-xs font-mono">No differences in {field} payload</div>
      ) : (
        <pre className="text-xs font-mono p-4 overflow-x-auto leading-relaxed">
          {lines.map((line, i) => (
            <div
              key={i}
              className={
                line.type === "add"
                  ? "bg-success/10 text-success"
                  : line.type === "remove"
                  ? "bg-error/10 text-error"
                  : "text-secondary"
              }
            >
              <span className="select-none text-muted mr-2">
                {line.type === "add" ? "+" : line.type === "remove" ? "-" : " "}
              </span>
              {line.text}
            </div>
          ))}
        </pre>
      )}
    </div>
  );
}

// ── Call chain tree ───────────────────────────────────────────────────────────

function ChainNodeRow({
  node,
  depth,
  currentId,
}: {
  node: ChainNode;
  depth: number;
  currentId: string;
}): React.ReactElement {
  const isCurrent = node.id === currentId;
  return (
    <>
      <div
        className={`flex items-center gap-2 py-1.5 px-3 rounded-lg transition-colors ${
          isCurrent ? "bg-accent/10 border border-accent/20" : "hover:bg-elevated"
        }`}
        style={{ paddingLeft: `${12 + depth * 20}px` }}
      >
        {depth > 0 && (
          <span className="text-border font-mono text-xs select-none">└─</span>
        )}
        <span className="w-1.5 h-1.5 rounded-full bg-accent/60 flex-shrink-0" />
        {isCurrent ? (
          <span className="font-mono text-xs text-accent-light font-semibold truncate">
            {node.id.slice(0, 8)}…
          </span>
        ) : (
          <Link
            to={`/sessions/${node.id}`}
            className="font-mono text-xs text-secondary hover:text-primary transition-colors truncate"
          >
            {node.id.slice(0, 8)}…
          </Link>
        )}
        <span className="text-muted text-[10px] font-mono ml-auto flex-shrink-0">
          {node.event_count} call{node.event_count !== 1 ? "s" : ""}
        </span>
        {isCurrent && (
          <span className="text-[10px] font-mono text-accent-light bg-accent/10 border border-accent/20 rounded px-1.5 py-0.5 flex-shrink-0">
            current
          </span>
        )}
      </div>
      {node.children.map((child) => (
        <ChainNodeRow key={child.id} node={child} depth={depth + 1} currentId={currentId} />
      ))}
    </>
  );
}

function CallChainPanel({ sessionId, traceId }: { sessionId: string; traceId: string }): React.ReactElement | null {
  const [expanded, setExpanded] = useState(false);

  const { data: chain } = useQuery<ChainNode>({
    queryKey: ["session-chain", sessionId],
    queryFn: () => authClient.get<ChainNode>(`/sessions/${sessionId}/chain`).then((r) => r.data),
    enabled: expanded,
  });

  const isChained = traceId !== sessionId;

  if (!isChained && !expanded) {
    return null;
  }

  return (
    <div className="mb-6 border border-accent/20 rounded-xl overflow-hidden bg-surface">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-3 px-5 py-3 text-left hover:bg-accent/5 transition-colors"
      >
        <span className="text-accent-light text-xs font-mono font-semibold">Agent Call Chain</span>
        <span className="text-muted text-xs font-mono">trace {traceId.slice(0, 8)}…</span>
        <span className="ml-auto text-muted text-xs">{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded && (
        <div className="px-3 pb-3 pt-1 border-t border-border">
          {chain == null ? (
            <div className="py-4 text-center text-muted text-xs font-mono">Loading chain…</div>
          ) : (
            <ChainNodeRow node={chain} depth={0} currentId={sessionId} />
          )}
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function SessionTrace(): React.ReactElement {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);
  const [compareMode, setCompareMode] = useState(false);
  const [compareSelected, setCompareSelected] = useState<string[]>([]);

  const { data: session, isLoading } = useQuery<Session>({
    queryKey: ["session", id],
    queryFn: () => authClient.get<Session>(`/sessions/${id}`).then((r) => r.data),
    enabled: !!id,
  });

  const { data: agentsPage } = useQuery<Page<Agent>>({
    queryKey: ["agents"],
    queryFn: () => authClient.get<Page<Agent>>("/agents").then((r) => r.data),
  });

  const agent = agentsPage?.items.find((a) => a.id === session?.agent_id);
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
      ? "text-success"
      : cacheHitRate >= 40
      ? "text-warning"
      : "text-error";

  const errorColor = errorCount > 0 ? "text-error" : "text-muted";

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

      {/* Call chain: shown when this session is part of a multi-hop trace */}
      {session.trace_id && (
        <CallChainPanel sessionId={session.id} traceId={session.trace_id} />
      )}

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

        {/* Stat pills + Compare toggle */}
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <StatPill label={`${events.length} calls`} />
          <StatPill label={`${errorCount} errors`} colorClass={errorColor} />
          <StatPill label={`${cacheHitRate}% cached`} colorClass={cacheRateColor} />
          <StatPill label={`${totalDuration}ms total`} />
          {events.length >= 2 && (
            <button
              onClick={() => { setCompareMode((m) => !m); setCompareSelected([]); }}
              className={`px-3 py-1 rounded-full text-xs font-medium border transition-all ${
                compareMode
                  ? "bg-accent/15 text-accent-light border-accent/30"
                  : "border-border text-muted hover:text-secondary"
              }`}
            >
              {compareMode ? "Exit Compare" : "Compare"}
            </button>
          )}
        </div>
      </div>

      {/* Summary strip */}
      <div className="bg-surface border-y border-border px-6 py-3 mb-8">
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
      <div className="flex items-center justify-between mb-4">
        <p className="text-secondary text-xs uppercase tracking-widest">Timeline</p>
        {compareMode && (
          <p className="text-muted text-xs font-mono">
            {compareSelected.length === 0 && "Select two events to compare"}
            {compareSelected.length === 1 && "Select one more event"}
            {compareSelected.length === 2 && "↓ Diff below"}
          </p>
        )}
      </div>

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
              const isCompareSelected = compareSelected.includes(event.id);

              return (
                <TraceRow
                  key={event.id}
                  event={event}
                  barLeftPct={barLeftPct}
                  barWidthPct={barWidthPct}
                  isExpanded={!compareMode && expandedEventId === event.id}
                  isSelected={isCompareSelected}
                  onToggle={() => {
                    if (compareMode) {
                      setCompareSelected((prev) => {
                        if (prev.includes(event.id)) return prev.filter((x) => x !== event.id);
                        if (prev.length >= 2) return [prev[1], event.id];
                        return [...prev, event.id];
                      });
                    } else {
                      setExpandedEventId((prev) => prev === event.id ? null : event.id);
                    }
                  }}
                />
              );
            })}
          </tbody>
        </table>
      )}

      {/* Diff panel */}
      {compareMode && compareSelected.length === 2 && (() => {
        const evA = events.find((e) => e.id === compareSelected[0]);
        const evB = events.find((e) => e.id === compareSelected[1]);
        return evA && evB ? (
          <DiffPanel
            eventA={evA}
            eventB={evB}
            onClose={() => setCompareSelected([])}
          />
        ) : null;
      })()}
    </div>
  );
}

export default SessionTrace;
