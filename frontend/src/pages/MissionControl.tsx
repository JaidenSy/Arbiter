/**
 * Arbiter — Mission Control page.
 *
 * Three-section command center for agent ops:
 *   A. Activity Feed   — today's agent sessions (filtered from /sessions)
 *   B. Task Queue      — list / create / expand tasks against /tasks
 *   C. Agent Summary   — live agent roster with today's tool-call counts
 *
 * Gated behind the `mission_control` plan flag — free orgs see a locked
 * state with an upgrade CTA.
 */

import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authClient } from "../api/client";
import type { Agent, Page, Session } from "../api/types";
import { useAuth } from "../context/AuthContext";

// ── Local types ───────────────────────────────────────────────────────────────

type TaskStatus = "pending" | "claimed" | "done" | "failed";
type TaskPriority = "low" | "normal" | "high";

interface Task {
  id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  claimed_by_agent_id: string | null;
  output: string | null;
  created_at: string;
  claimed_at: string | null;
  completed_at: string | null;
}

interface TaskCreatePayload {
  title: string;
  description?: string | null;
  priority: TaskPriority;
}

// ── Data fetchers ─────────────────────────────────────────────────────────────

const fetchAgents = (): Promise<Page<Agent>> =>
  authClient.get<Page<Agent>>("/agents").then((r) => r.data);

const fetchTodaySessions = (): Promise<Session[]> => {
  // Today, UTC midnight onward — same time math the dashboard "today" tiles use.
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  return authClient
    .get<Page<Session>>("/sessions", {
      params: { from_date: start.toISOString(), limit: 50 },
    })
    .then((r) => r.data.items);
};

const fetchTasks = (): Promise<Page<Task>> =>
  authClient.get<Page<Task>>("/tasks", { params: { limit: 100 } }).then((r) => r.data);

