/**
 * Arbiter — Tool Permissions page.
 *
 * Two-panel layout:
 *   Left:  Agent selector list
 *   Right: Permissions table for the selected agent + grant/revoke actions
 */

import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { authClient } from '../api/client'
import type { Agent, MCPServer, Page, ToolPermission, ToolPermissionCreate, ToolPermissionUpdate, ToolPermissionEvent } from '../api/types'
import Modal from '../components/Modal'
import ConfirmDialog from '../components/ConfirmDialog'
import { useAuth } from '../context/AuthContext'

// ── Data fetchers / mutators ───────────────────────────────────────────────────

const fetchAgents = (): Promise<Page<Agent>> =>
  authClient.get<Page<Agent>>('/agents').then((r) => r.data)

const fetchMCPServers = (): Promise<Page<MCPServer>> =>
  authClient.get<Page<MCPServer>>('/mcp-servers').then((r) => r.data)

const fetchPermissions = (agentId: string): Promise<ToolPermission[]> =>
  authClient.get<Page<ToolPermission>>(`/agents/${agentId}/permissions`).then((r) => r.data.items)

const grantPermission = ({
  agentId,
  payload,
}: {
  agentId: string
  payload: ToolPermissionCreate
}): Promise<ToolPermission> =>
  authClient
    .post<ToolPermission>(`/agents/${agentId}/permissions`, payload)
    .then((r) => r.data)

const revokePermission = ({
  agentId,
  permissionId,
}: {
  agentId: string
  permissionId: string
}): Promise<void> =>
  authClient.delete(`/agents/${agentId}/permissions/${permissionId}`).then(() => undefined)

const fetchHistory = (agentId: string): Promise<ToolPermissionEvent[]> =>
  authClient.get<Page<ToolPermissionEvent>>(`/agents/${agentId}/permissions/history`).then((r) => r.data.items)

const updatePermission = ({
  agentId,
  permissionId,
  payload,
}: {
  agentId: string
  permissionId: string
  payload: ToolPermissionUpdate
}): Promise<ToolPermission> =>
  authClient
    .patch<ToolPermission>(`/agents/${agentId}/permissions/${permissionId}`, payload)
    .then((r) => r.data)

// ── Helpers ────────────────────────────────────────────────────────────────────

function extractApiError(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const msg: unknown = (detail[0] as { msg?: unknown }).msg
    if (typeof msg === 'string') return msg.replace(/^Value error, /, '')
  }
  return fallback
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

// ── Grant Permission Modal ─────────────────────────────────────────────────────

interface GrantModalProps {
  isOpen: boolean
  onClose: () => void
  agentId: string
  servers: MCPServer[]
}

