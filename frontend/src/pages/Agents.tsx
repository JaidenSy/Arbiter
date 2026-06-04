/**
 * Arbiter — Agents page.
 *
 * Lists registered agents and allows:
 *   - Registering a new agent (form modal → one-time API key modal)
 *   - Deactivating (deleting) an agent via a confirmation dialog
 */

import React, { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authClient } from "../api/client";
import type { Agent, AgentCreateResponse, AgentScope, MCPServer, Page } from "../api/types";
import CopyButton from "../components/CopyButton";
import Modal from "../components/Modal";
import ConfirmDialog from "../components/ConfirmDialog";
import { Button, Input } from "../components/ui";

// ── Data fetchers / mutators ──────────────────────────────────────────────────

const fetchAgents = (): Promise<Page<Agent>> =>
  authClient.get<Page<Agent>>("/agents").then((r) => r.data);

const createAgent = (payload: {
  name: string;
  description: string;
  scope: AgentScope;
  rate_limit_per_minute?: number | null;
}): Promise<AgentCreateResponse> =>
  authClient.post<AgentCreateResponse>("/agents", payload).then((r) => r.data);

const deleteAgent = (id: string): Promise<void> =>
  authClient.delete(`/agents/${id}`).then(() => undefined);

const updateAgent = (id: string, payload: { name?: string; description?: string; rate_limit_per_minute?: number | null }): Promise<Agent> =>
  authClient.patch<Agent>(`/agents/${id}`, payload).then((r) => r.data);

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
  const [rateLimit, setRateLimit] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: createAgent,
    onSuccess: (data) => {
      setName("");
      setDescription("");
      setScope("full");
      setRateLimit("");
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
    mutation.mutate({
      name: name.trim(),
      description: description.trim(),
      scope,
      rate_limit_per_minute: rateLimit.trim() !== "" ? Number(rateLimit) : null,
    });
  };

  const handleClose = (): void => {
    setName("");
    setDescription("");
    setScope("full");
    setRateLimit("");
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
          <Input
            id="agent-name"
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. my-agent"
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
            className="w-full bg-base border border-border text-primary text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-border-accent focus:ring-1 focus:ring-accent/25 transition-all resize-none"
          />
        </div>

        <div>
          <p className="block text-xs font-semibold text-secondary mb-2 uppercase tracking-widest">Scope</p>
          <div className="flex flex-col gap-2">
            {([
              { value: 'full', label: 'Full Access', desc: 'Tool calls + vault read/write' },
              { value: 'read_only', label: 'Read Only', desc: 'Tool calls only, no vault writes' },
              { value: 'vault_read_only', label: 'Vault Read Only', desc: 'Secrets access only, no tool calls' },
            ] as { value: AgentScope; label: string; desc: string }[]).map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setScope(opt.value)}
                className={`w-full text-left px-3.5 py-2.5 rounded-lg border transition-all duration-150 ${
                  scope === opt.value
                    ? 'border-accent/60 bg-accent/8 ring-1 ring-accent/25'
                    : 'border-border bg-base hover:border-border-strong hover:bg-white/[0.02]'
                }`}
              >
                <span className={`text-sm font-medium block ${scope === opt.value ? 'text-accent-light' : 'text-primary'}`}>
                  {opt.label}
                </span>
                <span className="text-xs text-secondary mt-0.5 block">{opt.desc}</span>
              </button>
            ))}
          </div>
        </div>

        <div>
          <label htmlFor="agent-rate-limit" className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">
            Rate Limit <span className="text-muted normal-case font-normal">(total calls/min, leave blank for unlimited)</span>
          </label>
          <Input
            id="agent-rate-limit"
            type="number"
            min={1}
            value={rateLimit}
            onChange={(e) => setRateLimit(e.target.value)}
            placeholder="Unlimited"
          />
        </div>

        {error && (
          <div className="flex items-center gap-2 bg-error/8 border border-error/20 rounded-lg px-3 py-2">
            <span className="w-1.5 h-1.5 rounded-full bg-error flex-shrink-0" />
            <p className="text-error text-xs">{error}</p>
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" size="sm" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            size="sm"
            isLoading={mutation.isPending}
            disabled={mutation.isPending || !name.trim()}
          >
            Register
          </Button>
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
          <div className="bg-base border border-border rounded-lg p-3 flex items-start gap-2">
            <code className="text-xs font-mono text-accent-light flex-1 break-all">
              {apiKey ?? ""}
            </code>
            <CopyButton text={apiKey ?? ""} />
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <Button size="sm" onClick={onDismiss}>Dismiss</Button>
        </div>
      </div>
    </Modal>
  );
}

