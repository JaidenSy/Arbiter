/**
 * Arbiter — Vault page.
 *
 * Two-panel layout:
 *   Left:  Agent selector list
 *   Right: Secrets table for the selected agent + add/rotate/delete actions
 *
 * Org-level secrets (agent_id=null) are shown in a separate "Organization
 * Secrets" section visible only to owners and admins.
 *
 * Secrets are write-only by default; values can be revealed one at a time
 * via GET /vault/secrets/{id}. Revealed values are held only in local state.
 */

import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { authClient } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { Button } from '../components/ui'
import type { Agent, VaultSecret, VaultSecretWithValue, VaultSecretCreate, Page } from '../api/types'
import Modal from '../components/Modal'
import ConfirmDialog from '../components/ConfirmDialog'
import CopyButton from '../components/CopyButton'

// ── Data fetchers / mutators ───────────────────────────────────────────────────

const fetchAgents = (): Promise<Page<Agent>> =>
  authClient.get<Page<Agent>>('/agents').then((r) => r.data)

const fetchSecrets = (agentId: string): Promise<Page<VaultSecret>> =>
  authClient
    .get<Page<VaultSecret>>('/vault/secrets', { params: { agent_id: agentId } })
    .then((r) => r.data)

/** Fetch all secrets for the org (no agent_id filter). Returns all secrets the
 *  current user can see — for admins/owners this includes org-level secrets. */
const fetchAllSecrets = (): Promise<Page<VaultSecret>> =>
  authClient.get<Page<VaultSecret>>('/vault/secrets').then((r) => r.data)

const fetchSecretById = (id: string): Promise<VaultSecretWithValue> =>
  authClient.get<VaultSecretWithValue>(`/vault/secrets/${id}`).then((r) => r.data)

const createSecret = (payload: VaultSecretCreate & { agent_id: string | null }): Promise<VaultSecret> =>
  authClient.post<VaultSecret>('/vault/secrets', payload).then((r) => r.data)

const deleteSecret = (id: string): Promise<void> =>
  authClient.delete(`/vault/secrets/${id}`).then(() => undefined)