function GrantModal({
  isOpen,
  onClose,
  agentId,
  servers,
}: GrantModalProps): React.ReactElement | null {
  const queryClient = useQueryClient()
  const { user } = useAuth()

  const [mcpServerId, setMcpServerId] = useState('')
  const [toolName, setToolName] = useState('')
  const [error, setError] = useState<string | null>(null)

  React.useEffect(() => {
    if (isOpen) {
      setMcpServerId(servers.length > 0 ? servers[0].id : '')
      setToolName('')
      setError(null)
    }
  }, [isOpen, servers])

  const mutation = useMutation({
    mutationFn: grantPermission,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['permissions', agentId] })
      void queryClient.invalidateQueries({ queryKey: ['permissions-history', agentId] })
      onClose()
    },
    onError: (err: unknown) => {
      const httpStatus = (err as { response?: { status?: number } })?.response?.status
      if (httpStatus === 409) {
        setError('This permission already exists.')
      } else {
        setError(extractApiError(err, 'Failed to grant permission. Please try again.'))
      }
    },
  })

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault()
    if (!mcpServerId || !toolName.trim()) return
    setError(null)
    mutation.mutate({
      agentId,
      payload: {
        mcp_server_id: mcpServerId,
        tool_name: toolName.trim(),
      },
    })
  }

  const handleClose = (): void => {
    setError(null)
    onClose()
  }

  const inputClass = "w-full bg-base border border-white/[0.1] text-primary text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/30 transition-all"
  const labelClass = "block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest"

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Grant Permission">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="perm-server" className={labelClass}>
            MCP Server <span className="text-error normal-case">*</span>
          </label>
          <select
            id="perm-server"
            required
            value={mcpServerId}
            onChange={(e) => setMcpServerId(e.target.value)}
            className={inputClass}
          >
            {servers.length === 0 && (
              <option value="" disabled>No servers available</option>
            )}
            {servers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="perm-tool" className={labelClass}>
            Tool Name <span className="text-error normal-case">*</span>
          </label>
          <input
            id="perm-tool"
            type="text"
            required
            value={toolName}
            onChange={(e) => setToolName(e.target.value)}
            placeholder="e.g. read_file or *"
            className={`${inputClass} font-mono`}
          />
          <p className="text-xs text-muted mt-1.5">
            Use <code className="font-mono text-accent-light">*</code> to grant access to all tools on this server.
          </p>
        </div>

        <div>
          <label className={labelClass}>Granted By</label>
          <div className="px-3 py-2 bg-base border border-white/[0.07] rounded-lg text-sm text-secondary">
            {user?.display_name ?? user?.email ?? '—'}
          </div>
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
            disabled={mutation.isPending || !mcpServerId || !toolName.trim()}
            className="bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 text-white text-sm font-semibold px-4 py-1.5 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all hover:shadow-[0_0_16px_rgba(124,58,237,0.3)]"
          >
            {mutation.isPending ? 'Granting…' : 'Grant Permission'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

// ── Edit Permission Modal ──────────────────────────────────────────────────────

interface EditModalProps {
  isOpen: boolean
  onClose: () => void
  agentId: string
  permission: ToolPermission | null
}

function EditModal({ isOpen, onClose, agentId, permission }: EditModalProps): React.ReactElement | null {
  const queryClient = useQueryClient()

  const [rateLimit, setRateLimit] = useState<string>('')
  const [cacheTtl, setCacheTtl] = useState<string>('')
  const [error, setError] = useState<string | null>(null)

  React.useEffect(() => {
    if (isOpen && permission) {
      setRateLimit(permission.rate_limit_per_minute != null ? String(permission.rate_limit_per_minute) : '')
      setCacheTtl(permission.cache_ttl_seconds != null ? String(permission.cache_ttl_seconds) : '')
      setError(null)
    }
  }, [isOpen, permission])

  const mutation = useMutation({
    mutationFn: updatePermission,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['permissions', agentId] })
      void queryClient.invalidateQueries({ queryKey: ['permissions-history', agentId] })
      onClose()
    },
    onError: (err: unknown) => {
      setError(extractApiError(err, 'Failed to update permission.'))
    },
  })

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault()
    if (!permission) return
    setError(null)
    mutation.mutate({
      agentId,
      permissionId: permission.id,
      payload: {
        rate_limit_per_minute: rateLimit.trim() !== '' ? Number(rateLimit) : null,
        cache_ttl_seconds: cacheTtl.trim() !== '' ? Number(cacheTtl) : null,
      },
    })
  }

  const inputClass = "w-full bg-base border border-white/[0.1] text-primary text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/30 transition-all font-mono"
  const labelClass = "block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest"

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Edit Permission">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="bg-base border border-white/[0.07] rounded-lg px-3 py-2 space-y-0.5">
          <p className="text-xs text-muted">Tool</p>
          <p className="text-sm font-mono text-accent-light">{permission?.tool_name ?? '—'}</p>
        </div>

        <div>
          <label htmlFor="edit-rate-limit" className={labelClass}>
            Rate Limit <span className="text-muted normal-case font-normal">(calls/min — leave blank for unlimited)</span>
          </label>
          <input
            id="edit-rate-limit"
            type="number"
            min={1}
            value={rateLimit}
            onChange={(e) => setRateLimit(e.target.value)}
            placeholder="Unlimited"
            className={inputClass}
          />
        </div>

        <div>
          <label htmlFor="edit-cache-ttl" className={labelClass}>
            Cache TTL <span className="text-muted normal-case font-normal">(seconds — leave blank for global default)</span>
          </label>
          <input
            id="edit-cache-ttl"
            type="number"
            min={1}
            value={cacheTtl}
            onChange={(e) => setCacheTtl(e.target.value)}
            placeholder="Global default"
            className={inputClass}
          />
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
            onClick={onClose}
            className="text-secondary hover:text-primary hover:bg-elevated px-3 py-1.5 rounded-lg text-sm transition-all border border-white/[0.08] hover:border-white/[0.15]"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={mutation.isPending}
            className="bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 text-white text-sm font-semibold px-4 py-1.5 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all hover:shadow-[0_0_16px_rgba(124,58,237,0.3)]"
          >
            {mutation.isPending ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

// ── Skeleton rows ──────────────────────────────────────────────────────────────

function SkeletonRow(): React.ReactElement {
  return (
    <tr className="border-b border-white/[0.05]">
      {[5, 4, 4, 4, 3, 3, 2].map((w, i) => (
        <td key={i} className="py-3 px-4">
          <div className="skeleton-shimmer h-4 rounded" style={{ width: `${w * 14}px` }} />
        </td>
      ))}
    </tr>
  )
}

// ── History Panel ─────────────────────────────────────────────────────────────

function actionBadge(action: ToolPermissionEvent['action']): React.ReactElement {
  const styles: Record<string, string> = {
    granted: 'bg-success/10 text-success border-success/20',
    revoked: 'bg-error/10 text-error border-error/20',
    updated: 'bg-accent/10 text-accent-light border-accent/20',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border ${styles[action] ?? ''}`}>
      {action}
    </span>
  )
}

function formatChanges(changes: Record<string, [unknown, unknown]>): string {
  return Object.entries(changes)
    .map(([k, [from, to]]) => {
      const label = k === 'rate_limit_per_minute' ? 'rate limit' : 'cache TTL'
      const fmtVal = (v: unknown) => (v == null ? 'none' : String(v))
      return `${label}: ${fmtVal(from)} → ${fmtVal(to)}`
    })
    .join(', ')
}

const ACTION_FILTERS = ['all', 'granted', 'revoked', 'updated'] as const
type ActionFilter = typeof ACTION_FILTERS[number]

interface HistoryPanelProps {
  agentId: string
}

function HistoryPanel({ agentId }: HistoryPanelProps): React.ReactElement {
  const [actionFilter, setActionFilter] = useState<ActionFilter>('all')
  const [sortAsc, setSortAsc] = useState(false)

  const { data: events, isLoading } = useQuery<ToolPermissionEvent[]>({
    queryKey: ['permissions-history', agentId],
    queryFn: () => fetchHistory(agentId),
    enabled: !!agentId,
  })

  const filtered = (events ?? [])
    .filter((e) => actionFilter === 'all' || e.action === actionFilter)
    .sort((a, b) => {
      const diff = new Date(a.occurred_at).getTime() - new Date(b.occurred_at).getTime()
      return sortAsc ? diff : -diff
    })
    .slice(0, 10)

  const filterBtn = (f: ActionFilter) => {
    const active = actionFilter === f
    return (
      <button
        key={f}
        type="button"
        onClick={() => setActionFilter(f)}
        className={`px-3 py-1 rounded-md text-xs font-medium capitalize transition-all ${
          active
            ? 'bg-accent/15 text-accent-light border border-accent/30'
            : 'text-muted hover:text-secondary border border-transparent hover:border-white/[0.08]'
        }`}
      >
        {f}
      </button>
    )
  }

  return (
    <div className="mt-6">
      <div className="flex items-center justify-between mb-3">
        <p className="text-muted text-xs font-semibold uppercase tracking-widest">Permission History</p>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1">
            {ACTION_FILTERS.map(filterBtn)}
          </div>
          <button
            type="button"
            onClick={() => setSortAsc((v) => !v)}
            title={sortAsc ? 'Oldest first' : 'Newest first'}
            className="ml-1 px-2.5 py-1 rounded-md text-xs text-muted hover:text-secondary border border-transparent hover:border-white/[0.08] transition-all flex items-center gap-1"
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
              {sortAsc
                ? <><path d="M5 1v8M2 6l3 3 3-3"/></>
                : <><path d="M5 9V1M2 4l3-3 3 3"/></>}
            </svg>
            {sortAsc ? 'Oldest' : 'Newest'}
          </button>
        </div>
      </div>
      <div className="bg-surface border border-white/[0.07] rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="py-8 flex items-center justify-center">
            <div className="w-4 h-4 border-2 border-accent/40 border-t-accent rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <p className="text-muted text-xs text-center py-8">
            {events?.length ? 'No events match the filter.' : 'No history yet.'}
          </p>
        ) : (
          <table className="min-w-full">
            <thead>
              <tr className="border-b border-white/[0.06]">
                <th className="py-2.5 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Action</th>
                <th className="py-2.5 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Tool</th>
                <th className="py-2.5 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">By</th>
                <th className="py-2.5 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Changes</th>
                <th className="py-2.5 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">When</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => (
                <tr key={e.id} className="border-b border-white/[0.04] last:border-0">
                  <td className="py-2.5 px-4">{actionBadge(e.action)}</td>
                  <td className="py-2.5 px-4 font-mono text-xs text-accent-light">{e.tool_name}</td>
                  <td className="py-2.5 px-4 text-xs text-secondary">{e.performed_by ?? '—'}</td>
                  <td className="py-2.5 px-4 text-xs text-muted">
                    {e.changes ? formatChanges(e.changes) : '—'}
                  </td>
                  <td className="py-2.5 px-4 font-mono text-xs text-muted">
                    {new Date(e.occurred_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

// ── Permissions Table ──────────────────────────────────────────────────────────

interface PermissionsTableProps {
  agentId: string
  agentName: string
  servers: MCPServer[]
}

function PermissionsTable({
  agentId,
  agentName,
  servers,
}: PermissionsTableProps): React.ReactElement {
  const queryClient = useQueryClient()

  const [grantOpen, setGrantOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<ToolPermission | null>(null)
  const [revokeTarget, setRevokeTarget] = useState<ToolPermission | null>(null)

  const { data: permissions, isLoading } = useQuery<ToolPermission[]>({
    queryKey: ['permissions', agentId],
    queryFn: () => fetchPermissions(agentId),
    enabled: !!agentId,
  })

  const invalidateAll = () => {
    void queryClient.invalidateQueries({ queryKey: ['permissions', agentId] })
    void queryClient.invalidateQueries({ queryKey: ['permissions-history', agentId] })
  }

  const revokeMutation = useMutation({
    mutationFn: revokePermission,
    onSuccess: invalidateAll,
    onError: (err) => {
      console.error('Failed to revoke permission', err)
      invalidateAll()
    },
  })

  const handleRevokeConfirm = (): void => {
    if (revokeTarget) {
      revokeMutation.mutate({ agentId, permissionId: revokeTarget.id })
      setRevokeTarget(null)
    }
  }

  const serverName = (id: string): string =>
    servers.find((s) => s.id === id)?.name ?? id

  return (
    <div className="flex-1">
      {/* Header row */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <p className="text-primary text-sm font-semibold">
            Permissions for <span className="text-accent-light">{agentName}</span>
          </p>
        </div>
        <button
          type="button"
          onClick={() => setGrantOpen(true)}
          className="bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-all hover:shadow-[0_0_16px_rgba(124,58,237,0.3)]"
        >
          Grant Permission
        </button>
      </div>

      {/* Table */}
      <div className="bg-surface border border-white/[0.07] rounded-xl overflow-hidden">
        <table className="min-w-full">
          <thead>
            <tr className="border-b border-white/[0.06]">
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">MCP Server</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Tool</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Granted At</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Granted By</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Rate Limit</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Cache TTL</th>
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
            ) : !permissions || permissions.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-20 px-4 text-center">
                  <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
                    <svg className="text-accent-light" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <rect x="3" y="11" width="18" height="11" rx="1"/>
                      <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                    </svg>
                  </div>
                  <p className="text-primary text-sm font-medium mb-1">No permissions granted</p>
                  <p className="text-secondary text-xs max-w-xs mx-auto">Grant a permission to allow this agent to call specific tools.</p>
                </td>
              </tr>
            ) : (
              permissions.map((perm) => (
                <tr
                  key={perm.id}
                  className={`group border-b border-white/[0.05] hover:bg-white/[0.025] transition-colors ${''}`}
                >
                  <td className="py-3 px-4 text-sm text-primary font-medium">
                    {serverName(perm.mcp_server_id)}
                  </td>
                  <td className="py-3 px-4">
                    {perm.tool_name === '*' ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold text-warning bg-warning/10 border border-warning/30">
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                        all tools
                      </span>
                    ) : (
                      <span className="font-mono text-xs text-accent-light bg-accent/8 border border-accent/15 px-2 py-0.5 rounded-md">
                        {perm.tool_name}
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-4 font-mono text-xs text-muted">
                    {formatDate(perm.granted_at)}
                  </td>
                  <td className="py-3 px-4 text-xs text-secondary">
                    {perm.granted_by ?? <span className="text-muted italic">—</span>}
                  </td>
                  <td className="py-3 px-4 font-mono text-xs text-muted">
                    {perm.rate_limit_per_minute != null
                      ? <span className="text-primary">{perm.rate_limit_per_minute}/min</span>
                      : <span className="italic">unlimited</span>}
                  </td>
                  <td className="py-3 px-4 font-mono text-xs text-muted">
                    {perm.cache_ttl_seconds != null
                      ? <span className="text-primary">{perm.cache_ttl_seconds}s</span>
                      : <span className="italic">default</span>}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <div className="inline-flex items-center gap-1 opacity-40 group-hover:opacity-100 transition-opacity">
                      <button
                        type="button"
                        onClick={() => setEditTarget(perm)}
                        className="text-secondary hover:text-primary hover:bg-white/[0.06] border border-transparent hover:border-white/[0.1] px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => setRevokeTarget(perm)}
                        className="text-error hover:bg-error/10 border border-transparent hover:border-error/20 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                      >
                        Revoke
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <GrantModal
        isOpen={grantOpen}
        onClose={() => setGrantOpen(false)}
        agentId={agentId}
        servers={servers}
      />

      <EditModal
        isOpen={editTarget !== null}
        onClose={() => setEditTarget(null)}
        agentId={agentId}
        permission={editTarget}
      />

      <ConfirmDialog
        isOpen={revokeTarget !== null}
        onClose={() => setRevokeTarget(null)}
        onConfirm={handleRevokeConfirm}
        title="Revoke Permission"
        message={`Revoke permission for tool "${revokeTarget?.tool_name ?? ''}"? This cannot be undone.`}
        confirmLabel="Revoke"
      />

      <HistoryPanel agentId={agentId} />
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

function Permissions(): React.ReactElement {
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)

  const { data: agentsPage } = useQuery<Page<Agent>>({
    queryKey: ['agents'],
    queryFn: fetchAgents,
  })
  const agents = agentsPage?.items ?? []

  const { data: serversPage } = useQuery<Page<MCPServer>>({
    queryKey: ['mcp-servers'],
    queryFn: fetchMCPServers,
  })
  const servers = serversPage?.items ?? []

  const selectedAgent = agents.find((a) => a.id === selectedAgentId) ?? null

  return (
    <div className="p-8 animate-fade-in">
      <div className="mb-8">
        <h1 className="gradient-text-purple text-xl font-bold">Tool Permissions</h1>
        <p className="text-secondary text-sm mt-1">Control which tools each agent is allowed to invoke</p>
      </div>

      <div className="grid gap-6" style={{ gridTemplateColumns: '240px 1fr' }}>
        {/* Left panel — agent selector */}
        <div>
          <p className="text-muted text-xs font-semibold uppercase tracking-widest mb-3">
            Agents
          </p>
          <div className="bg-surface border border-white/[0.07] rounded-xl overflow-hidden">
            {agents.length === 0 ? (
              <div className="px-4 py-5 flex flex-col items-start gap-3">
                <p className="text-secondary text-xs">No agents registered.</p>
                <Link
                  to="/agents"
                  className="border border-white/[0.1] hover:border-accent/50 text-secondary hover:text-accent-light px-4 py-2 rounded-lg text-sm transition-all"
                >
                  Register Agent
                </Link>
              </div>
            ) : (
              agents.map((agent) => {
                const isSelected = agent.id === selectedAgentId
                return (
                  <button
                    key={agent.id}
                    type="button"
                    onClick={() => setSelectedAgentId(agent.id)}
                    className={`w-full text-left flex items-center gap-2.5 px-4 py-3 transition-all duration-150 border-b border-white/[0.05] last:border-0 ${
                      isSelected
                        ? 'bg-accent/8 border-l-2 border-l-accent'
                        : 'border-l-2 border-l-transparent hover:bg-white/[0.025]'
                    }`}
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                        agent.is_active ? 'bg-success' : 'bg-muted'
                      }`}
                    />
                    <span className="text-primary text-sm truncate font-medium">{agent.name}</span>
                  </button>
                )
              })
            )}
          </div>
        </div>

        {/* Right panel — permissions */}
        {selectedAgent ? (
          <PermissionsTable
            agentId={selectedAgent.id}
            agentName={selectedAgent.name}
            servers={servers}
          />
        ) : (
          <div className="flex flex-col items-center justify-center gap-3 text-center py-20 bg-surface border border-white/[0.07] rounded-xl">
            <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center">
              <svg className="text-accent-light" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="3" y="11" width="18" height="11" rx="1"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
            </div>
            <div>
              <p className="text-primary text-sm font-medium">Select an agent</p>
              <p className="text-secondary text-xs mt-1">to view and manage tool permissions</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default Permissions
