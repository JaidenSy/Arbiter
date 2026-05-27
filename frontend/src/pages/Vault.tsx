/**
 * Arbiter — Vault page.
 *
 * Two-panel layout:
 *   Left:  Agent selector list
 *   Right: Secrets table for the selected agent + add/rotate/delete actions
 *
 * Secrets are write-only by default; values can be revealed one at a time
 * via GET /vault/secrets/{id}. Revealed values are held only in local state.
 */

import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { authClient } from '../api/client'
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

const fetchSecretById = (id: string): Promise<VaultSecretWithValue> =>
  authClient.get<VaultSecretWithValue>(`/vault/secrets/${id}`).then((r) => r.data)

const createSecret = (payload: VaultSecretCreate & { agent_id: string }): Promise<VaultSecret> =>
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

// ── Add / Rotate Secret Modal ──────────────────────────────────────────────────

interface SecretFormModalProps {
  isOpen: boolean
  onClose: () => void
  agentId: string
  rotateTarget: VaultSecret | null
}

function SecretFormModal({
  isOpen,
  onClose,
  agentId,
  rotateTarget,
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
      void queryClient.invalidateQueries({ queryKey: ['vault', agentId] })
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

// ── Secrets Table ─────────────────────────────────────────────────────────────

interface SecretsTableProps {
  agentId: string
  agentName: string
}

function SecretsTable({ agentId, agentName }: SecretsTableProps): React.ReactElement {
  const queryClient = useQueryClient()

  const [addOpen, setAddOpen] = useState(false)
  const [rotateTarget, setRotateTarget] = useState<VaultSecret | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<VaultSecret | null>(null)
  const [revealedValues, setRevealedValues] = useState<Map<string, string>>(new Map())
  const [revealingId, setRevealingId] = useState<string | null>(null)

  const { data: secretsPage, isLoading } = useQuery<Page<VaultSecret>>({
    queryKey: ['vault', agentId],
    queryFn: () => fetchSecrets(agentId),
    enabled: !!agentId,
  })
  const secrets = secretsPage?.items

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

  const hasSecrets = secrets && secrets.length > 0

  return (
    <div className="flex-1">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <p className="text-primary text-sm font-semibold">
            Vault — <span className="text-accent-light">{agentName}</span>
          </p>
        </div>
        <Button onClick={() => setAddOpen(true)}>Add Secret</Button>
      </div>

      {/* Security banner */}
      {hasSecrets && (
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
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Stored</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Value</th>
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
            ) : !secrets || secrets.length === 0 ? (
              <tr>
                <td colSpan={4} className="py-16 px-4 text-center">
                  <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center mx-auto mb-3">
                    <LockIcon />
                  </div>
                  <p className="text-primary text-sm font-medium mb-1">No secrets stored</p>
                  <p className="text-secondary text-xs mt-1">
                    Add a secret to inject into tool calls using{' '}
                    <code className="font-mono text-accent-light bg-accent/10 px-1 rounded">{'{{SECRET_NAME}}'}</code>.
                  </p>
                </td>
              </tr>
            ) : (
              secrets.map((secret) => {
                const revealedValue = revealedValues.get(secret.id)
                const isRevealed = revealedValue !== undefined
                const isRevealing = revealingId === secret.id

                return (
                  <tr
                    key={secret.id}
                    className={`group border-b border-border hover:bg-white/[0.025] transition-colors ${''}`}
                  >
                    <td className="py-3 px-4">
                      <span className="font-mono text-sm text-accent-light">
                        {secret.name}
                      </span>
                    </td>

                    <td className="py-3 px-4 font-mono text-xs text-muted">
                      {relativeTime(secret.created_at)}
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
                          onClick={() => void handleReveal(secret)}
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
                          onClick={() => setRotateTarget(secret)}
                          className="text-secondary hover:text-primary border border-border hover:border-border-strong px-2 py-1.5 rounded-md text-xs transition-all flex items-center gap-1"
                          aria-label="Update secret"
                          title="Update"
                        >
                          <PencilIcon />
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeleteTarget(secret)}
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
              })
            )}
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
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)

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

        {/* Right panel — secrets */}
        {selectedAgent ? (
          <SecretsTable agentId={selectedAgent.id} agentName={selectedAgent.name} />
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
