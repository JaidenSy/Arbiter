/**
 * Arbiter — Webhooks page (Pro+).
 *
 * Lists org webhooks. Owners/admins can create, edit, delete, and view
 * delivery logs per webhook. Secret is shown once on creation only.
 */

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authClient } from "../api/client";
import type { Webhook, WebhookCreate, WebhookCreateResponse, WebhookUpdate, DeliveryLog } from "../api/types";
import Modal from "../components/Modal";
import ConfirmDialog from "../components/ConfirmDialog";
import CopyButton from "../components/CopyButton";
import { Button } from "../components/ui";
import { useAuth } from "../context/AuthContext";

// ── Available event types (mirror backend WEBHOOK_EVENTS) ──────────────────────

const WEBHOOK_EVENTS = [
  "permission.denied",
  "quota.exceeded",
  "mcp_server.offline",
] as const;

// ── Data fetchers / mutators ──────────────────────────────────────────────────

const fetchWebhooks = (): Promise<Webhook[]> =>
  authClient.get<Webhook[]>("/webhooks").then((r) => r.data);

const createWebhook = (payload: WebhookCreate): Promise<WebhookCreateResponse> =>
  authClient.post<WebhookCreateResponse>("/webhooks", payload).then((r) => r.data);

const updateWebhook = (id: string, payload: WebhookUpdate): Promise<Webhook> =>
  authClient.patch<Webhook>(`/webhooks/${id}`, payload).then((r) => r.data);

const deleteWebhook = (id: string): Promise<void> =>
  authClient.delete(`/webhooks/${id}`).then(() => undefined);

const fetchDeliveryLogs = (id: string): Promise<DeliveryLog[]> =>
  authClient.get<DeliveryLog[]>(`/webhooks/${id}/logs`).then((r) => r.data);

// ── Helpers ───────────────────────────────────────────────────────────────────

function extractApiError(err: unknown, fallback: string): string {
  if (err && typeof err === "object" && "response" in err) {
    const r = (err as { response?: { data?: { detail?: string } } }).response;
    if (r?.data?.detail) return r.data.detail;
  }
  return fallback;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

// ── Create / Edit Modal ───────────────────────────────────────────────────────

interface WebhookFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  editTarget: Webhook | null;
}

