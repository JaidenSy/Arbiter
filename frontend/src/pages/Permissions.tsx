/**
 * Nexvault — Tool Permissions page.
 *
 * Two-panel layout:
 *   Left:  Agent selector list
 *   Right: Permissions table for the selected agent + grant/revoke actions
 */

import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { authClient } from '../api/client'
import type { Agent, MCPServer, ToolPermission, ToolPermissionCreate } from '../api/types'
import Modal from '../components/Modal'
import ConfirmDialog from '../components/ConfirmDialog'

// ── Data fetchers / mutators ───────────────────────────────────────────────────

const fetchAgents = (): Promise<Agent[]> =>
  authClient.get<Agent[]>('/agents').then((r) => r.data)

const fetchMCPServers = (): Promise<MCPServer[]> =>
  authClient.get<MCPServer[]>('/mcp-servers').then((r) => r.data)

const fetchPermissions = (agentId: string): Promise<ToolPermission[]> =>
  authClient.get<ToolPermission[]>(`/agents/${agentId}/permissions`).then((r) => r.data)

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

// ── Helpers ────────────────────────────────────────────────────────────────────

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

  const [mcpServerId, setMcpServerId] = useState('')
  const [toolName, setToolName] = useState('')
  const [grantedBy, setGrantedBy] = useState('')
  const [error, setError] = useState<string | null>(null)

  React.useEffect(() => {
    if (isOpen) {
      setMcpServerId(servers.length > 0 ? servers[0].id : '')
      setToolName('')
      setGrantedBy('')
      setError(null)
    }
  }, [isOpen, servers])

  const mutation = useMutation({
    mutationFn: grantPermission,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['permissions', agentId] })
      onClose()
    },
    onError: (err: unknown) => {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 409) {
        setError('This permission already exists.')
      } else {
        setError('Failed to grant permission. Please try again.')
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
        granted_by: grantedBy.trim() || null,
      },
    })
  }

  const handleClose = (): void => {
    setError(null)
    onClose()
  }

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Grant Permission">
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* MCP Server */}
        <div>
          <label
            htmlFor="perm-server"
            className="block text-sm text-secondary mb-1"
          >
            MCP Server <span className="text-error">*</span>
          </label>
          <select
            id="perm-server"
            required
            value={mcpServerId}
            onChange={(e) => setMcpServerId(e.target.value)}
            className="bg-elevated border border-white/[0.14] text-primary text-sm rounded px-3 py-2 w-full focus:border-accent focus:outline-none"
          >
            {servers.length === 0 && (
              <option value="" disabled>
                No servers available
              </option>
            )}
            {servers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>

        {/* Tool Name */}
        <div>
          <label
            htmlFor="perm-tool"
            className="block text-sm text-secondary mb-1"
          >
            Tool Name <span className="text-error">*</span>
          </label>
          <input
            id="perm-tool"
            type="text"
            required
            value={toolName}
            onChange={(e) => setToolName(e.target.value)}
            placeholder="e.g. read_file or *"
            className="w-full bg-elevated border border-white/[0.14] text-primary text-sm px-3 py-2 rounded font-mono focus:outline-none focus:border-accent focus:ring-0"
          />
          <p className="text-xs text-muted mt-1">
            Use <span className="font-mono">*</span> to grant access to all tools on this server.
          </p>
        </div>

        {/* Granted By */}
        <div>
          <label
            htmlFor="perm-granted-by"
            className="block text-sm text-secondary mb-1"
          >
            Granted By
          </label>
          <input
            id="perm-granted-by"
            type="text"
            value={grantedBy}
            onChange={(e) => setGrantedBy(e.target.value)}
            placeholder="your name or team"
            className="w-full bg-elevated border border-white/[0.14] text-primary text-sm px-3 py-2 rounded focus:outline-none focus:border-accent focus:ring-0"
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
            disabled={mutation.isPending || !mcpServerId || !toolName.trim()}
            className="bg-accent hover:bg-violet-600 text-white text-sm font-medium px-3 py-1.5 rounded disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {mutation.isPending ? 'Granting…' : 'Grant Permission'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

// ── Skeleton rows ──────────────────────────────────────────────────────────────

function SkeletonRow(): React.ReactElement {
  return (
    <tr className="border-b border-white/[0.07]">
      {[1, 2, 3, 4, 5].map((i) => (
        <td key={i} className="py-2 px-4">
          <div className="animate-pulse bg-elevated h-4 rounded w-3/4" />
        </td>
      ))}
    </tr>
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
  const [revokeTarget, setRevokeTarget] = useState<ToolPermission | null>(null)

  const { data: permissions, isLoading } = useQuery<ToolPermission[]>({
    queryKey: ['permissions', agentId],
    queryFn: () => fetchPermissions(agentId),
    enabled: !!agentId,
  })

  const revokeMutation = useMutation({
    mutationFn: revokePermission,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['permissions', agentId] })
    },
    onError: (err) => {
      console.error('Failed to revoke permission', err)
      void queryClient.invalidateQueries({ queryKey: ['permissions', agentId] })
    },
  })

  const handleRevokeConfirm = (): void => {
    if (revokeTarget) {
      revokeMutation.mutate({ agentId, permissionId: revokeTarget.id })
      setRevokeTarget(null)
    }
  }

  // Resolve MCP server name from id
  const serverName = (id: string): string =>
    servers.find((s) => s.id === id)?.name ?? id

  return (
    <div className="flex-1">
      {/* Header row */}
      <div className="flex items-center justify-between mb-4">
        <p className="text-primary text-sm font-semibold">
          Permissions for {agentName}
        </p>
        <button
          type="button"
          onClick={() => setGrantOpen(true)}
          className="bg-accent hover:bg-violet-600 text-white text-sm font-medium px-3 py-1.5 rounded transition-colors"
        >
          Grant Permission
        </button>
      </div>

      {/* Table */}
      <div className="border-t border-white/[0.07]">
        <table className="min-w-full">
          <thead>
            <tr>
              <th className="py-2 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">
                MCP Server
              </th>
              <th className="py-2 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">
                Tool
              </th>
              <th className="py-2 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">
                Granted At
              </th>
              <th className="py-2 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">
                Granted By
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
            ) : !permissions || permissions.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-12 px-4 text-center">
                  <p className="text-secondary text-sm">No permissions granted.</p>
                </td>
              </tr>
            ) : (
              permissions.map((perm) => (
                <tr
                  key={perm.id}
                  className="group border-b border-white/[0.07] hover:bg-elevated transition-colors"
                >
                  <td className="py-2 px-4 text-sm text-primary">
                    {serverName(perm.mcp_server_id)}
                  </td>
                  <td className="py-2 px-4">
                    {perm.tool_name === '*' ? (
                      <span className="font-mono text-xs text-secondary italic">
                        all tools
                      </span>
                    ) : (
                      <span className="font-mono text-xs text-accent-light">
                        {perm.tool_name}
                      </span>
                    )}
                  </td>
                  <td className="py-2 px-4 font-mono text-xs text-muted">
                    {formatDate(perm.granted_at)}
                  </td>
                  <td className="py-2 px-4 text-xs text-muted">
                    {perm.granted_by ?? <span className="text-muted">—</span>}
                  </td>
                  <td className="py-2 px-4 text-right">
                    <button
                      type="button"
                      onClick={() => setRevokeTarget(perm)}
                      className="opacity-0 group-hover:opacity-100 text-error hover:bg-error/10 px-3 py-1.5 rounded text-sm transition-all"
                    >
                      Revoke
                    </button>
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

      <ConfirmDialog
        isOpen={revokeTarget !== null}
        onClose={() => setRevokeTarget(null)}
        onConfirm={handleRevokeConfirm}
        title="Revoke Permission"
        message={`Revoke permission for tool "${revokeTarget?.tool_name ?? ''}"? This cannot be undone.`}
        confirmLabel="Revoke"
      />
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

function Permissions(): React.ReactElement {
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)

  const { data: agents } = useQuery<Agent[]>({
    queryKey: ['agents'],
    queryFn: fetchAgents,
  })

  const { data: servers = [] } = useQuery<MCPServer[]>({
    queryKey: ['mcp-servers'],
    queryFn: fetchMCPServers,
  })

  const selectedAgent = agents?.find((a) => a.id === selectedAgentId) ?? null

  return (
    <div className="p-8">
      <h1 className="text-primary text-lg font-semibold mb-8">Tool Permissions</h1>

      <div className="grid gap-6" style={{ gridTemplateColumns: '240px 1fr' }}>
        {/* Left panel — agent selector */}
        <div>
          <p className="text-muted text-xs uppercase tracking-widest mb-3">
            Agents
          </p>
          <div>
            {!agents || agents.length === 0 ? (
              <p className="text-secondary text-sm">No agents registered.</p>
            ) : (
              agents.map((agent) => {
                const isSelected = agent.id === selectedAgentId
                return (
                  <button
                    key={agent.id}
                    type="button"
                    onClick={() => setSelectedAgentId(agent.id)}
                    className={`w-full text-left flex items-center gap-2 px-3 py-2 transition-colors ${
                      isSelected
                        ? 'bg-highlight border-l-2 border-accent'
                        : 'border-l-2 border-transparent hover:bg-elevated'
                    }`}
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                        agent.is_active ? 'bg-green-400' : 'bg-muted'
                      }`}
                    />
                    <span className="text-primary text-sm truncate">{agent.name}</span>
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
          <div className="flex items-center justify-center">
            <p className="text-secondary text-sm">
              Select an agent to view permissions
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export default Permissions
