/**
 * Arbiter: Organization page.
 *
 * Route: /organization (protected, with sidebar)
 * Shows org info with rename (owner only), member list, and invite management.
 */

import React, { useEffect, useState, useCallback } from 'react'
import { authClient } from '../api/client'
import type { Page } from '../api/types'
import { useAuth } from '../context/AuthContext'
import ConfirmDialog from '../components/ConfirmDialog'

// ── Types ─────────────────────────────────────────────────────────────────────

interface OrgInfo {
  id: string
  name: string
  slug: string
  plan_tier: string
  created_at: string
}

interface Member {
  id: string
  email: string
  display_name: string | null
  role: string
  is_verified: boolean
  created_at: string
}

interface Invite {
  id: string
  email: string
  role: string
  created_at: string
  expires_at: string
  accepted_at: string | null
}

const ACCESS_KEY = 'arbiter_access_token'
const REFRESH_KEY = 'arbiter_refresh_token'

const VALID_ROLES = ['owner', 'admin', 'member'] as const
type Role = typeof VALID_ROLES[number]

const ROLE_BADGE: Record<string, string> = {
  owner: 'bg-accent/15 text-accent-light border-border-accent',
  admin: 'bg-teal/10 text-teal-light border-teal/20',
  member: 'bg-elevated text-secondary border-border',
}