// ── Helpers ────────────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const now = Date.now()
  const then = new Date(iso).getTime()
  const diff = Math.floor((now - then) / 1000)

  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)}d ago`
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

// ── Icons ─────────────────────────────────────────────────────────────────────

const EyeOpenIcon = (): React.ReactElement => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>
)

const EyeClosedIcon = (): React.ReactElement => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
    <line x1="1" y1="1" x2="23" y2="23"/>
  </svg>
)

const PencilIcon = (): React.ReactElement => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
  </svg>
)

const TrashIcon = (): React.ReactElement => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <polyline points="3 6 5 6 21 6"/>
    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
    <path d="M10 11v6M14 11v6"/>
    <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
  </svg>
)

const LockIcon = (): React.ReactElement => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="3" y="11" width="18" height="11" rx="1"/>
    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
  </svg>
)

const InfoIcon = (): React.ReactElement => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="12" cy="12" r="10"/>
    <line x1="12" y1="8" x2="12" y2="12"/>
    <line x1="12" y1="16" x2="12.01" y2="16"/>
  </svg>
)

const BuildingIcon = (): React.ReactElement => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="2" y="3" width="20" height="18" rx="1"/>
    <path d="M8 21V8h8v13"/>
    <path d="M8 3v2M16 3v2"/>
    <path d="M2 8h20"/>
  </svg>
)

// ── Add / Rotate Secret Modal ──────────────────────────────────────────────────

interface SecretFormModalProps {
  isOpen: boolean
  onClose: () => void
  /** null for org-level secrets, a UUID string for agent-scoped secrets */
  agentId: string | null
  rotateTarget: VaultSecret | null
  /** Query cache key to invalidate on success */
  queryKey: unknown[]
}

function SecretFormModal({
  isOpen,
  onClose,
  agentId,
  rotateTarget,
  queryKey,
}: SecretFormModalProps): React.ReactElement | null {
  const queryClient = useQueryClient()
  const isRotating = rotateTarget !== null

  const [name, setName] = useState('')
  const [value, setValue] = useState('')
  const [showValue, setShowValue] = useState(false)
  const [error, setError] = useState<string | null>(null)

  React.useEffect(() => {
    if (isOpen) {
      setName(isRotating ? rotateTarget.name : '')
      setValue('')
      setShowValue(false)
      setError(null)
    }
  }, [isOpen, isRotating, rotateTarget])

  const mutation = useMutation({
    mutationFn: createSecret,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey })
      onClose()
    },
    onError: () => {
      setError('Failed to save secret. Please try again.')
    },
  })

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault()
    if (!name.trim() || !value.trim()) return
    setError(null)
    mutation.mutate({ name: name.trim(), value: value.trim(), agent_id: agentId })
  }

  const handleClose = (): void => {
    setError(null)
    onClose()
  }

  const inputClass = "w-full bg-base border border-border text-primary text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/30 transition-all"
  const labelClass = "block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest"

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title={isRotating ? 'Update Secret' : 'Add Secret'}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="secret-name" className={labelClass}>
            Name <span className="text-error normal-case">*</span>
          </label>
          {isRotating ? (
            <div className="px-3 py-2 bg-base border border-border rounded-lg">
              <span className="font-mono text-sm text-accent-light">{rotateTarget?.name}</span>
            </div>
          ) : (
            <input
              id="secret-name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value.toUpperCase())}
              placeholder="GITHUB_TOKEN"
              className={`${inputClass} font-mono uppercase`}
            />
          )}
        </div>

        <div>
          <label htmlFor="secret-value" className={labelClass}>
            Value <span className="text-error normal-case">*</span>
          </label>
          <div className="relative">
            <input
              id="secret-value"
              type={showValue ? 'text' : 'password'}
              required
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="••••••••"
              className={`${inputClass} pr-9 font-mono`}
            />
            <button
              type="button"
              onClick={() => setShowValue((v) => !v)}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-secondary transition-colors"
              aria-label={showValue ? 'Hide value' : 'Show value'}
            >
              {showValue ? <EyeClosedIcon /> : <EyeOpenIcon />}
            </button>
          </div>
          {isRotating && (
            <p className="text-xs text-muted mt-1.5">
              Submitting will overwrite the existing value.
            </p>
          )}
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
            isLoading={mutation.isPending}
            disabled={mutation.isPending || !name.trim() || !value.trim()}
          >
            {isRotating ? 'Update Secret' : 'Add Secret'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

// ── Skeleton rows ──────────────────────────────────────────────────────────────

function SkeletonRow(): React.ReactElement {
  return (
    <tr className="border-b border-border">
      {[5, 3, 6, 2].map((w, i) => (
        <td key={i} className="py-3 px-4">
          <div className="skeleton-shimmer h-4 rounded" style={{ width: `${w * 14}px` }} />
        </td>
      ))}
    </tr>
  )
}

// ── Shared secrets table rows ──────────────────────────────────────────────────

interface SecretsRowsProps {
  secrets: VaultSecret[]
  isLoading: boolean
  revealedValues: Map<string, string>
  revealingId: string | null
  onReveal: (secret: VaultSecret) => Promise<void>
  onRotate: (secret: VaultSecret) => void
  onDelete: (secret: VaultSecret) => void
  emptyMessage: React.ReactNode
}

function SecretsRows({
  secrets,
  isLoading,
  revealedValues,
  revealingId,
  onReveal,
  onRotate,
  onDelete,
  emptyMessage,
}: SecretsRowsProps): React.ReactElement {
  if (isLoading) {
    return (
      <>
        <SkeletonRow />
        <SkeletonRow />
        <SkeletonRow />
      </>
    )
  }

  if (secrets.length === 0) {
    return (
      <tr>
        <td colSpan={4} className="py-12 px-4 text-center">
          {emptyMessage}
        </td>
      </tr>
    )
  }

  return (
    <>
      {secrets.map((secret) => {
        const revealedValue = revealedValues.get(secret.id)
        const isRevealed = revealedValue !== undefined
        const isRevealing = revealingId === secret.id

        return (
          <tr
            key={secret.id}
            className="group border-b border-border hover:bg-white/[0.025] transition-colors"
          >
            <td className="py-3 px-4">
              <span className="font-mono text-sm text-accent-light">
                {secret.name}
              </span>
            </td>

            <td className="py-3 px-4 font-mono text-xs text-muted" title={new Date(secret.updated_at).toLocaleString()}>
              {relativeTime(secret.updated_at)}
            </td>

            <td className="py-3 px-4">
              <div className="flex items-center gap-2">
                {isRevealed ? (
                  <>
                    <span className="font-mono text-xs text-teal-light break-all">
                      {revealedValue}
                    </span>
                    <CopyButton text={revealedValue} />
                  </>
                ) : (
                  <span className="font-mono text-xs text-muted">
                    {isRevealing ? 'Loading…' : '••••••••'}
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => void onReveal(secret)}
                  disabled={isRevealing}
                  className="text-secondary hover:text-primary border border-border hover:border-border-strong px-2 py-1 rounded-md text-xs transition-all disabled:cursor-wait flex items-center gap-1"
                  aria-label={isRevealed ? 'Hide value' : 'Reveal value'}
                >
                  {isRevealed ? <EyeClosedIcon /> : <EyeOpenIcon />}
                  <span>{isRevealed ? 'Hide' : 'Reveal'}</span>
                </button>
              </div>
            </td>

            <td className="py-3 px-4 text-right">
              <div className="flex items-center justify-end gap-1">
                <button
                  type="button"
                  onClick={() => onRotate(secret)}
                  className="text-secondary hover:text-primary border border-border hover:border-border-strong px-2 py-1.5 rounded-md text-xs transition-all flex items-center gap-1"
                  aria-label="Update secret"
                  title="Update"
                >
                  <PencilIcon />
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(secret)}
                  className="text-error hover:bg-error/10 border border-transparent hover:border-error/20 px-2 py-1.5 rounded-md text-xs transition-all flex items-center gap-1"
                  aria-label="Delete secret"
                  title="Delete"
                >
                  <TrashIcon />
                </button>
              </div>
            </td>
          </tr>
        )
      })}
    </>
  )
}

// ── Org Secrets Section ────────────────────────────────────────────────────────

function OrgSecretsSection(): React.ReactElement {
  const queryClient = useQueryClient()

  const [addOpen, setAddOpen] = useState(false)
  const [rotateTarget, setRotateTarget] = useState<VaultSecret | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<VaultSecret | null>(null)
  const [revealedValues, setRevealedValues] = useState<Map<string, string>>(new Map())
  const [revealingId, setRevealingId] = useState<string | null>(null)

  // Auto-hide revealed secrets after 30 seconds
  useEffect(() => {
    if (revealedValues.size === 0) return
    const timer = setTimeout(() => setRevealedValues(new Map()), 30_000)
    return () => clearTimeout(timer)
  }, [revealedValues])

  const { data: allSecretsPage, isLoading } = useQuery<Page<VaultSecret>>({
    queryKey: ['vault', 'org'],
    queryFn: fetchAllSecrets,
  })

  const orgSecrets = (allSecretsPage?.items ?? []).filter((s) => s.agent_id === null)

  const deleteMutation = useMutation({
    mutationFn: deleteSecret,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['vault', 'org'] })
    },
    onError: (err) => {
      console.error('Failed to delete org secret', err)
      void queryClient.invalidateQueries({ queryKey: ['vault', 'org'] })
    },
  })

  const handleDeleteConfirm = (): void => {
    if (deleteTarget) {
      deleteMutation.mutate(deleteTarget.id)
      setDeleteTarget(null)
    }
  }

  const handleReveal = async (secret: VaultSecret): Promise<void> => {
    if (revealedValues.has(secret.id)) {
      setRevealedValues((prev) => {
        const next = new Map(prev)
        next.delete(secret.id)
        return next
      })
      return
    }
    setRevealingId(secret.id)
    try {
      const data = await fetchSecretById(secret.id)
      setRevealedValues((prev) => new Map(prev).set(secret.id, data.value))
    } catch (err) {
      console.error('Failed to reveal org secret', err)
    } finally {
      setRevealingId(null)
    }
  }

  return (
    <div className="mb-8">
      {/* Section header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <BuildingIcon />
          <div>
            <p className="text-primary text-sm font-semibold">Organization Secrets</p>
            <p className="text-secondary text-xs mt-0.5">
              Injected into MCP server request headers. Not scoped to a specific agent.
            </p>
          </div>
        </div>
        <Button size="sm" onClick={() => setAddOpen(true)}>
          + Add Org Secret
        </Button>
      </div>

      {/* Info callout */}
      <div className="flex items-start gap-2 text-xs text-muted mb-4 bg-elevated/50 border border-border rounded-lg px-3 py-2">
        <InfoIcon />
        <span>
          Organization secrets are available to all MCP servers as header values (e.g.{' '}
          <code className="font-mono text-accent-light bg-accent/10 px-1 rounded">{'{{GITHUB_TOKEN}}'}</code>).
          They are not associated with any single agent and are visible only to owners and admins.
        </span>
      </div>

      {/* Table */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <table className="min-w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Name</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Last Updated</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Value</th>
              <th className="py-3 px-4 text-right text-xs font-mono text-muted uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody>
            <SecretsRows
              secrets={orgSecrets}
              isLoading={isLoading}
              revealedValues={revealedValues}
              revealingId={revealingId}
              onReveal={handleReveal}
              onRotate={setRotateTarget}
              onDelete={setDeleteTarget}
              emptyMessage={
                <div>
                  <div className="w-8 h-8 rounded-xl bg-accent/10 flex items-center justify-center mx-auto mb-2">
                    <BuildingIcon />
                  </div>
                  <p className="text-primary text-sm font-medium mb-1">No organization secrets</p>
                  <p className="text-secondary text-xs">
                    Add a shared secret to inject it as a header into all MCP server requests.
                  </p>
                </div>
              }
            />
          </tbody>
        </table>
      </div>

      <SecretFormModal
        isOpen={addOpen || rotateTarget !== null}
        onClose={() => {
          setAddOpen(false)
          setRotateTarget(null)
        }}
        agentId={null}
        rotateTarget={rotateTarget}
        queryKey={['vault', 'org']}
      />

      <ConfirmDialog
        isOpen={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDeleteConfirm}
        title="Delete Organization Secret"
        message={`Delete secret "${deleteTarget?.name ?? ''}"? This cannot be undone.`}
        confirmLabel="Delete"
      />
    </div>
  )
}

// ── Agent Secrets Section ──────────────────────────────────────────────────────

interface AgentSectionProps {
  agentId: string
  agentName: string
}

function AgentSecretsSection({ agentId, agentName }: AgentSectionProps): React.ReactElement {
  const queryClient = useQueryClient()

  const [addOpen, setAddOpen] = useState(false)
  const [rotateTarget, setRotateTarget] = useState<VaultSecret | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<VaultSecret | null>(null)
  const [revealedValues, setRevealedValues] = useState<Map<string, string>>(new Map())
  const [revealingId, setRevealingId] = useState<string | null>(null)

  // Auto-hide revealed secrets after 30 seconds
  useEffect(() => {
    if (revealedValues.size === 0) return
    const timer = setTimeout(() => {
      setRevealedValues(new Map())
    }, 30_000)
    return () => clearTimeout(timer)
  }, [revealedValues])

  const { data: secretsPage, isLoading } = useQuery<Page<VaultSecret>>({
    queryKey: ['vault', agentId],
    queryFn: () => fetchSecrets(agentId),
    enabled: !!agentId,
  })

  // Show only agent-scoped secrets (filter out org-level in case the backend
  // returns them when no agent_id filter is applied)
  const agentSecrets = (secretsPage?.items ?? []).filter(
    (s) => s.agent_id !== null
  )

  const deleteMutation = useMutation({
    mutationFn: deleteSecret,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['vault', agentId] })
    },
    onError: (err) => {
      console.error('Failed to delete secret', err)
      void queryClient.invalidateQueries({ queryKey: ['vault', agentId] })
    },
  })

  const handleDeleteConfirm = (): void => {
    if (deleteTarget) {
      deleteMutation.mutate(deleteTarget.id)
      setDeleteTarget(null)
    }
  }

  const handleReveal = async (secret: VaultSecret): Promise<void> => {
    if (revealedValues.has(secret.id)) {
      setRevealedValues((prev) => {
        const next = new Map(prev)
        next.delete(secret.id)
        return next
      })
      return
    }

    setRevealingId(secret.id)
    try {
      const data = await fetchSecretById(secret.id)
      setRevealedValues((prev) => new Map(prev).set(secret.id, data.value))
    } catch (err) {
      console.error('Failed to reveal secret', err)
    } finally {
      setRevealingId(null)
    }
  }

  return (
    <div className="flex-1">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <p className="text-primary text-sm font-semibold">
            Agent Secrets — <span className="text-accent-light">{agentName}</span>
          </p>
          <p className="text-secondary text-xs mt-0.5">Scoped to this agent only.</p>
        </div>
        <Button onClick={() => setAddOpen(true)}>Add Secret</Button>
      </div>

      {/* Security banner */}
      {agentSecrets.length > 0 && (
        <div className="flex items-center gap-2 text-xs text-muted mb-5 bg-elevated/50 border border-border rounded-lg px-3 py-2">
          <LockIcon />
          <span>Values are AES-256-GCM encrypted at rest. Revealed values are never stored by this interface.</span>
        </div>
      )}

      {/* Table */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <table className="min-w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Name</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Last Updated</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Value</th>
              <th className="py-3 px-4 text-right text-xs font-mono text-muted uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody>
            <SecretsRows
              secrets={agentSecrets}
              isLoading={isLoading}
              revealedValues={revealedValues}
              revealingId={revealingId}
              onReveal={handleReveal}
              onRotate={setRotateTarget}
              onDelete={setDeleteTarget}
              emptyMessage={
                <div>
                  <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center mx-auto mb-3">
                    <LockIcon />
                  </div>
                  <p className="text-primary text-sm font-medium mb-1">No secrets stored</p>
                  <p className="text-secondary text-xs mt-1">
                    Add a secret to inject into tool calls using{' '}
                    <code className="font-mono text-accent-light bg-accent/10 px-1 rounded">{'{{SECRET_NAME}}'}</code>.
                  </p>
                </div>
              }
            />
          </tbody>
        </table>
      </div>

      <SecretFormModal
        isOpen={addOpen || rotateTarget !== null}
        onClose={() => {
          setAddOpen(false)
          setRotateTarget(null)
        }}
        agentId={agentId}
        rotateTarget={rotateTarget}
        queryKey={['vault', agentId]}
      />

      <ConfirmDialog
        isOpen={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDeleteConfirm}
        title="Delete Secret"
        message={`Delete secret "${deleteTarget?.name ?? ''}"? This cannot be undone.`}
        confirmLabel="Delete"
      />
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

function Vault(): React.ReactElement {
  const { user } = useAuth()
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)

  const isPrivileged = user?.role === 'owner' || user?.role === 'admin'

  const { data: agentsPage } = useQuery<Page<Agent>>({
    queryKey: ['agents'],
    queryFn: fetchAgents,
  })
  const agents = agentsPage?.items

  useEffect(() => {
    if (!selectedAgentId && agents && agents.length > 0) {
      setSelectedAgentId(agents[0].id)
    }
  }, [agents, selectedAgentId])

  const selectedAgent = agents?.find((a) => a.id === selectedAgentId) ?? null

  return (
    <div className="p-8 animate-fade-in">
      <div className="mb-8">
        <h1 className="font-display text-xl font-semibold tracking-tight text-primary">Vault</h1>
        <p className="text-secondary text-sm mt-1">AES-256-GCM encrypted secrets per agent</p>
      </div>

      {/* Organization Secrets — owners and admins only */}
      {isPrivileged && <OrgSecretsSection />}

      {/* Divider between org and agent sections */}
      {isPrivileged && (
        <div className="flex items-center gap-3 mb-6">
          <div className="flex-1 h-px bg-border" />
          <span className="text-muted text-xs font-semibold uppercase tracking-widest">Agent Secrets</span>
          <div className="flex-1 h-px bg-border" />
        </div>
      )}

      <div className="grid grid-cols-[240px_1fr] gap-6">
        {/* Left panel — agent selector */}
        <div>
          <p className="text-muted text-xs font-semibold uppercase tracking-widest mb-3">
            Agents
          </p>
          <div className="bg-surface border border-border rounded-xl overflow-hidden">
            {!agents || agents.length === 0 ? (
              <div className="px-4 py-5 flex flex-col items-start gap-3">
                <p className="text-secondary text-xs">No agents registered yet.</p>
                <Link
                  to="/agents"
                  className="border border-border hover:border-accent/50 text-secondary hover:text-accent-light px-4 py-2 rounded-lg text-sm transition-all"
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
                    className={`relative w-full text-left flex items-start gap-2.5 px-4 py-3 transition-all duration-150 border-b border-border last:border-0 overflow-hidden ${
                      isSelected
                        ? 'bg-accent/[0.07] border border-border-accent'
                        : 'hover:bg-white/[0.025]'
                    }`}
                  >
                    {isSelected && (
                      <span aria-hidden className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-accent rounded-full" />
                    )}
                    <span
                      className={`w-1.5 h-1.5 rounded-full flex-shrink-0 mt-1.5 ${
                        agent.is_active ? 'bg-success' : 'bg-muted'
                      }`}
                    />
                    <div className="min-w-0">
                      <span className="text-primary text-sm truncate block font-medium">{agent.name}</span>
                      {agent.description && (
                        <span className="text-muted text-xs truncate block">{agent.description}</span>
                      )}
                      <span className="text-muted text-[10px] font-mono">
                        {new Date(agent.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                      </span>
                    </div>
                  </button>
                )
              })
            )}
          </div>
        </div>

        {/* Right panel — agent secrets */}
        {selectedAgent ? (
          <AgentSecretsSection agentId={selectedAgent.id} agentName={selectedAgent.name} />
        ) : (
          <div className="flex flex-col items-center justify-center gap-3 text-center py-20 bg-surface border border-border rounded-xl">
            <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center">
              <svg className="text-accent-light" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="2" y="3" width="20" height="18" rx="1"/>
                <circle cx="12" cy="12" r="4"/>
                <path d="M12 8v1M12 15v1M8 12h1M15 12h1"/>
                <path d="M18 3v18"/>
              </svg>
            </div>
            <div>
              <p className="text-primary text-sm font-medium">Select an agent</p>
              <p className="text-secondary text-xs mt-1 max-w-[200px]">Secrets are encrypted at rest with AES-256-GCM</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default Vault
