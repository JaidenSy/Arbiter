/**
 * Arbiter — MCP Servers page.
 *
 * Lists registered MCP servers and allows:
 *   - Adding a new server (form modal)
 *   - Editing an existing server (form modal, pre-filled)
 *   - Deactivating (deleting) a server via a confirmation dialog
 */

import React, { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { authClient } from '../api/client'
import type { MCPServer, MCPServerCreate, MCPServerUpdate, MCPServerTestResult, Page } from '../api/types'
import Modal from '../components/Modal'
import ConfirmDialog from '../components/ConfirmDialog'
import Toggle from '../components/Toggle'
import { Button } from '../components/ui'

// ── Helpers ───────────────────────────────────────────────────────────────────

function extractApiError(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const msg: unknown = (detail[0] as { msg?: unknown }).msg
    if (typeof msg === 'string') return msg.replace(/^Value error, /, '')
  }
  return fallback
}

// ── Data fetchers / mutators ───────────────────────────────────────────────────

const fetchMCPServers = (): Promise<Page<MCPServer>> =>
  authClient.get<Page<MCPServer>>('/mcp-servers').then((r) => r.data)

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

const testMCPServer = (id: string): Promise<MCPServerTestResult> =>
  authClient.post<MCPServerTestResult>(`/mcp-servers/${id}/test`).then((r) => r.data)

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
    onError: (err: unknown) => setError(extractApiError(err, 'Failed to add server.')),
  })

  const updateMutation = useMutation({
    mutationFn: updateMCPServer,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['mcp-servers'] })
      onClose()
    },
    onError: (err: unknown) => setError(extractApiError(err, 'Failed to update server.')),
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

  const inputClass = "w-full bg-base border border-border text-primary text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/30 transition-all"
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
          <Button type="button" variant="secondary" size="sm" onClick={handleClose}>Cancel</Button>
          <Button
            type="submit"
            size="sm"
            isLoading={isPending}
            disabled={isPending || !name.trim() || !baseUrl.trim()}
          >
            {isEditing ? 'Save' : 'Add Server'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

// ── Server overflow menu (Deactivate) ─────────────────────────────────────────

function ServerOverflowMenu({ server, onDeactivate }: {
  server: MCPServer
  onDeactivate: (s: MCPServer) => void
}): React.ReactElement {
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
            onClick={() => { onDeactivate(server); setOpen(false); }}
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

// ── Skeleton rows ──────────────────────────────────────────────────────────────

function SkeletonRow(): React.ReactElement {
  return (
    <tr className="border-b border-border">
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
  const [testingId, setTestingId] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<{ id: string; result: MCPServerTestResult } | null>(null)
  const testResultTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const testMutation = useMutation({
    mutationFn: testMCPServer,
    onSuccess: (data, id) => {
      if (testResultTimerRef.current) clearTimeout(testResultTimerRef.current)
      setTestResult({ id, result: data })
      setTestingId(null)
      testResultTimerRef.current = setTimeout(() => setTestResult(null), 8000)
    },
    onError: () => {
      setTestingId(null)
    },
  })

  const handleTestClick = (server: MCPServer): void => {
    if (testResultTimerRef.current) clearTimeout(testResultTimerRef.current)
    setTestingId(server.id)
    setTestResult(null)
    testMutation.mutate(server.id)
  }

  const { data: serversPage, isLoading } = useQuery<Page<MCPServer>>({
    queryKey: ['mcp-servers'],
    queryFn: fetchMCPServers,
    refetchInterval: 30_000,
  })
  const servers = serversPage?.items

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
          <h1 className="font-display text-xl font-semibold tracking-tight text-primary">MCP Servers</h1>
          <p className="text-secondary text-sm mt-1">Connected tool servers proxied through Arbiter</p>
        </div>
        <Button onClick={handleAddClick}>Add Server</Button>
      </div>

      {/* Table card */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr className="border-b border-border">
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
                  <Button onClick={handleAddClick}>Add Server</Button>
                </td>
              </tr>
            ) : (
              servers.map((server) => (
                <tr
                  key={server.id}
                  className="group border-b border-border hover:bg-white/[0.025] transition-all duration-150"
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
                    {testResult?.id === server.id && (
                      <span className={`inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full border mr-2 ${
                        testResult.result.reachable
                          ? 'text-success bg-success/10 border-success/20'
                          : 'text-error bg-error/10 border-error/20'
                      }`}>
                        {testResult.result.reachable
                          ? `✓ ${testResult.result.tool_count ?? 0} tools · ${testResult.result.latency_ms}ms`
                          : `✗ ${testResult.result.error ?? 'unreachable'}`}
                      </span>
                    )}
                    <div className="inline-flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={testingId === server.id}
                        onClick={() => handleTestClick(server)}
                      >
                        {testingId === server.id ? 'Testing…' : 'Test'}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleEditClick(server)}>
                        Edit
                      </Button>
                      <ServerOverflowMenu
                        server={server}
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
