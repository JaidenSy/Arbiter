/**
 * Arbiter — Agents page.
 *
 * Lists registered agents and allows:
 *   - Registering a new agent (form modal → one-time API key modal)
 *   - Deactivating (deleting) an agent via a confirmation dialog
 */

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authClient } from "../api/client";
import type { Agent, AgentCreateResponse, AgentScope } from "../api/types";
import CopyButton from "../components/CopyButton";
import Modal from "../components/Modal";
import ConfirmDialog from "../components/ConfirmDialog";

// ── Data fetchers / mutators ──────────────────────────────────────────────────

const fetchAgents = (): Promise<Agent[]> =>
  authClient.get<Agent[]>("/agents").then((r) => r.data);

const createAgent = (payload: {
  name: string;
  description: string;
  scope: AgentScope;
}): Promise<AgentCreateResponse> =>
  authClient.post<AgentCreateResponse>("/agents", payload).then((r) => r.data);

const deleteAgent = (id: string): Promise<void> =>
  authClient.delete(`/agents/${id}`).then(() => undefined);

const rotateAgentKey = (id: string): Promise<AgentCreateResponse> =>
  authClient.post<AgentCreateResponse>(`/agents/${id}/rotate-key`).then((r) => r.data);

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

// ── Register Agent Modal ──────────────────────────────────────────────────────

interface RegisterModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (response: AgentCreateResponse) => void;
}