function WebhookFormModal({ isOpen, onClose, editTarget }: WebhookFormModalProps): React.ReactElement | null {
  const queryClient = useQueryClient();
  const [url, setUrl] = useState(editTarget?.url ?? "");
  const [events, setEvents] = useState<string[]>(editTarget?.events ?? []);
  const [isActive, setIsActive] = useState(editTarget?.is_active ?? true);
  const [error, setError] = useState<string | null>(null);
  const [createdSecret, setCreatedSecret] = useState<string | null>(null);

  React.useEffect(() => {
    if (isOpen) {
      setUrl(editTarget?.url ?? "");
      setEvents(editTarget?.events ?? []);
      setIsActive(editTarget?.is_active ?? true);
      setError(null);
      setCreatedSecret(null);
    }
  }, [isOpen, editTarget]);

  const createMutation = useMutation({
    mutationFn: createWebhook,
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ["webhooks"] });
      setCreatedSecret(data.secret);
    },
    onError: (err: unknown) => setError(extractApiError(err, "Failed to create webhook.")),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: WebhookUpdate }) =>
      updateWebhook(id, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["webhooks"] });
      onClose();
    },
    onError: (err: unknown) => setError(extractApiError(err, "Failed to update webhook.")),
  });

  const isPending = createMutation.isPending || updateMutation.isPending;
  const isEditing = editTarget !== null;

  const toggleEvent = (ev: string): void => {
    setEvents((prev) =>
      prev.includes(ev) ? prev.filter((e) => e !== ev) : [...prev, ev]
    );
  };

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    if (!url.trim() || events.length === 0) return;
    setError(null);
    if (isEditing) {
      updateMutation.mutate({ id: editTarget.id, payload: { url: url.trim(), events, is_active: isActive } });
    } else {
      createMutation.mutate({ url: url.trim(), events, is_active: isActive });
    }
  };

  const inputClass = "w-full bg-base border border-border text-primary text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/30 transition-all font-mono";
  const labelClass = "block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest";

  if (createdSecret) {
    return (
      <Modal isOpen={isOpen} onClose={onClose} title="Webhook Created">
        <div className="space-y-4">
          <div className="bg-warning/8 border border-warning/20 rounded-lg px-4 py-3">
            <p className="text-warning text-xs font-semibold mb-1">Copy your signing secret now</p>
            <p className="text-secondary text-xs">This secret is shown once and cannot be retrieved again. Use it to verify webhook payloads.</p>
          </div>
          <div>
            <label className={labelClass}>Signing Secret</label>
            <div className="flex items-center gap-2">
              <code className="flex-1 bg-elevated border border-border rounded-lg px-3 py-2 text-xs font-mono text-primary break-all">
                {createdSecret}
              </code>
              <CopyButton text={createdSecret} />
            </div>
          </div>
          <div className="flex justify-end">
            <Button size="sm" onClick={onClose}>Done</Button>
          </div>
        </div>
      </Modal>
    );
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={isEditing ? "Edit Webhook" : "Add Webhook"}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="webhook-url" className={labelClass}>
            Destination URL <span className="text-error normal-case">*</span>
          </label>
          <input
            id="webhook-url"
            type="url"
            required
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://your-server.com/webhook"
            className={inputClass}
          />
        </div>

        <div>
          <label className={labelClass}>
            Events <span className="text-error normal-case">*</span>
          </label>
          <div className="space-y-2">
            {WEBHOOK_EVENTS.map((ev) => (
              <label key={ev} className="flex items-center gap-3 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={events.includes(ev)}
                  onChange={() => toggleEvent(ev)}
                  className="w-4 h-4 rounded border-border bg-base text-accent focus:ring-accent/30 focus:ring-1 cursor-pointer"
                />
                <span className="text-sm text-primary font-mono group-hover:text-accent-light transition-colors">{ev}</span>
              </label>
            ))}
          </div>
          {events.length === 0 && (
            <p className="text-xs text-muted mt-1.5">Select at least one event.</p>
          )}
        </div>

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="w-4 h-4 rounded border-border bg-base text-accent focus:ring-accent/30 focus:ring-1 cursor-pointer"
          />
          <span className="text-sm text-primary">Active</span>
        </label>

        {error && (
          <div className="flex items-center gap-2 bg-error/8 border border-error/20 rounded-lg px-3 py-2">
            <span className="w-1.5 h-1.5 rounded-full bg-error flex-shrink-0" />
            <p className="text-error text-xs">{error}</p>
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            size="sm"
            isLoading={isPending}
            disabled={isPending || !url.trim() || events.length === 0}
          >
            {isEditing ? "Save" : "Add Webhook"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

// ── Delivery Logs Panel ───────────────────────────────────────────────────────

function DeliveryLogsPanel({ webhookId, onClose }: { webhookId: string; onClose: () => void }): React.ReactElement {
  const { data: logs, isLoading } = useQuery<DeliveryLog[]>({
    queryKey: ["webhook-logs", webhookId],
    queryFn: () => fetchDeliveryLogs(webhookId),
    refetchInterval: 15_000,
  });

  return (
    <Modal isOpen onClose={onClose} title="Delivery Log">
      <div className="space-y-2 max-h-[400px] overflow-y-auto">
        {isLoading && (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 skeleton-shimmer rounded-lg" />
            ))}
          </div>
        )}
        {!isLoading && logs?.length === 0 && (
          <p className="text-secondary text-sm text-center py-6">No deliveries yet.</p>
        )}
        {logs?.map((log) => (
          <div
            key={log.id}
            className="flex items-start gap-3 bg-elevated border border-border rounded-lg px-3 py-2.5"
          >
            <span
              className={`mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${
                log.response_status && log.response_status < 300
                  ? "bg-success"
                  : log.error
                  ? "bg-error"
                  : "bg-warning"
              }`}
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-primary">{log.event_type}</span>
                {log.response_status && (
                  <span className={`text-xs font-mono ${log.response_status < 300 ? "text-success" : "text-error"}`}>
                    {log.response_status}
                  </span>
                )}
                <span className="text-xs text-muted ml-auto">{formatDate(log.delivered_at)}</span>
              </div>
              {log.error && (
                <p className="text-xs text-error mt-0.5 truncate">{log.error}</p>
              )}
              {log.attempt > 1 && (
                <p className="text-xs text-muted mt-0.5">Attempt {log.attempt}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </Modal>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function Webhooks(): React.ReactElement {
  const { user } = useAuth();
  const isPro = user?.org_plan !== "free";
  const canManage = user?.role === "owner" || user?.role === "admin";
  const queryClient = useQueryClient();

  const [formOpen, setFormOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Webhook | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Webhook | null>(null);
  const [logsTarget, setLogsTarget] = useState<string | null>(null);

  const { data: webhooks, isLoading } = useQuery<Webhook[]>({
    queryKey: ["webhooks"],
    queryFn: fetchWebhooks,
    enabled: isPro,
    refetchInterval: 30_000,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteWebhook,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["webhooks"] }),
  });

  const handleEdit = (hook: Webhook): void => {
    setEditTarget(hook);
    setFormOpen(true);
  };

  const handleFormClose = (): void => {
    setFormOpen(false);
    setEditTarget(null);
  };

  if (!isPro) {
    return (
      <div className="p-6 md:p-8 max-w-[1400px] mx-auto">
        <div className="mb-6">
          <h1 className="font-display text-primary text-xl font-semibold tracking-tight">Webhooks</h1>
        </div>
        <div className="border border-border rounded-xl bg-surface p-10 flex flex-col items-center gap-4 text-center">
          <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-accent-light">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
              <polyline points="15 3 21 3 21 9"/>
              <line x1="10" y1="14" x2="21" y2="3"/>
            </svg>
          </div>
          <div>
            <p className="text-primary font-semibold">Webhooks require Pro</p>
            <p className="text-secondary text-sm mt-1">Get real-time event notifications delivered to your endpoint.</p>
          </div>
          <a
            href="/settings?tab=billing"
            className="bg-accent hover:bg-accent-light text-white text-sm font-semibold px-5 py-2 rounded-lg transition-all hover-glow-standard"
          >
            Upgrade to Pro →
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 max-w-[1400px] mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-display text-primary text-xl font-semibold tracking-tight">Webhooks</h1>
          <p className="text-secondary text-sm mt-0.5">Real-time event notifications to your endpoint.</p>
        </div>
        {canManage && (
          <button
            onClick={() => { setEditTarget(null); setFormOpen(true); }}
            className="bg-accent hover:bg-accent-light text-white text-sm font-semibold px-4 py-2 rounded-lg transition-all hover-glow-standard"
          >
            + Add Webhook
          </button>
        )}
      </div>

      {/* Table */}
      <div className="border border-border rounded-xl bg-surface overflow-hidden">
        {isLoading ? (
          <div className="p-6 space-y-3">
            {[1, 2].map((i) => <div key={i} className="h-12 skeleton-shimmer rounded-lg" />)}
          </div>
        ) : webhooks?.length === 0 ? (
          <div className="p-10 flex flex-col items-center gap-3 text-center">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" className="text-muted">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
              <polyline points="15 3 21 3 21 9"/>
              <line x1="10" y1="14" x2="21" y2="3"/>
            </svg>
            <p className="text-secondary text-sm">No webhooks yet.</p>
            {canManage && (
              <button
                onClick={() => setFormOpen(true)}
                className="text-accent-light text-sm hover:underline transition-colors"
              >
                Add your first webhook →
              </button>
            )}
          </div>
        ) : (
          <table className="min-w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="py-3 px-5 text-left text-xs font-mono text-muted uppercase tracking-wider">URL</th>
                <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Events</th>
                <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Status</th>
                <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Created</th>
                <th className="py-3 px-4" />
              </tr>
            </thead>
            <tbody>
              {webhooks?.map((hook) => (
                <tr key={hook.id} className="border-b border-border last:border-0 hover:bg-white/[0.015] transition-colors">
                  <td className="py-3 px-5 font-mono text-sm text-primary max-w-[240px] truncate" title={hook.url}>
                    {hook.url}
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex flex-wrap gap-1">
                      {hook.events.map((ev) => (
                        <span key={ev} className="text-[11px] font-mono bg-elevated border border-border rounded px-1.5 py-0.5 text-secondary">
                          {ev}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <span className={`text-xs font-mono ${hook.is_active ? "text-success" : "text-muted"}`}>
                      {hook.is_active ? "active" : "paused"}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-xs text-muted font-mono">{formatDate(hook.created_at)}</td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2 justify-end">
                      <button
                        onClick={() => setLogsTarget(hook.id)}
                        className="text-xs text-secondary hover:text-primary transition-colors font-mono"
                      >
                        logs
                      </button>
                      {canManage && (
                        <>
                          <button
                            onClick={() => handleEdit(hook)}
                            className="text-xs text-secondary hover:text-primary transition-colors font-mono"
                          >
                            edit
                          </button>
                          <button
                            onClick={() => setDeleteTarget(hook)}
                            className="text-xs text-secondary hover:text-error transition-colors font-mono"
                          >
                            delete
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <WebhookFormModal isOpen={formOpen} onClose={handleFormClose} editTarget={editTarget} />

      {logsTarget && (
        <DeliveryLogsPanel webhookId={logsTarget} onClose={() => setLogsTarget(null)} />
      )}

      <ConfirmDialog
        isOpen={deleteTarget !== null}
        title="Delete webhook"
        message={`This will permanently delete the webhook at ${deleteTarget?.url ?? ""}. Deliveries will stop immediately.`}
        confirmLabel="Delete"
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) {
            deleteMutation.mutate(deleteTarget.id);
            setDeleteTarget(null);
          }
        }}
      />
    </div>
  );
}

export default Webhooks;