// ── Helpers ───────────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function sessionDurationLabel(s: Session): string {
  if (!s.ended_at) return "active";
  const ms = new Date(s.ended_at).getTime() - new Date(s.started_at).getTime();
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${Math.round(ms / 100) / 10}s`;
  return `${Math.round(ms / 6000) / 10}m`;
}

const STATUS_BADGE: Record<TaskStatus, string> = {
  pending: "bg-warning/15 text-warning border-warning/30",
  claimed: "bg-accent/15 text-accent-light border-accent/30",
  done: "bg-success/15 text-success border-success/30",
  failed: "bg-error/15 text-error border-error/30",
};

const PRIORITY_LABEL: Record<TaskPriority, string> = {
  low: "text-muted",
  normal: "text-secondary",
  high: "text-warning",
};

// ── Locked-state (free plan) ─────────────────────────────────────────────────

function LockedState(): React.ReactElement {
  return (
    <div className="p-8 animate-fade-in">
      <div className="max-w-2xl mx-auto mt-16 bg-surface border border-white/[0.07] rounded-2xl p-10 text-center relative overflow-hidden">
        <div className="absolute -top-12 left-1/2 -translate-x-1/2 w-48 h-48 bg-accent/15 rounded-full blur-3xl pointer-events-none" />
        <div className="relative">
          <div className="w-14 h-14 rounded-2xl bg-accent/10 border border-accent/30 flex items-center justify-center mx-auto mb-6">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-accent-light">
              <rect x="3" y="11" width="18" height="11" rx="1" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          </div>
          <h1 className="gradient-text-purple text-2xl font-bold mb-2">Mission Control</h1>
          <p className="text-secondary text-sm max-w-md mx-auto mb-6">
            Queue tasks for your agents, watch live activity, and see who's online — all in one
            command center. Available on the <span className="text-accent-light font-semibold">Pro</span> plan.
          </p>
          <ul className="text-left text-sm text-secondary max-w-md mx-auto mb-8 space-y-2">
            <li>• Task queue with claim / complete lifecycle for autonomous agents</li>
            <li>• Today's activity feed across every agent in your org</li>
            <li>• Live agent summary with per-agent tool-call counts</li>
          </ul>
          <Link
            to="/settings"
            className="inline-flex items-center gap-2 bg-accent hover:bg-accent-light text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-all shadow-[0_0_18px_rgba(124,58,237,0.35)]"
          >
            Upgrade to Pro
          </Link>
        </div>
      </div>
    </div>
  );
}

// ── Activity Feed ────────────────────────────────────────────────────────────

function ActivityFeed({
  sessions,
  isLoading,
  agentMap,
}: {
  sessions: Session[];
  isLoading: boolean;
  agentMap: Map<string, string>;
}): React.ReactElement {
  return (
    <section className="bg-surface border border-white/[0.07] rounded-xl overflow-hidden">
      <header className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
        <div>
          <h2 className="text-primary text-sm font-semibold">Activity feed</h2>
          <p className="text-muted text-xs mt-0.5">Today's agent sessions</p>
        </div>
        <Link to="/sessions" className="text-accent-light hover:text-accent text-xs">
          View all →
        </Link>
      </header>
      <div className="max-h-[360px] overflow-y-auto">
        <table className="min-w-full">
          <thead>
            <tr className="border-b border-white/[0.06] sticky top-0 bg-surface">
              <th className="py-2.5 px-4 text-left text-[10px] font-mono text-muted uppercase tracking-wider">Agent</th>
              <th className="py-2.5 px-4 text-left text-[10px] font-mono text-muted uppercase tracking-wider">Started</th>
              <th className="py-2.5 px-4 text-left text-[10px] font-mono text-muted uppercase tracking-wider">Duration</th>
              <th className="py-2.5 px-4 text-left text-[10px] font-mono text-muted uppercase tracking-wider">Events</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              [1, 2, 3].map((i) => (
                <tr key={i} className="border-b border-white/[0.05]">
                  {[100, 64, 48, 32].map((w, j) => (
                    <td key={j} className="py-2.5 px-4">
                      <div className="h-3 skeleton-shimmer rounded" style={{ width: w }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : sessions.length === 0 ? (
              <tr>
                <td colSpan={4} className="py-10 text-center text-secondary text-xs">
                  No agent activity yet today.
                </td>
              </tr>
            ) : (
              sessions.map((s) => (
                <tr key={s.id} className="border-b border-white/[0.05] hover:bg-white/[0.02] transition-colors">
                  <td className="py-2.5 px-4 text-sm font-mono text-secondary">
                    {agentMap.get(s.agent_id) ?? s.agent_id.slice(0, 8)}
                  </td>
                  <td className="py-2.5 px-4 text-sm text-secondary">{relativeTime(s.started_at)}</td>
                  <td className="py-2.5 px-4 text-sm font-mono text-secondary tabular-nums">{sessionDurationLabel(s)}</td>
                  <td className="py-2.5 px-4 text-sm font-mono text-secondary tabular-nums">{s.events?.length ?? 0}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ── Task Queue ───────────────────────────────────────────────────────────────

function TaskQueue({
  tasks,
  isLoading,
  agentMap,
}: {
  tasks: Task[];
  isLoading: boolean;
  agentMap: Map<string, string>;
}): React.ReactElement {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<TaskPriority>("normal");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const createTask = useMutation<Task, Error, TaskCreatePayload>({
    mutationFn: (payload) =>
      authClient.post<Task>("/tasks", payload).then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["mission-control-tasks"] });
      setTitle("");
      setDescription("");
      setPriority("normal");
      setShowForm(false);
      setFormError(null);
    },
    onError: (err) => setFormError(err.message || "Failed to queue task"),
  });

  const deleteTask = useMutation<void, Error, string>({
    mutationFn: (id) => authClient.delete(`/tasks/${id}`).then(() => undefined),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["mission-control-tasks"] });
    },
  });

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    if (!title.trim()) {
      setFormError("Title is required");
      return;
    }
    createTask.mutate({
      title: title.trim(),
      description: description.trim() || null,
      priority,
    });
  };

  return (
    <section className="bg-surface border border-white/[0.07] rounded-xl overflow-hidden">
      <header className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
        <div>
          <h2 className="text-primary text-sm font-semibold">Task queue</h2>
          <p className="text-muted text-xs mt-0.5">Work items for your agents to pick up</p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="bg-accent/10 hover:bg-accent/20 border border-accent/30 text-accent-light text-xs font-medium px-3 py-1.5 rounded-lg transition-all"
        >
          {showForm ? "Cancel" : "+ New task"}
        </button>
      </header>

      {showForm && (
        <form onSubmit={handleSubmit} className="border-b border-white/[0.06] px-5 py-4 space-y-3 bg-elevated/30">
          <input
            type="text"
            placeholder="Task title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full bg-elevated border border-white/[0.1] text-primary text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-accent/60 transition-all"
            maxLength={255}
            autoFocus
          />
          <textarea
            placeholder="Description (optional) — what should the agent do?"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full bg-elevated border border-white/[0.1] text-primary text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-accent/60 transition-all min-h-[60px] resize-y"
          />
          <div className="flex items-center gap-3">
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as TaskPriority)}
              className="bg-elevated border border-white/[0.1] text-primary text-sm px-3 py-1.5 rounded-lg focus:outline-none focus:border-accent/60 transition-all"
            >
              <option value="low">Low priority</option>
              <option value="normal">Normal priority</option>
              <option value="high">High priority</option>
            </select>
            <button
              type="submit"
              disabled={createTask.isPending}
              className="bg-accent hover:bg-accent-light disabled:opacity-50 text-white text-sm font-medium px-4 py-1.5 rounded-lg transition-all shadow-[0_0_12px_rgba(124,58,237,0.25)]"
            >
              {createTask.isPending ? "Queueing…" : "Queue task"}
            </button>
            {formError && <span className="text-error text-xs">{formError}</span>}
          </div>
        </form>
      )}

      <div className="max-h-[420px] overflow-y-auto">
        <table className="min-w-full">
          <thead>
            <tr className="border-b border-white/[0.06] sticky top-0 bg-surface">
              <th className="py-2.5 px-4 text-left text-[10px] font-mono text-muted uppercase tracking-wider">Title</th>
              <th className="py-2.5 px-4 text-left text-[10px] font-mono text-muted uppercase tracking-wider">Status</th>
              <th className="py-2.5 px-4 text-left text-[10px] font-mono text-muted uppercase tracking-wider">Priority</th>
              <th className="py-2.5 px-4 text-left text-[10px] font-mono text-muted uppercase tracking-wider">Claimed by</th>
              <th className="py-2.5 px-4 text-left text-[10px] font-mono text-muted uppercase tracking-wider">Age</th>
              <th className="py-2.5 px-4" />
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              [1, 2, 3].map((i) => (
                <tr key={i} className="border-b border-white/[0.05]">
                  {[140, 60, 60, 80, 50, 20].map((w, j) => (
                    <td key={j} className="py-2.5 px-4">
                      <div className="h-3 skeleton-shimmer rounded" style={{ width: w }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : tasks.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-12 text-center">
                  <p className="text-primary text-sm font-medium mb-1">No tasks queued</p>
                  <p className="text-secondary text-xs">Click "New task" to give your agents something to do.</p>
                </td>
              </tr>
            ) : (
              tasks.map((task) => {
                const isExpanded = expandedId === task.id;
                return (
                  <React.Fragment key={task.id}>
                    <tr
                      className="border-b border-white/[0.05] hover:bg-white/[0.02] cursor-pointer transition-colors"
                      onClick={() => setExpandedId(isExpanded ? null : task.id)}
                    >
                      <td className="py-2.5 px-4 text-sm text-primary truncate max-w-xs">{task.title}</td>
                      <td className="py-2.5 px-4">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider border ${STATUS_BADGE[task.status]}`}>
                          {task.status}
                        </span>
                      </td>
                      <td className={`py-2.5 px-4 text-xs font-mono uppercase ${PRIORITY_LABEL[task.priority]}`}>
                        {task.priority}
                      </td>
                      <td className="py-2.5 px-4 text-sm font-mono text-secondary">
                        {task.claimed_by_agent_id
                          ? agentMap.get(task.claimed_by_agent_id) ?? task.claimed_by_agent_id.slice(0, 8)
                          : "—"}
                      </td>
                      <td className="py-2.5 px-4 text-sm text-secondary">{relativeTime(task.created_at)}</td>
                      <td className="py-2.5 px-4 text-right">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (confirm(`Delete task "${task.title}"?`)) {
                              deleteTask.mutate(task.id);
                            }
                          }}
                          className="text-muted hover:text-error text-xs transition-colors"
                          aria-label="Delete task"
                          title="Delete task"
                        >
                          ✕
                        </button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className="bg-elevated/30">
                        <td colSpan={6} className="px-4 py-4">
                          <div className="space-y-2 text-xs">
                            {task.description && (
                              <div>
                                <span className="text-muted uppercase tracking-wider font-mono">Description</span>
                                <p className="text-secondary mt-1 whitespace-pre-wrap">{task.description}</p>
                              </div>
                            )}
                            {task.output && (
                              <div>
                                <span className="text-muted uppercase tracking-wider font-mono">Output</span>
                                <pre className="text-secondary mt-1 whitespace-pre-wrap font-mono bg-base/40 border border-white/[0.05] rounded-md px-3 py-2">{task.output}</pre>
                              </div>
                            )}
                            {!task.description && !task.output && (
                              <p className="text-muted">No description or output recorded.</p>
                            )}
                            <div className="text-muted font-mono">
                              Created {relativeTime(task.created_at)}
                              {task.claimed_at && ` • Claimed ${relativeTime(task.claimed_at)}`}
                              {task.completed_at && ` • Completed ${relativeTime(task.completed_at)}`}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ── Agent Summary ────────────────────────────────────────────────────────────