// ── Test Call Modal ───────────────────────────────────────────────────────────

interface TestCallResult {
  session_id: string
  tool_name: string
  result: Record<string, unknown>
  cache_hit: boolean
  duration_ms: number | null
}

interface TestCallModalProps {
  agent: Agent | null
  onClose: () => void
}

function TestCallModal({ agent, onClose }: TestCallModalProps): React.ReactElement | null {
  const [serverName, setServerName] = useState("")
  const [toolName, setToolName] = useState("")
  const [paramsJson, setParamsJson] = useState("{}")
  const [jsonError, setJsonError] = useState<string | null>(null)
  const [result, setResult] = useState<TestCallResult | null>(null)
  const [callError, setCallError] = useState<string | null>(null)

  const { data: serversPage } = useQuery<Page<MCPServer>>({
    queryKey: ["mcp-servers"],
    queryFn: () => authClient.get<Page<MCPServer>>("/mcp-servers").then((r) => r.data),
    enabled: !!agent,
  })
  const servers = serversPage?.items ?? []

  React.useEffect(() => {
    if (agent) {
      setServerName(servers.length > 0 ? servers[0].name : "")
      setToolName("")
      setParamsJson("{}")
      setJsonError(null)
      setResult(null)
      setCallError(null)
    }
  }, [agent, servers])

  const mutation = useMutation({
    mutationFn: (payload: { server_name: string; tool_name: string; params: Record<string, unknown> }) =>
      authClient.post<TestCallResult>(`/agents/${agent!.id}/test-call`, payload).then((r) => r.data),
    onSuccess: (data) => {
      setResult(data)
      setCallError(null)
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setCallError(detail ?? "Call failed")
      setResult(null)
    },
  })

  const handleRun = (): void => {
    setJsonError(null)
    let params: Record<string, unknown> = {}
    try {
      params = JSON.parse(paramsJson) as Record<string, unknown>
    } catch {
      setJsonError("Invalid JSON")
      return
    }
    mutation.mutate({ server_name: serverName, tool_name: toolName.trim(), params })
  }

  const sharedInputClass = "w-full bg-base border border-border text-primary text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-border-accent focus:ring-1 focus:ring-accent/25 transition-all"
  const labelClass = "block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest"

  if (!agent) return null

  return (
    <Modal isOpen onClose={onClose} title={`Test Call — ${agent.name}`}>
      <div className="space-y-4">
        <div>
          <label className={labelClass}>MCP Server</label>
          <select value={serverName} onChange={(e) => setServerName(e.target.value)} className={sharedInputClass}>
            {servers.map((s) => <option key={s.id} value={s.name}>{s.name}</option>)}
            {servers.length === 0 && <option value="">No servers registered</option>}
          </select>
        </div>

        <div>
          <label className={labelClass}>Tool Name</label>
          <Input
            type="text"
            value={toolName}
            onChange={(e) => setToolName(e.target.value)}
            placeholder="e.g. echo"
            inputClassName="font-mono"
          />
        </div>

        <div>
          <label className={labelClass}>Params (JSON)</label>
          <textarea
            value={paramsJson}
            onChange={(e) => setParamsJson(e.target.value)}
            rows={4}
            className={`${sharedInputClass} font-mono resize-none`}
          />
          {jsonError && <p className="text-error text-xs mt-1">{jsonError}</p>}
        </div>

        <Button
          className="w-full"
          isLoading={mutation.isPending}
          disabled={mutation.isPending || !serverName || !toolName.trim()}
          onClick={handleRun}
        >
          Run
        </Button>

        {callError && (
          <div className="bg-error/8 border border-error/20 rounded-lg px-3 py-2">
            <p className="text-error text-xs font-mono">{callError}</p>
          </div>
        )}

        {result && (
          <div className="bg-base border border-border rounded-lg p-3 space-y-2">
            <div className="flex items-center gap-3 text-xs text-muted">
              <span className={`font-semibold ${result.cache_hit ? "text-teal-light" : "text-secondary"}`}>
                {result.cache_hit ? "⚡ Cache hit" : "↗ Live call"}
              </span>
              {result.duration_ms != null && <span>{result.duration_ms}ms</span>}
              <span className="ml-auto font-mono text-[10px]">session {result.session_id.slice(0, 8)}</span>
            </div>
            <pre className="text-xs text-primary font-mono whitespace-pre-wrap break-all overflow-auto max-h-48">
              {JSON.stringify(result.result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </Modal>
  )
}

// ── Code Snippets Modal ───────────────────────────────────────────────────────

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

function buildSnippets(apiKey: string): Record<string, string> {
  return {
    Python: `import requests

API_KEY = "${apiKey}"
BASE_URL = "${API_BASE}"

response = requests.post(
    f"{BASE_URL}/proxy/tool-call",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={
        "server_name": "your-mcp-server",
        "tool_name": "your_tool",
        "params": {},
    },
)
print(response.json())`,
    curl: `curl -X POST ${API_BASE}/proxy/tool-call \\
  -H "Authorization: Bearer ${apiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "server_name": "your-mcp-server",
    "tool_name": "your_tool",
    "params": {}
  }'`,
    TypeScript: `const response = await fetch("${API_BASE}/proxy/tool-call", {
  method: "POST",
  headers: {
    Authorization: "Bearer ${apiKey}",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    server_name: "your-mcp-server",
    tool_name: "your_tool",
    params: {},
  }),
});
const data = await response.json();
console.log(data);`,
  };
}

interface SnippetModalProps {
  agent: Agent | null;
  onClose: () => void;
}

function SnippetModal({ agent, onClose }: SnippetModalProps): React.ReactElement | null {
  const [tab, setTab] = useState<"Python" | "curl" | "TypeScript">("Python");
  if (!agent) return null;

  // We don't store raw keys — show placeholder so user fills in their own.
  const placeholder = "<YOUR_API_KEY>";
  const snippets = buildSnippets(placeholder);

  return (
    <Modal isOpen onClose={onClose} title={`Code Snippets — ${agent.name}`}>
      <div className="space-y-4">
        <p className="text-secondary text-xs">
          Replace <code className="text-accent-light bg-elevated px-1 rounded">&lt;YOUR_API_KEY&gt;</code> with the key you copied when registering this agent.
        </p>

        {/* Tab bar */}
        <div className="inline-flex border border-border rounded-lg overflow-hidden bg-elevated/50">
          {(["Python", "curl", "TypeScript"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3.5 py-1.5 text-xs font-medium transition-all duration-150 focus:outline-none ${
                tab === t
                  ? "bg-accent/15 text-accent-light"
                  : "text-muted hover:text-secondary"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Code block */}
        <div className="relative group">
          <pre className="bg-base border border-border rounded-lg p-4 text-xs font-mono text-secondary overflow-x-auto leading-relaxed whitespace-pre-wrap">
            {snippets[tab]}
          </pre>
          <div className="absolute top-2 right-2">
            <CopyButton text={snippets[tab]} />
          </div>
        </div>
      </div>
    </Modal>
  );
}

// ── Rename Modal ──────────────────────────────────────────────────────────────

interface RenameModalProps {
  agent: Agent | null;
  onClose: () => void;
  onSuccess: () => void;
}

function RenameModal({ agent, onClose, onSuccess }: RenameModalProps): React.ReactElement | null {
  const [name, setName] = useState(agent?.name ?? "");
  const [description, setDescription] = useState(agent?.description ?? "");
  const [rateLimit, setRateLimit] = useState(agent?.rate_limit_per_minute != null ? String(agent.rate_limit_per_minute) : "");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (payload: { name?: string; description?: string; rate_limit_per_minute?: number | null }) =>
      updateAgent(agent!.id, payload),
    onSuccess: () => {
      onSuccess();
      onClose();
    },
    onError: () => {
      setError("Failed to update agent. Name may already be taken.");
    },
  });

  if (!agent) return null;

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    setError(null);
    const newRateLimit = rateLimit.trim() !== "" ? Number(rateLimit) : null;
    const payload: { name?: string; description?: string; rate_limit_per_minute?: number | null } = {};
    if (name.trim() !== agent.name) payload.name = name.trim();
    if (description.trim() !== (agent.description ?? "")) payload.description = description.trim();
    if (newRateLimit !== agent.rate_limit_per_minute) payload.rate_limit_per_minute = newRateLimit;
    if (Object.keys(payload).length === 0) { onClose(); return; }
    mutation.mutate(payload);
  };

  return (
    <Modal isOpen onClose={onClose} title={`Edit Agent — ${agent.name}`}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">Name</label>
          <Input
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">Description</label>
          <textarea
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full bg-elevated border border-border text-primary text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-border-accent focus:ring-1 focus:ring-accent/25 transition-all resize-none"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">
            Rate Limit <span className="text-muted normal-case font-normal">(total calls/min, leave blank for unlimited)</span>
          </label>
          <Input
            type="number"
            min={1}
            value={rateLimit}
            onChange={(e) => setRateLimit(e.target.value)}
            placeholder="Unlimited"
          />
        </div>
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
            isLoading={mutation.isPending}
            disabled={mutation.isPending || !name.trim()}
          >
            Save
          </Button>
        </div>
      </form>
    </Modal>
  );
}

// ── Overflow menu for destructive actions ─────────────────────────────────────

interface OverflowMenuProps {
  agent:        Agent
  onRotate:     (a: Agent) => void
  onDeactivate: (a: Agent) => void
}

function OverflowMenu({ agent, onRotate, onDeactivate }: OverflowMenuProps): React.ReactElement {
  const [open, setOpen] = useState(false)
  const [menuPos, setMenuPos] = useState({ top: 0, right: 0 })
  const btnRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onMouse(e: MouseEvent): void {
      if (
        menuRef.current && !menuRef.current.contains(e.target as Node) &&
        btnRef.current && !btnRef.current.contains(e.target as Node)
      ) setOpen(false)
    }
    function onKey(e: KeyboardEvent): void {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onMouse)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onMouse)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const handleToggle = (): void => {
    if (!open && btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect()
      setMenuPos({ top: rect.bottom + 4, right: window.innerWidth - rect.right })
    }
    setOpen((o) => !o)
  }

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        aria-label="More actions"
        onClick={handleToggle}
        className="inline-flex items-center justify-center h-7 w-7 text-secondary hover:text-primary hover:bg-white/[0.05] border border-transparent hover:border-border rounded-lg text-sm transition-all"
      >
        ⋯
      </button>
      {open && createPortal(
        <div
          ref={menuRef}
          style={{ position: 'fixed', top: menuPos.top, right: menuPos.right, zIndex: 9999 }}
          className="bg-elevated border border-border-strong rounded-xl shadow-[0_8px_24px_rgba(0,0,0,0.3)] py-1 min-w-[140px]"
        >
          <button
            type="button"
            onClick={() => { onRotate(agent); setOpen(false); }}
            className="flex items-center w-full px-3 py-2 text-xs text-warning hover:bg-warning/10 transition-colors"
          >
            Rotate Key
          </button>
          <div className="border-t border-border my-0.5" />
          <button
            type="button"
            onClick={() => { onDeactivate(agent); setOpen(false); }}
            className="flex items-center w-full px-3 py-2 text-xs text-error hover:bg-error/10 transition-colors"
          >
            Deactivate
          </button>
        </div>,
        document.body
      )}
    </>
  )
}

// ── Skeleton rows ─────────────────────────────────────────────────────────────

function SkeletonRow(): React.ReactElement {
  return (
    <tr className="border-b border-border">
      {[5, 8, 3, 4, 2, 3].map((w, i) => (
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
  const [snippetAgent, setSnippetAgent] = useState<Agent | null>(null);
  const [renameAgent, setRenameAgent] = useState<Agent | null>(null);
  const [testCallAgent, setTestCallAgent] = useState<Agent | null>(null);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);
  const [bannerIsError, setBannerIsError] = useState(false);
  const bannerTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showBanner = (msg: string, isError = false): void => {
    if (bannerTimerRef.current) clearTimeout(bannerTimerRef.current);
    setBannerIsError(isError);
    setSuccessBanner(msg);
    bannerTimerRef.current = setTimeout(() => setSuccessBanner(null), 3000);
  };

  const { data: agentsPage, isLoading } = useQuery<Page<Agent>>({
    queryKey: ["agents"],
    queryFn: fetchAgents,
  });
  const agents = agentsPage?.items;

  const deactivateMutation = useMutation({
    mutationFn: deleteAgent,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["agents"] });
      void queryClient.invalidateQueries({ queryKey: ["stats"] });
      void queryClient.invalidateQueries({ queryKey: ["billing-status"] });
      showBanner('Agent deactivated');
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
      showBanner('Failed to rotate key — please try again.', true);
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
    void queryClient.invalidateQueries({ queryKey: ["stats"] });
    void queryClient.invalidateQueries({ queryKey: ["billing-status"] });
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
      {successBanner && (
        <div className={`fixed top-4 right-4 z-50 flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm shadow-lg animate-fade-in border ${
          bannerIsError
            ? 'bg-error/10 border-error/20 text-error'
            : 'bg-success/10 border-success/20 text-success'
        }`}>
          {bannerIsError
            ? <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            : <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
          }
          {successBanner}
        </div>
      )}
      {/* Page header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight text-primary">Agents</h1>
          <p className="text-secondary text-sm mt-1">Registered agent identities and their API keys</p>
        </div>
        <Button onClick={() => setShowRegisterModal(true)}>
          Register Agent
        </Button>
      </div>

      {/* Table card */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Name</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Description</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Status</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Scope</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Rate Limit</th>
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
                <td colSpan={6} className="py-20 px-4 text-center">
                  <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
                    <svg className="text-accent-light" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <rect x="2" y="3" width="20" height="14" rx="2"/>
                      <path d="M8 21h8M12 17v4"/>
                      <circle cx="12" cy="10" r="3"/>
                    </svg>
                  </div>
                  <p className="text-primary text-sm font-medium mb-1">No agents registered yet</p>
                  <p className="text-secondary text-xs max-w-xs mx-auto mb-4">Register your first agent to start routing tool calls through Arbiter.</p>
                  <Button onClick={() => setShowRegisterModal(true)}>
                    Register Agent
                  </Button>
                </td>
              </tr>
            ) : (
              agents.map((agent) => (
                <tr
                  key={agent.id}
                  className={`group border-b border-border hover:bg-white/[0.025] transition-all duration-150 ${''}`}
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
                    {agent.rate_limit_per_minute != null
                      ? <span className="text-primary">{agent.rate_limit_per_minute}/min</span>
                      : <span className="italic">unlimited</span>}
                  </td>
                  <td className="py-3 px-4 font-mono text-xs text-muted">
                    {formatDate(agent.created_at)}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button variant="ghost" size="sm" onClick={() => setTestCallAgent(agent)}>
                        Test
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setSnippetAgent(agent)}>
                        Snippets
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setRenameAgent(agent)}>
                        Edit
                      </Button>
                      <OverflowMenu
                        agent={agent}
                        onRotate={setRotateTarget}
                        onDeactivate={setDeactivateTarget}
                      />
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        </div>
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

      <SnippetModal
        agent={snippetAgent}
        onClose={() => setSnippetAgent(null)}
      />

      <RenameModal
        agent={renameAgent}
        onClose={() => setRenameAgent(null)}
        onSuccess={() => {
          void queryClient.invalidateQueries({ queryKey: ["agents"] });
          showBanner('Agent renamed');
        }}
      />

      <TestCallModal
        agent={testCallAgent}
        onClose={() => setTestCallAgent(null)}
      />
    </div>
  );
}

export default Agents;
