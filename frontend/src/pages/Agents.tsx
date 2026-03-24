/**
 * NexusAI — Agents page.
 *
 * Lists registered agents and allows:
 *   - Registering a new agent (form modal → one-time API key modal)
 *   - Deactivating (deleting) an agent via a confirmation dialog
 */

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import type { Agent, AgentCreateResponse } from "../api/types";
import CopyButton from "../components/CopyButton";
import Modal from "../components/Modal";
import ConfirmDialog from "../components/ConfirmDialog";

// ── Data fetchers / mutators ──────────────────────────────────────────────────

const fetchAgents = (): Promise<Agent[]> =>
  apiClient.get<Agent[]>("/agents").then((r) => r.data);

const createAgent = (payload: {
  name: string;
  description: string;
}): Promise<AgentCreateResponse> =>
  apiClient.post<AgentCreateResponse>("/agents", payload).then((r) => r.data);

const deleteAgent = (id: string): Promise<void> =>
  apiClient.delete(`/agents/${id}`).then(() => undefined);

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
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: createAgent,
    onSuccess: (data) => {
      setName("");
      setDescription("");
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
    mutation.mutate({ name: name.trim(), description: description.trim() });
  };

  const handleClose = (): void => {
    setName("");
    setDescription("");
    setError(null);
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Register Agent">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="agent-name"
            className="block text-sm text-secondary mb-1"
          >
            Name <span className="text-error">*</span>
          </label>
          <input
            id="agent-name"
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. my-agent"
            className="w-full bg-elevated border border-white/[0.14] text-primary text-sm px-3 py-1.5 rounded focus:outline-none focus:border-accent focus:ring-0"
          />
        </div>

        <div>
          <label
            htmlFor="agent-desc"
            className="block text-sm text-secondary mb-1"
          >
            Description
          </label>
          <textarea
            id="agent-desc"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description…"
            className="w-full bg-elevated border border-white/[0.14] text-primary text-sm px-3 py-1.5 rounded focus:outline-none focus:border-accent focus:ring-0 resize-none"
          />
        </div>

        {error && <p className="text-sm text-error">{error}</p>}

        <div className="flex justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={handleClose}
            className="text-secondary hover:text-primary hover:bg-elevated px-3 py-1.5 rounded text-sm transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={mutation.isPending || !name.trim()}
            className="bg-accent hover:bg-violet-600 text-white text-sm font-medium px-3 py-1.5 rounded disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
  onDismiss: () => void;
}

function ApiKeyModal({
  isOpen,
  apiKey,
  onDismiss,
}: ApiKeyModalProps): React.ReactElement | null {
  return (
    <Modal isOpen={isOpen} onClose={onDismiss} title="Agent Registered">
      <div className="space-y-4">
        <div className="bg-yellow-950/40 border border-yellow-800/50 rounded p-3">
          <p className="text-sm font-semibold text-yellow-400">
            This key will not be shown again. Copy it now.
          </p>
        </div>

        <div>
          <p className="text-xs text-secondary mb-2 font-mono uppercase tracking-wider">
            API Key
          </p>
          <div className="bg-base border border-white/10 rounded p-3 flex items-start gap-2">
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
            className="bg-accent hover:bg-violet-600 text-white text-sm font-medium px-3 py-1.5 rounded transition-colors"
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
    <tr className="border-b border-white/[0.07]">
      {[1, 2, 3, 4, 5].map((i) => (
        <td key={i} className="py-2 px-4">
          <div className="h-3 bg-elevated rounded animate-pulse w-3/4" />
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
  const [deactivateTarget, setDeactivateTarget] = useState<Agent | null>(null);

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

  const handleRegisterSuccess = (response: AgentCreateResponse): void => {
    setShowRegisterModal(false);
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

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-primary text-lg font-semibold">Agents</h1>
        <button
          type="button"
          className="bg-accent hover:bg-violet-600 text-white text-sm font-medium px-3 py-1.5 rounded transition-colors"
          onClick={() => setShowRegisterModal(true)}
        >
          Register Agent
        </button>
      </div>

      {/* Table */}
      <div className="border-t border-white/[0.07]">
        <table className="min-w-full">
          <thead>
            <tr>
              <th className="py-2 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">
                Name
              </th>
              <th className="py-2 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">
                Description
              </th>
              <th className="py-2 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">
                Status
              </th>
              <th className="py-2 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">
                Created
              </th>
              <th className="py-2 px-4 text-right text-xs font-mono text-muted uppercase tracking-wider">
                Actions
              </th>
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
                <td
                  className="py-4 px-4 text-sm text-secondary font-mono"
                  colSpan={5}
                >
                  No agents registered yet.
                </td>
              </tr>
            ) : (
              agents.map((agent) => (
                <tr
                  key={agent.id}
                  className="group border-b border-white/[0.07] hover:bg-elevated transition-colors"
                >
                  <td className="py-2 px-4 text-sm text-primary">
                    {agent.name}
                  </td>
                  <td className="py-2 px-4 text-xs text-secondary">
                    {agent.description ?? (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                  <td className="py-2 px-4">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${agent.is_active ? 'bg-green-400' : 'bg-muted'}`}
                      />
                      <span className="text-xs text-secondary">
                        {agent.is_active ? "Active" : "Inactive"}
                      </span>
                    </div>
                  </td>
                  <td className="py-2 px-4 font-mono text-xs text-muted">
                    {formatDate(agent.created_at)}
                  </td>
                  <td className="py-2 px-4 text-right">
                    <button
                      type="button"
                      onClick={() => setDeactivateTarget(agent)}
                      className="opacity-0 group-hover:opacity-100 text-error hover:bg-red-500/10 px-3 py-1.5 rounded text-sm transition-all"
                    >
                      Deactivate
                    </button>
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
    </div>
  );
}

export default Agents;
