/**
 * NexusAI — MCP Servers page.
 *
 * Lists registered MCP servers and allows:
 *   - Adding a new server (form modal)
 *   - Editing an existing server (form modal, pre-filled)
 *   - Deactivating (deleting) a server via a confirmation dialog
 */

import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { MCPServer, MCPServerCreate, MCPServerUpdate } from '../api/types'
import Modal from '../components/Modal'
import ConfirmDialog from '../components/ConfirmDialog'
import Toggle from '../components/Toggle'

// ── Data fetchers / mutators ───────────────────────────────────────────────────

const fetchMCPServers = (): Promise<MCPServer[]> =>
  apiClient.get<MCPServer[]>('/mcp_servers').then((r) => r.data)

const createMCPServer = (payload: MCPServerCreate): Promise<MCPServer> =>
  apiClient.post<MCPServer>('/mcp_servers', payload).then((r) => r.data)

const updateMCPServer = ({
  id,
  payload,
}: {
  id: string
  payload: MCPServerUpdate
}): Promise<MCPServer> =>
  apiClient.patch<MCPServer>(`/mcp_servers/${id}`, payload).then((r) => r.data)

const deleteMCPServer = (id: string): Promise<void> =>
  apiClient.delete(`/mcp_servers/${id}`).then(() => undefined)

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

  // Re-sync form when editTarget changes (modal re-used for add vs edit)
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

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={isEditing ? 'Edit Server' : 'Add Server'}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="server-name"
            className="block text-sm text-secondary mb-1"
          >
            Name <span className="text-error">*</span>
          </label>
          <input
            id="server-name"
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. my-mcp-server"
            className="w-full bg-elevated border border-white/[0.14] text-primary text-sm px-3 py-1.5 rounded focus:outline-none focus:border-accent focus:ring-0"
          />
        </div>

        <div>
          <label
            htmlFor="server-url"
            className="block text-sm text-secondary mb-1"
          >
            Base URL <span className="text-error">*</span>
          </label>
          <input
            id="server-url"
            type="text"
            required
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://"
            className="w-full bg-elevated border border-white/[0.14] text-primary text-sm px-3 py-1.5 rounded font-mono focus:outline-none focus:border-accent focus:ring-0"
          />
        </div>

        <div>
          <label
            htmlFor="server-desc"
            className="block text-sm text-secondary mb-1"
          >
            Description
          </label>
          <input
            id="server-desc"
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description"
            className="w-full bg-elevated border border-white/[0.14] text-primary text-sm px-3 py-1.5 rounded focus:outline-none focus:border-accent focus:ring-0"
          />
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm text-secondary">Cache enabled</span>
          <Toggle checked={cacheEnabled} onChange={setCacheEnabled} />
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
            disabled={isPending || !name.trim() || !baseUrl.trim()}
            className="bg-accent hover:bg-violet-600 text-white text-sm font-medium px-3 py-1.5 rounded disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isPending
              ? isEditing
                ? 'Saving…'
                : 'Adding…'
              : isEditing
                ? 'Save'
                : 'Add Server'}
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
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <td key={i} className="py-2 px-4">
          <div className="h-3 bg-elevated rounded animate-pulse w-3/4" />
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
  const [deactivateTarget, setDeactivateTarget] = useState<MCPServer | null>(
    null
  )

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
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-primary text-lg font-semibold">MCP Servers</h1>
        <button
          type="button"
          className="bg-accent hover:bg-violet-600 text-white text-sm font-medium px-3 py-1.5 rounded transition-colors"
          onClick={handleAddClick}
        >
          Add Server
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
                Base URL
              </th>
              <th className="py-2 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">
                Description
              </th>
              <th className="py-2 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">
                Cache
              </th>
              <th className="py-2 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">
                Status
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
            ) : !servers || servers.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-12 px-4 text-center">
                  <p className="text-secondary text-sm">
                    No MCP servers registered.
                  </p>
                  <p className="text-muted text-xs mt-1">
                    Add a server to start routing tool calls.
                  </p>
                </td>
              </tr>
            ) : (
              servers.map((server) => (
                <tr
                  key={server.id}
                  className="group border-b border-white/[0.07] hover:bg-elevated transition-colors"
                >
                  <td className="py-2 px-4">
                    <span
                      className={`text-sm font-medium ${
                        server.is_active ? 'text-primary' : 'text-muted line-through'
                      }`}
                    >
                      {server.name}
                    </span>
                  </td>
                  <td className="py-2 px-4 max-w-xs">
                    <span
                      className="font-mono text-xs text-secondary truncate block max-w-xs"
                      title={server.base_url}
                    >
                      {server.base_url}
                    </span>
                  </td>
                  <td className="py-2 px-4 max-w-xs">
                    {server.description ? (
                      <span
                        className="text-secondary text-xs truncate block max-w-xs"
                        title={server.description}
                      >
                        {server.description}
                      </span>
                    ) : (
                      <span className="text-muted text-xs">—</span>
                    )}
                  </td>
                  <td className="py-2 px-4">
                    <div className="flex items-center">
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          server.cache_enabled ? 'bg-green-400' : 'bg-muted'
                        }`}
                      />
                      <span className="text-muted text-xs ml-1.5">
                        {server.cache_enabled ? 'cached' : 'no cache'}
                      </span>
                    </div>
                  </td>
                  <td className="py-2 px-4">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          server.is_active ? 'bg-green-400' : 'bg-muted'
                        }`}
                      />
                      <span className="text-xs text-secondary">
                        {server.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                  </td>
                  <td className="py-2 px-4 text-right">
                    <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        type="button"
                        onClick={() => handleEditClick(server)}
                        className="text-secondary hover:text-primary hover:bg-elevated px-3 py-1.5 rounded text-sm transition-colors"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => setDeactivateTarget(server)}
                        className="text-error hover:bg-red-500/10 px-3 py-1.5 rounded text-sm transition-colors"
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
