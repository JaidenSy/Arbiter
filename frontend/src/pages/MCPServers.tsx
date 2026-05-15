/**
 * Arbiter — MCP Servers page.
 *
 * Lists registered MCP servers and allows:
 *   - Adding a new server (form modal)
 *   - Editing an existing server (form modal, pre-filled)
 *   - Deactivating (deleting) a server via a confirmation dialog
 */

import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { authClient } from '../api/client'
import type { MCPServer, MCPServerCreate, MCPServerUpdate } from '../api/types'
import Modal from '../components/Modal'
import ConfirmDialog from '../components/ConfirmDialog'
import Toggle from '../components/Toggle'

// ── Data fetchers / mutators ───────────────────────────────────────────────────

const fetchMCPServers = (): Promise<MCPServer[]> =>
  authClient.get<MCPServer[]>('/mcp-servers').then((r) => r.data)

const createMCPServer = (payload: MCPServerCreate): Promise<MCPServer> =>
  authClient.post<MCPServer>('/mcp-servers', payload).then((r) => r.data)

const updateMCPServer = ({
  id,
  payload,
}: {
  id: string
  payload: MCPServerUpdate
}): Promise<MCPServer> =>
  authClient.patch<MCPServer>(`/mcp-servers/${id}`, payload).then((r) => r.data)

const deleteMCPServer = (id: string): Promise<void> =>
  authClient.delete(`/mcp-servers/${id}`).then(() => undefined)

// ── Server Form Modal ─────────────────────────────────────────────────────────

interface ServerFormModalProps {
  isOpen: boolean
  onClose: () => void
  editTarget: MCPServer | null
}