function AgentSummary({
  agents,
  sessions,
  isLoading,
}: {
  agents: Agent[];
  sessions: Session[];
  isLoading: boolean;
}): React.ReactElement {
  // Tool-call count today per agent (sum events across today's sessions).
  const callsByAgent = useMemo(() => {
    const counts = new Map<string, number>();
    for (const s of sessions) {
      counts.set(s.agent_id, (counts.get(s.agent_id) ?? 0) + (s.events?.length ?? 0));
    }
    return counts;
  }, [sessions]);

  // Last-active per agent (most recent session.started_at in today's window).
  const lastActiveByAgent = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of sessions) {
      const existing = map.get(s.agent_id);
      if (!existing || new Date(s.started_at) > new Date(existing)) {
        map.set(s.agent_id, s.started_at);
      }
    }
    return map;
  }, [sessions]);

  return (
    <section className="bg-surface border border-white/[0.07] rounded-xl overflow-hidden">
      <header className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
        <div>
          <h2 className="text-primary text-sm font-semibold">Agent summary</h2>
          <p className="text-muted text-xs mt-0.5">Roster, scope, and activity today</p>
        </div>
        <Link to="/agents" className="text-accent-light hover:text-accent text-xs">
          Manage →
        </Link>
      </header>
      <div className="max-h-[360px] overflow-y-auto">
        <table className="min-w-full">
          <thead>
            <tr className="border-b border-white/[0.06] sticky top-0 bg-surface">
              <th className="py-2.5 px-4 text-left text-[10px] font-mono text-muted uppercase tracking-wider">Agent</th>
              <th className="py-2.5 px-4 text-left text-[10px] font-mono text-muted uppercase tracking-wider">Scope</th>
              <th className="py-2.5 px-4 text-left text-[10px] font-mono text-muted uppercase tracking-wider">State</th>
              <th className="py-2.5 px-4 text-left text-[10px] font-mono text-muted uppercase tracking-wider">Calls today</th>
              <th className="py-2.5 px-4 text-left text-[10px] font-mono text-muted uppercase tracking-wider">Last active</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              [1, 2].map((i) => (
                <tr key={i} className="border-b border-white/[0.05]">
                  {[120, 60, 60, 40, 80].map((w, j) => (
                    <td key={j} className="py-2.5 px-4">
                      <div className="h-3 skeleton-shimmer rounded" style={{ width: w }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : agents.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-10 text-center text-secondary text-xs">
                  No agents registered yet.{" "}
                  <Link to="/agents" className="text-accent-light hover:text-accent">Create one →</Link>
                </td>
              </tr>
            ) : (
              agents.map((agent) => {
                const lastActive = lastActiveByAgent.get(agent.id);
                return (
                  <tr key={agent.id} className="border-b border-white/[0.05] hover:bg-white/[0.02] transition-colors">
                    <td className="py-2.5 px-4 text-sm font-mono text-primary">{agent.name}</td>
                    <td className="py-2.5 px-4 text-xs font-mono text-secondary">{agent.scope}</td>
                    <td className="py-2.5 px-4">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider border ${
                          agent.is_active
                            ? "bg-success/15 text-success border-success/30"
                            : "bg-white/[0.05] text-muted border-white/[0.08]"
                        }`}
                      >
                        {agent.is_active ? "active" : "inactive"}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 text-sm font-mono text-secondary tabular-nums">
                      {callsByAgent.get(agent.id) ?? 0}
                    </td>
                    <td className="py-2.5 px-4 text-sm text-secondary">
                      {lastActive ? relativeTime(lastActive) : "—"}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function MissionControl(): React.ReactElement {
  const { user } = useAuth();
  const orgPlan = user?.org_plan ?? "free";

  // Hooks must be unconditional — fetch data even when locked, but the queries
  // are disabled so we don't pay the request cost on the free plan.
  const enabled = orgPlan !== "free";

  const { data: agentsPage, isLoading: agentsLoading } = useQuery<Page<Agent>>({
    queryKey: ["mission-control-agents"],
    queryFn: fetchAgents,
    enabled,
  });

  const { data: sessions, isLoading: sessionsLoading } = useQuery<Session[]>({
    queryKey: ["mission-control-sessions"],
    queryFn: fetchTodaySessions,
    enabled,
  });

  const { data: tasksPage, isLoading: tasksLoading } = useQuery<Page<Task>>({
    queryKey: ["mission-control-tasks"],
    queryFn: fetchTasks,
    enabled,
  });

  const agentList = agentsPage?.items ?? [];
  const sessionList = sessions ?? [];
  const taskList = tasksPage?.items ?? [];

  const agentMap = useMemo(
    () => new Map(agentList.map((a) => [a.id, a.name])),
    [agentList]
  );

  if (orgPlan === "free") {
    return <LockedState />;
  }

  return (
    <div className="p-8 animate-fade-in">
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="gradient-text-purple text-xl font-bold">Mission Control</h1>
          <p className="text-secondary text-sm mt-1">
            Queue work for your agents, watch activity in real time, and see who's online.
          </p>
        </div>
      </div>

      {/* Top row: Task queue (wider) + Agent summary */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-6">
        <div className="xl:col-span-2">
          <TaskQueue tasks={taskList} isLoading={tasksLoading} agentMap={agentMap} />
        </div>
        <div>
          <AgentSummary agents={agentList} sessions={sessionList} isLoading={agentsLoading || sessionsLoading} />
        </div>
      </div>

      {/* Bottom row: Activity feed full-width */}
      <ActivityFeed sessions={sessionList} isLoading={sessionsLoading} agentMap={agentMap} />
    </div>
  );
}

export default MissionControl;