function RegisterModal({
  isOpen,
  onClose,
  onSuccess,
}: RegisterModalProps): React.ReactElement | null {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [scope, setScope] = useState<AgentScope>("full");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: createAgent,
    onSuccess: (data) => {
      setName("");
      setDescription("");
      setScope("full");
      setError(null);
      onSuccess(data);
    },
    onError: () => {
      setError("Failed to register agent. Please try again.");
    },
  });

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    if (!name.trim()) return;
    setError(null);
    mutation.mutate({ name: name.trim(), description: description.trim(), scope });
  };

  const handleClose = (): void => {
    setName("");
    setDescription("");
    setScope("full");
    setError(null);
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Register Agent">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="agent-name" className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">
            Name <span className="text-error normal-case">*</span>
          </label>
          <input
            id="agent-name"
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. my-agent"
            className="w-full bg-elevated border border-white/[0.1] text-primary text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/30 transition-all"
          />
        </div>

        <div>
          <label htmlFor="agent-desc" className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">
            Description
          </label>
          <textarea
            id="agent-desc"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description…"
            className="w-full bg-elevated border border-white/[0.1] text-primary text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/30 transition-all resize-none"
          />
        </div>

        <div>
          <label htmlFor="agent-scope" className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">
            Scope
          </label>
          <select
            id="agent-scope"
            value={scope}
            onChange={(e) => setScope(e.target.value as AgentScope)}
            className="w-full bg-elevated border border-white/[0.1] text-primary text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/30 transition-all"
          >
            <option value="full">Full — tool calls + vault read/write</option>
            <option value="read_only">Read Only — tool calls only, no vault writes</option>
            <option value="vault_read_only">Vault Read Only — secrets only, no tool calls</option>
          </select>
        </div>

        {error && (
          <div className="flex items-center gap-2 bg-error/8 border border-error/20 rounded-lg px-3 py-2">
            <span className="w-1.5 h-1.5 rounded-full bg-error flex-shrink-0" />
            <p className="text-error text-xs">{error}</p>
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={handleClose}
            className="text-secondary hover:text-primary hover:bg-elevated px-3 py-1.5 rounded-lg text-sm transition-all border border-white/[0.08] hover:border-white/[0.15]"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={mutation.isPending || !name.trim()}
            className="bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 text-white text-sm font-semibold px-4 py-1.5 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all hover:shadow-[0_0_16px_rgba(124,58,237,0.3)]"
          >
            {mutation.isPending ? "Registering…" : "Register"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// ── API Key Modal ─────────────────────────────────────────────────────────────

interface ApiKeyModalProps {
  isOpen: boolean;
  apiKey: string | null;
  title: string;
  onDismiss: () => void;
}

function ApiKeyModal({
  isOpen,
  apiKey,
  title,
  onDismiss,
}: ApiKeyModalProps): React.ReactElement | null {
  return (
    <Modal isOpen={isOpen} onClose={onDismiss} title={title}>
      <div className="space-y-4">
        <div className="bg-warning/8 border border-warning/25 rounded-lg p-3 flex items-start gap-2">
          <span className="text-warning mt-0.5">⚠</span>
          <p className="text-sm font-semibold text-warning">
            This key will not be shown again. Copy it now.
          </p>
        </div>

        <div>
          <p className="text-xs font-semibold text-secondary mb-2 uppercase tracking-widest">
            API Key
          </p>
          <div className="bg-base border border-white/[0.08] rounded-lg p-3 flex items-start gap-2">
            <code className="text-xs font-mono text-accent-light flex-1 break-all">
              {apiKey ?? ""}
            </code>
            <CopyButton text={apiKey ?? ""} />
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="button"
            onClick={onDismiss}
            className="bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 text-white text-sm font-semibold px-4 py-1.5 rounded-lg transition-all hover:shadow-[0_0_16px_rgba(124,58,237,0.3)]"
          >
            Dismiss
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ── Skeleton rows ─────────────────────────────────────────────────────────────

function SkeletonRow(): React.ReactElement {
  return (
    <tr className="border-b border-white/[0.05]">
      {[5, 8, 3, 4, 2].map((w, i) => (
        <td key={i} className="py-3 px-4">
          <div className="h-3 skeleton-shimmer rounded" style={{ width: `${w * 14}px` }} />
        </td>
      ))}
    </tr>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function Agents(): React.ReactElement {
  const queryClient = useQueryClient();

  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [newApiKey, setNewApiKey] = useState<string | null>(null);
  const [newApiKeyTitle, setNewApiKeyTitle] = useState('Agent Registered');
  const [deactivateTarget, setDeactivateTarget] = useState<Agent | null>(null);
  const [rotateTarget, setRotateTarget] = useState<Agent | null>(null);

  const { data: agents, isLoading } = useQuery<Agent[]>({
    queryKey: ["agents"],
    queryFn: fetchAgents,
  });

  const deactivateMutation = useMutation({
    mutationFn: deleteAgent,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["agents"] });
    },
    onError: (err) => {
      console.error("Failed to deactivate agent", err);
      void queryClient.invalidateQueries({ queryKey: ["agents"] });
    },
  });

  const rotateMutation = useMutation({
    mutationFn: rotateAgentKey,
    onSuccess: (data) => {
      setRotateTarget(null);
      setNewApiKeyTitle('New API Key');
      setNewApiKey(data.api_key);
    },
    onError: (err) => {
      console.error("Failed to rotate key", err);
    },
  });

  const handleRegisterSuccess = (response: AgentCreateResponse): void => {
    setShowRegisterModal(false);
    setNewApiKeyTitle('Agent Registered');
    setNewApiKey(response.api_key);
  };

  const handleApiKeyDismiss = (): void => {
    setNewApiKey(null);
    void queryClient.invalidateQueries({ queryKey: ["agents"] });
  };

  const handleDeactivateConfirm = (): void => {
    if (deactivateTarget) {
      deactivateMutation.mutate(deactivateTarget.id);
      setDeactivateTarget(null);
    }
  };

  const handleRotateConfirm = (): void => {
    if (rotateTarget) {
      rotateMutation.mutate(rotateTarget.id);
    }
  };

  return (
    <div className="p-8 animate-fade-in">
      {/* Page header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="gradient-text-purple text-xl font-bold">Agents</h1>
          <p className="text-secondary text-sm mt-1">Registered agent identities and their API keys</p>
        </div>
        <button
          type="button"
          className="bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-all hover:shadow-[0_0_20px_rgba(124,58,237,0.3)]"
          onClick={() => setShowRegisterModal(true)}
        >
          Register Agent
        </button>
      </div>

      {/* Table card */}
      <div className="bg-surface border border-white/[0.07] rounded-xl overflow-hidden">
        <table className="min-w-full">
          <thead>
            <tr className="border-b border-white/[0.06]">
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Name</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Description</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Status</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Scope</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Created</th>
              <th className="py-3 px-4 text-right text-xs font-mono text-muted uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <>
                <SkeletonRow />
                <SkeletonRow />
                <SkeletonRow />
              </>
            ) : !agents || agents.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-20 px-4 text-center">
                  <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
                    <svg className="text-accent-light" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <rect x="2" y="3" width="20" height="14" rx="2"/>
                      <path d="M8 21h8M12 17v4"/>
                      <circle cx="12" cy="10" r="3"/>
                    </svg>
                  </div>
                  <p className="text-primary text-sm font-medium mb-1">No agents registered yet</p>
                  <p className="text-secondary text-xs max-w-xs mx-auto mb-4">Register your first agent to start routing tool calls through Arbiter.</p>
                  <button
                    type="button"
                    onClick={() => setShowRegisterModal(true)}
                    className="bg-gradient-to-r from-accent to-violet-600 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-all hover:shadow-[0_0_16px_rgba(124,58,237,0.3)]"
                  >
                    Register Agent
                  </button>
                </td>
              </tr>
            ) : (
              agents.map((agent, idx) => (
                <tr
                  key={agent.id}
                  className={`group border-b border-white/[0.05] hover:bg-white/[0.025] transition-all duration-150 ${idx % 2 === 1 ? 'bg-white/[0.01]' : ''}`}
                >
                  <td className="py-3 px-4 text-sm font-medium text-primary">
                    {agent.name}
                  </td>
                  <td className="py-3 px-4 text-xs text-secondary">
                    {agent.description ?? (
                      <span className="text-muted italic">—</span>
                    )}
                  </td>
                  <td className="py-3 px-4">
                    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide ${
                      agent.is_active
                        ? 'bg-success/10 text-success border border-success/20'
                        : 'bg-muted/20 text-muted border border-muted/20'
                    }`}>
                      <span className={`w-1 h-1 rounded-full ${agent.is_active ? 'bg-success' : 'bg-muted'}`} />
                      {agent.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide border ${
                      agent.scope === "full"
                        ? 'bg-accent/10 text-accent border-accent/20'
                        : agent.scope === "read_only"
                        ? 'bg-warning/10 text-warning border-warning/20'
                        : 'bg-muted/10 text-muted border-muted/20'
                    }`}>
                      {agent.scope === "full" ? "Full" : agent.scope === "read_only" ? "Read Only" : "Vault RO"}
                    </span>
                  </td>
                  <td className="py-3 px-4 font-mono text-xs text-muted">
                    {formatDate(agent.created_at)}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-all">
                      <button
                        type="button"
                        onClick={() => setRotateTarget(agent)}
                        className="text-secondary hover:text-warning hover:bg-warning/10 border border-transparent hover:border-warning/20 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                      >
                        Rotate Key
                      </button>
                      <button
                        type="button"
                        onClick={() => setDeactivateTarget(agent)}
                        className="text-error hover:bg-error/10 border border-transparent hover:border-error/20 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                      >
                        Deactivate
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <RegisterModal
        isOpen={showRegisterModal}
        onClose={() => setShowRegisterModal(false)}
        onSuccess={handleRegisterSuccess}
      />

      <ApiKeyModal
        isOpen={newApiKey !== null}
        apiKey={newApiKey}
        title={newApiKeyTitle}
        onDismiss={handleApiKeyDismiss}
      />

      <ConfirmDialog
        isOpen={deactivateTarget !== null}
        onClose={() => setDeactivateTarget(null)}
        onConfirm={handleDeactivateConfirm}
        title="Deactivate Agent"
        message={`Deactivate agent "${deactivateTarget?.name ?? ""}"? This cannot be undone.`}
        confirmLabel="Deactivate"
      />

      <ConfirmDialog
        isOpen={rotateTarget !== null}
        onClose={() => setRotateTarget(null)}
        onConfirm={handleRotateConfirm}
        title="Rotate API Key"
        message={`Rotate the key for "${rotateTarget?.name ?? ""}"? The current key will stop working immediately.`}
        confirmLabel="Rotate Key"
      />
    </div>
  );
}

export default Agents;