function ServerFormModal({
  isOpen,
  onClose,
  editTarget,
}: ServerFormModalProps): React.ReactElement | null {
  const queryClient = useQueryClient()

  const [name, setName] = useState(editTarget?.name ?? '')
  const [baseUrl, setBaseUrl] = useState(editTarget?.base_url ?? '')
  const [description, setDescription] = useState(editTarget?.description ?? '')
  const [cacheEnabled, setCacheEnabled] = useState(
    editTarget?.cache_enabled ?? false
  )
  const [error, setError] = useState<string | null>(null)

  React.useEffect(() => {
    if (isOpen) {
      setName(editTarget?.name ?? '')
      setBaseUrl(editTarget?.base_url ?? '')
      setDescription(editTarget?.description ?? '')
      setCacheEnabled(editTarget?.cache_enabled ?? false)
      setError(null)
    }
  }, [isOpen, editTarget])

  const createMutation = useMutation({
    mutationFn: createMCPServer,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['mcp-servers'] })
      onClose()
    },
    onError: () => setError('Failed to add server. Please try again.'),
  })

  const updateMutation = useMutation({
    mutationFn: updateMCPServer,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['mcp-servers'] })
      onClose()
    },
    onError: () => setError('Failed to update server. Please try again.'),
  })

  const isPending = createMutation.isPending || updateMutation.isPending
  const isEditing = editTarget !== null

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault()
    if (!name.trim() || !baseUrl.trim()) return
    setError(null)

    const payload = {
      name: name.trim(),
      base_url: baseUrl.trim(),
      description: description.trim() || null,
      cache_enabled: cacheEnabled,
    }

    if (isEditing) {
      updateMutation.mutate({ id: editTarget.id, payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  const handleClose = (): void => {
    setError(null)
    onClose()
  }

  const inputClass = "w-full bg-elevated border border-white/[0.1] text-primary text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/30 transition-all"
  const labelClass = "block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest"

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={isEditing ? 'Edit Server' : 'Add Server'}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="server-name" className={labelClass}>
            Name <span className="text-error normal-case">*</span>
          </label>
          <input
            id="server-name"
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. my-mcp-server"
            className={inputClass}
          />
        </div>

        <div>
          <label htmlFor="server-url" className={labelClass}>
            Base URL <span className="text-error normal-case">*</span>
          </label>
          <input
            id="server-url"
            type="text"
            required
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://"
            className={`${inputClass} font-mono`}
          />
        </div>

        <div>
          <label htmlFor="server-desc" className={labelClass}>
            Description
          </label>
          <input
            id="server-desc"
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description"
            className={inputClass}
          />
        </div>

        <div className="flex items-center justify-between py-1">
          <div>
            <span className="text-sm text-primary font-medium">Cache enabled</span>
            <p className="text-xs text-secondary mt-0.5">Cache tool responses for faster repeated calls</p>
          </div>
          <Toggle checked={cacheEnabled} onChange={setCacheEnabled} />
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
            disabled={isPending || !name.trim() || !baseUrl.trim()}
            className="bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 text-white text-sm font-semibold px-4 py-1.5 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all hover:shadow-[0_0_16px_rgba(124,58,237,0.3)]"
          >
            {isPending
              ? isEditing ? 'Saving…' : 'Adding…'
              : isEditing ? 'Save' : 'Add Server'}
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
      {[4, 8, 6, 3, 3, 2].map((w, i) => (
        <td key={i} className="py-3 px-4">
          <div className="h-3 skeleton-shimmer rounded" style={{ width: `${w * 14}px` }} />
        </td>
      ))}
    </tr>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

function MCPServers(): React.ReactElement {
  const queryClient = useQueryClient()

  const [formOpen, setFormOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<MCPServer | null>(null)
  const [deactivateTarget, setDeactivateTarget] = useState<MCPServer | null>(null)

  const { data: servers, isLoading } = useQuery<MCPServer[]>({
    queryKey: ['mcp-servers'],
    queryFn: fetchMCPServers,
    refetchInterval: 30_000,
  })

  const deleteMutation = useMutation({
    mutationFn: deleteMCPServer,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['mcp-servers'] })
    },
    onError: (err) => {
      console.error('Failed to deactivate server', err)
      void queryClient.invalidateQueries({ queryKey: ['mcp-servers'] })
    },
  })

  const handleAddClick = (): void => {
    setEditTarget(null)
    setFormOpen(true)
  }

  const handleEditClick = (server: MCPServer): void => {
    setEditTarget(server)
    setFormOpen(true)
  }

  const handleFormClose = (): void => {
    setFormOpen(false)
    setEditTarget(null)
  }

  const handleDeactivateConfirm = (): void => {
    if (deactivateTarget) {
      deleteMutation.mutate(deactivateTarget.id)
      setDeactivateTarget(null)
    }
  }

  return (
    <div className="p-8 animate-fade-in">
      {/* Page header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="gradient-text-purple text-xl font-bold">MCP Servers</h1>
          <p className="text-secondary text-sm mt-1">Connected tool servers proxied through Arbiter</p>
        </div>
        <button
          type="button"
          className="bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-all hover:shadow-[0_0_20px_rgba(124,58,237,0.3)]"
          onClick={handleAddClick}
        >
          Add Server
        </button>
      </div>

      {/* Table card */}
      <div className="bg-surface border border-white/[0.07] rounded-xl overflow-hidden">
        <table className="min-w-full">
          <thead>
            <tr className="border-b border-white/[0.06]">
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Name</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Base URL</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Description</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Cache</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Status</th>
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
            ) : !servers || servers.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-20 px-4 text-center">
                  <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
                    <svg className="text-accent-light" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <rect x="2" y="3" width="20" height="5" rx="1"/>
                      <rect x="2" y="10" width="20" height="5" rx="1"/>
                      <rect x="2" y="17" width="20" height="5" rx="1"/>
                      <circle cx="18" cy="5.5" r="0.75" fill="currentColor"/>
                      <circle cx="18" cy="12.5" r="0.75" fill="currentColor"/>
                      <circle cx="18" cy="19.5" r="0.75" fill="currentColor"/>
                    </svg>
                  </div>
                  <p className="text-primary text-sm font-medium mb-1">No MCP servers registered</p>
                  <p className="text-secondary text-xs max-w-xs mx-auto mb-4">Add a server to start routing tool calls through Arbiter.</p>
                  <button
                    type="button"
                    onClick={handleAddClick}
                    className="bg-gradient-to-r from-accent to-violet-600 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-all hover:shadow-[0_0_16px_rgba(124,58,237,0.3)]"
                  >
                    Add Server
                  </button>
                </td>
              </tr>
            ) : (
              servers.map((server, idx) => (
                <tr
                  key={server.id}
                  className={`group border-b border-white/[0.05] hover:bg-white/[0.025] transition-all duration-150 ${idx % 2 === 1 ? 'bg-white/[0.01]' : ''}`}
                >
                  <td className="py-3 px-4">
                    <span
                      className={`text-sm font-medium ${
                        server.is_active ? 'text-primary' : 'text-muted line-through'
                      }`}
                    >
                      {server.name}
                    </span>
                  </td>
                  <td className="py-3 px-4 max-w-xs">
                    <span
                      className="font-mono text-xs text-secondary truncate block max-w-xs"
                      title={server.base_url}
                    >
                      {server.base_url}
                    </span>
                  </td>
                  <td className="py-3 px-4 max-w-xs">
                    {server.description ? (
                      <span className="text-secondary text-xs truncate block max-w-xs" title={server.description}>
                        {server.description}
                      </span>
                    ) : (
                      <span className="text-muted text-xs italic">—</span>
                    )}
                  </td>
                  <td className="py-3 px-4">
                    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide ${
                      server.cache_enabled
                        ? 'bg-teal/10 text-teal-light border border-teal/20'
                        : 'bg-muted/10 text-muted border border-muted/10'
                    }`}>
                      <span className={`w-1 h-1 rounded-full ${server.cache_enabled ? 'bg-teal-light' : 'bg-muted'}`} />
                      {server.cache_enabled ? 'cached' : 'off'}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide ${
                      server.is_active
                        ? 'bg-success/10 text-success border border-success/20'
                        : 'bg-muted/20 text-muted border border-muted/20'
                    }`}>
                      <span className={`w-1 h-1 rounded-full ${server.is_active ? 'bg-success' : 'bg-muted'}`} />
                      {server.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        type="button"
                        onClick={() => handleEditClick(server)}
                        className="text-secondary hover:text-primary border border-white/[0.08] hover:border-white/[0.18] px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => setDeactivateTarget(server)}
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

      <ServerFormModal
        isOpen={formOpen}
        onClose={handleFormClose}
        editTarget={editTarget}
      />

      <ConfirmDialog
        isOpen={deactivateTarget !== null}
        onClose={() => setDeactivateTarget(null)}
        onConfirm={handleDeactivateConfirm}
        title="Deactivate Server"
        message={`Deactivate server "${deactivateTarget?.name ?? ''}"? This cannot be undone.`}
        confirmLabel="Deactivate"
      />
    </div>
  )
}

export default MCPServers