const PLAN_BADGE: Record<string, string> = {
  free: 'bg-elevated text-secondary border-border',
  pro: 'bg-accent/15 text-accent-light border-border-accent',
  enterprise: 'bg-warning/10 text-warning border-warning/20',
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function canManage(currentRole: string): boolean {
  return currentRole === 'owner' || currentRole === 'admin'
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SelectField({
  value,
  onChange,
  options,
  className = '',
}: {
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
  className?: string
}) {
  return (
    <div className={`relative ${className}`}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none w-full bg-base border border-border-strong text-primary text-sm px-3.5 py-2.5 pr-9 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent/60 transition-all cursor-pointer"
      >
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <svg className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
      </svg>
    </div>
  )
}

// ── Component ─────────────────────────────────────────────────────────────────

function Organization(): React.ReactElement {
  const { user } = useAuth()
  const currentRole = user?.role ?? 'member'
  const isOwner = currentRole === 'owner'
  const isManager = canManage(currentRole)

  const [org, setOrg] = useState<OrgInfo | null>(null)
  const [members, setMembers] = useState<Member[]>([])
  const [invites, setInvites] = useState<Invite[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Rename state
  const [renaming, setRenaming] = useState(false)
  const [renameValue, setRenameValue] = useState('')
  const [renameError, setRenameError] = useState('')
  const [renameSaving, setRenameSaving] = useState(false)

  // Remove member confirm dialog state
  const [removeMemberId, setRemoveMemberId] = useState<string | null>(null)

  // Leave org state
  const [showLeaveConfirm, setShowLeaveConfirm] = useState(false)
  const [leaveError, setLeaveError] = useState('')
  const [leaving, setLeaving] = useState(false)

  // Invite modal state
  const [showInvite, setShowInvite] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<Role>('member')
  const [inviteError, setInviteError] = useState('')
  const [inviteSubmitting, setInviteSubmitting] = useState(false)
  const [inviteSuccess, setInviteSuccess] = useState('')

  const fetchData = useCallback(async () => {
    setError('')
    try {
      const [orgRes, membersRes, invitesRes] = await Promise.all([
        authClient.get<OrgInfo>('/org'),
        authClient.get<Page<Member>>('/org/members'),
        isManager ? authClient.get<Page<Invite>>('/org/invites') : Promise.resolve(null),
      ])
      setOrg(orgRes.data)
      setMembers(membersRes.data.items)
      if (invitesRes) setInvites(invitesRes.data.items)
    } catch {
      setError('Failed to load organization data.')
    } finally {
      setLoading(false)
    }
  }, [isManager])

  useEffect(() => { void fetchData() }, [fetchData])

  function startRename() {
    setRenameValue(org?.name ?? '')
    setRenameError('')
    setRenaming(true)
  }

  async function saveRename() {
    const name = renameValue.trim()
    if (!name) { setRenameError('Name cannot be empty'); return }
    setRenameSaving(true)
    setRenameError('')
    try {
      const res = await authClient.patch<OrgInfo>('/org', { name })
      setOrg(res.data)
      setRenaming(false)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setRenameError(msg ?? 'Failed to rename organization.')
    } finally {
      setRenameSaving(false)
    }
  }

  async function handleRoleChange(memberId: string, newRole: Role) {
    try {
      await authClient.patch(`/org/members/${memberId}`, { role: newRole })
      setMembers(prev => prev.map(m => m.id === memberId ? { ...m, role: newRole } : m))
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Failed to update role.')
    }
  }

  async function doRemoveMember(memberId: string) {
    try {
      await authClient.delete(`/org/members/${memberId}`)
      setMembers(prev => prev.filter(m => m.id !== memberId))
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Failed to remove member.')
    }
  }

  async function doLeaveOrg() {
    setLeaving(true)
    setLeaveError('')
    try {
      // Returns a fresh token pair with the next org active (or a new
      // personal org when no other membership remains).
      const res = await authClient.post<{ access_token: string; refresh_token: string }>(
        '/org/leave'
      )
      localStorage.setItem(ACCESS_KEY, res.data.access_token)
      localStorage.setItem(REFRESH_KEY, res.data.refresh_token)
      // Hard reload: every org-scoped view must rehydrate for the new org.
      window.location.href = '/'
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setLeaveError(msg ?? 'Failed to leave organization.')
      setLeaving(false)
      setShowLeaveConfirm(false)
    }
  }

  async function handleCancelInvite(inviteId: string) {
    try {
      await authClient.delete(`/org/invites/${inviteId}`)
      setInvites(prev => prev.filter(i => i.id !== inviteId))
    } catch {
      setError('Failed to cancel invite.')
    }
  }

  async function handleSendInvite(e: React.FormEvent) {
    e.preventDefault()
    setInviteError('')
    setInviteSuccess('')
    setInviteSubmitting(true)
    try {
      const res = await authClient.post<Invite>('/org/invites', { email: inviteEmail, role: inviteRole })
      setInvites(prev => [res.data, ...prev])
      setInviteSuccess(`Invite sent to ${inviteEmail}`)
      setInviteEmail('')
      setInviteRole('member')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setInviteError(msg ?? 'Failed to send invite.')
    } finally {
      setInviteSubmitting(false)
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">
        <div>
          <div className="h-5 skeleton-shimmer rounded w-40 mb-2" />
          <div className="h-3 skeleton-shimmer rounded w-64" />
        </div>
        <div className="bg-surface border border-border rounded-xl overflow-hidden">
          <div className="border-b border-border px-5 py-3 flex gap-8">
            {['w-24', 'w-16', 'w-20'].map((w, i) => (
              <div key={i} className={`h-2.5 skeleton-shimmer rounded ${w}`} />
            ))}
          </div>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex items-center gap-8 px-5 py-3.5 border-b border-border last:border-0">
              <div className="flex-1 space-y-1.5">
                <div className="h-3 skeleton-shimmer rounded w-32" />
                <div className="h-2.5 skeleton-shimmer rounded w-48" />
              </div>
              <div className="h-5 skeleton-shimmer rounded-full w-16" />
              <div className="h-3 skeleton-shimmer rounded w-24" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight text-primary">Organization</h1>
        <p className="text-secondary text-sm mt-0.5">Manage your organization settings and members</p>
      </div>

      {error && (
        <div className="flex items-center gap-2 bg-error/8 border border-error/20 rounded-lg px-4 py-2.5">
          <span className="w-1.5 h-1.5 rounded-full bg-error flex-shrink-0" />
          <p className="text-error text-sm">{error}</p>
        </div>
      )}

      {/* Org info card */}
      {org && (
        <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-secondary uppercase tracking-widest mb-1">Organization name</p>
              {renaming ? (
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') void saveRename(); if (e.key === 'Escape') setRenaming(false) }}
                    autoFocus
                    className="bg-base border border-border-strong text-primary text-sm px-3 py-1.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent/60 w-full max-w-xs transition-all"
                  />
                  <button
                    onClick={() => void saveRename()}
                    disabled={renameSaving}
                    className="text-xs font-medium text-accent-light hover:text-white transition-colors disabled:opacity-50"
                  >
                    {renameSaving ? 'Saving…' : 'Save'}
                  </button>
                  <button onClick={() => setRenaming(false)} className="text-xs text-muted hover:text-secondary transition-colors">Cancel</button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <span className="text-primary font-semibold text-base">{org.name}</span>
                  {isOwner && (
                    <button onClick={startRename} className="text-muted hover:text-secondary transition-colors" aria-label="Rename organization">
                      <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
                      </svg>
                    </button>
                  )}
                </div>
              )}
              {renameError && <p className="text-error text-xs mt-1">{renameError}</p>}
            </div>
            <span className={`inline-block text-xs font-medium border rounded-full px-2.5 py-0.5 flex-shrink-0 ${PLAN_BADGE[org.plan_tier] ?? PLAN_BADGE['free']}`}>
              {org.plan_tier}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-4 pt-1 border-t border-border">
            <div>
              <p className="text-xs text-muted mb-0.5">Slug</p>
              <p className="text-sm text-secondary font-mono">{org.slug}</p>
            </div>
            <div>
              <p className="text-xs text-muted mb-0.5">Created</p>
              <p className="text-sm text-secondary">{formatDate(org.created_at)}</p>
            </div>
          </div>
        </div>
      )}

      {/* Members section */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-primary">Members</h2>
          <p className="text-secondary text-sm mt-0.5">{members.length} member{members.length !== 1 ? 's' : ''}</p>
        </div>
        {isManager && (
          <button
            onClick={() => { setShowInvite(true); setInviteSuccess(''); setInviteError('') }}
            className="bg-accent hover:bg-accent-light text-white font-semibold text-sm py-2 px-4 rounded-lg transition-all duration-150"
          >
            + Invite member
          </button>
        )}
      </div>

      {/* Members table */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left text-xs font-semibold text-secondary uppercase tracking-widest px-5 py-3">Member</th>
              <th className="text-left text-xs font-semibold text-secondary uppercase tracking-widest px-5 py-3">Role</th>
              <th className="text-left text-xs font-semibold text-secondary uppercase tracking-widest px-5 py-3">Joined</th>
              {isManager && <th className="px-5 py-3" />}
            </tr>
          </thead>
          <tbody>
            {members.map((m) => {
              const isSelf = m.id === user?.id
              return (
                <tr key={m.id} className="border-b border-border last:border-0 hover:bg-white/[0.02] transition-colors">
                  <td className="px-5 py-3.5">
                    <div className="font-medium text-primary">{m.display_name ?? m.email}</div>
                    {m.display_name && <div className="text-muted text-xs">{m.email}</div>}
                    {!m.is_verified && (
                      <span className="inline-block mt-0.5 text-xs text-warning bg-warning/10 border border-warning/20 rounded px-1.5 py-0.5">unverified</span>
                    )}
                  </td>
                  <td className="px-5 py-3.5">
                    {isManager && !isSelf ? (
                      <SelectField
                        value={m.role}
                        onChange={(v) => void handleRoleChange(m.id, v as Role)}
                        options={VALID_ROLES.map(r => ({ value: r, label: r }))}
                        className="w-28"
                      />
                    ) : (
                      <span className={`inline-block text-xs font-medium border rounded-full px-2.5 py-0.5 ${ROLE_BADGE[m.role] ?? ROLE_BADGE['member']}`}>
                        {m.role}
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-3.5 text-secondary">{formatDate(m.created_at)}</td>
                  {isManager && (
                    <td className="px-5 py-3.5 text-right">
                      {!isSelf && (
                        <button
                          onClick={() => setRemoveMemberId(m.id)}
                          className="text-muted hover:text-error text-xs transition-colors"
                        >
                          Remove
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pending invites */}
      {isManager && invites.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-secondary uppercase tracking-widest mb-3">Pending Invites</h2>
          <div className="bg-surface border border-border rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left text-xs font-semibold text-secondary uppercase tracking-widest px-5 py-3">Email</th>
                  <th className="text-left text-xs font-semibold text-secondary uppercase tracking-widest px-5 py-3">Role</th>
                  <th className="text-left text-xs font-semibold text-secondary uppercase tracking-widest px-5 py-3">Expires</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody>
                {invites.map((inv) => (
                  <tr key={inv.id} className="border-b border-border last:border-0 hover:bg-white/[0.02] transition-colors">
                    <td className="px-5 py-3.5 text-primary">{inv.email}</td>
                    <td className="px-5 py-3.5">
                      <span className={`inline-block text-xs font-medium border rounded-full px-2.5 py-0.5 ${ROLE_BADGE[inv.role] ?? ROLE_BADGE['member']}`}>
                        {inv.role}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-secondary">{formatDate(inv.expires_at)}</td>
                    <td className="px-5 py-3.5 text-right">
                      <button
                        onClick={() => void handleCancelInvite(inv.id)}
                        className="text-muted hover:text-error text-xs transition-colors"
                      >
                        Cancel
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Leave organization */}
      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-primary">Leave this organization</p>
            {isOwner ? (
              <p className="text-secondary text-xs mt-0.5">
                You must transfer ownership before leaving. Promote another member to owner first.
              </p>
            ) : (
              <p className="text-secondary text-xs mt-0.5">
                Your agents, secrets, and MCP servers in this organization will be reassigned to
                the org owner. This cannot be undone.
              </p>
            )}
            {leaveError && <p className="text-error text-xs mt-1.5">{leaveError}</p>}
          </div>
          <button
            onClick={() => { setLeaveError(''); setShowLeaveConfirm(true) }}
            disabled={leaving || isOwner}
            className="flex-shrink-0 border border-error/30 text-error hover:bg-error/10 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium py-2 px-4 rounded-lg transition-colors"
          >
            {leaving ? 'Leaving…' : 'Leave organization'}
          </button>
        </div>
      </div>

      {/* Remove member confirm dialog */}
      <ConfirmDialog
        isOpen={removeMemberId !== null}
        onClose={() => setRemoveMemberId(null)}
        onConfirm={() => { if (removeMemberId) void doRemoveMember(removeMemberId) }}
        title="Remove member"
        message="Remove this member from your organization? Their account stays active, but they lose access here and any agents they created in this organization are deactivated."
        confirmLabel="Remove"
      />

      {/* Leave org confirm dialog */}
      <ConfirmDialog
        isOpen={showLeaveConfirm}
        onClose={() => setShowLeaveConfirm(false)}
        onConfirm={() => void doLeaveOrg()}
        title="Leave organization"
        message={`Your agents, secrets, and MCP servers in ${org?.name ?? 'this organization'} will be reassigned to the org owner. This cannot be undone.`}
        confirmLabel="Leave"
      />

      {/* Invite modal */}
      {showInvite && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setShowInvite(false)}>
          <div className="bg-surface border border-border-strong rounded-xl p-6 w-full max-w-sm shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-base font-bold text-primary mb-4">Invite a member</h2>

            {inviteSuccess ? (
              <div className="text-center py-4">
                <div className="w-10 h-10 rounded-full bg-success/10 border border-success/20 flex items-center justify-center mx-auto mb-3">
                  <svg className="w-5 h-5 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <p className="text-secondary text-sm">{inviteSuccess}</p>
                <button onClick={() => setShowInvite(false)} className="mt-4 text-accent-light hover:text-white text-sm font-medium transition-colors">
                  Done
                </button>
              </div>
            ) : (
              <form onSubmit={(e) => void handleSendInvite(e)} className="flex flex-col gap-4">
                <div>
                  <label className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">Email</label>
                  <input
                    type="email"
                    required
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="colleague@company.com"
                    className="w-full bg-base border border-border-strong text-primary text-sm px-3.5 py-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent/60 transition-all placeholder:text-muted"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">Role</label>
                  <SelectField
                    value={inviteRole}
                    onChange={(v) => setInviteRole(v as Role)}
                    options={[
                      { value: 'member', label: 'Member' },
                      { value: 'admin', label: 'Admin' },
                      ...(currentRole === 'owner' ? [{ value: 'owner', label: 'Owner' }] : []),
                    ]}
                  />
                </div>

                {inviteError && (
                  <div className="flex items-center gap-2 bg-error/8 border border-error/20 rounded-lg px-3 py-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-error flex-shrink-0" />
                    <p className="text-error text-xs">{inviteError}</p>
                  </div>
                )}

                <div className="flex gap-3 mt-1">
                  <button
                    type="button"
                    onClick={() => setShowInvite(false)}
                    className="flex-1 border border-border text-secondary hover:text-primary text-sm font-medium py-2.5 rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={inviteSubmitting}
                    className="flex-1 bg-accent hover:bg-accent-light disabled:opacity-50 text-white font-semibold text-sm py-2.5 rounded-lg transition-all"
                  >
                    {inviteSubmitting ? 'Sending…' : 'Send invite'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default Organization
