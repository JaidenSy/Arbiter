/**
 * NexVault — Members page.
 *
 * Route: /members (protected, with sidebar)
 * Owners and admins can list members, change roles, remove members, and invite new ones.
 */

import React, { useEffect, useState, useCallback } from 'react'
import { authClient } from '../api/client'
import { useAuth } from '../context/AuthContext'

// ── Types ─────────────────────────────────────────────────────────────────────

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

const VALID_ROLES = ['owner', 'admin', 'member'] as const
type Role = typeof VALID_ROLES[number]

const ROLE_BADGE: Record<string, string> = {
  owner: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  admin: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
  member: 'bg-white/5 text-secondary border-white/10',
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function canManage(currentRole: string): boolean {
  return currentRole === 'owner' || currentRole === 'admin'
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

// ── Component ─────────────────────────────────────────────────────────────────

function Members(): React.ReactElement {
  const { user } = useAuth()
  const currentRole = user?.role ?? 'member'
  const isManager = canManage(currentRole)

  const [members, setMembers] = useState<Member[]>([])
  const [invites, setInvites] = useState<Invite[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

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
      const [membersRes, invitesRes] = await Promise.all([
        authClient.get<Member[]>('/org/members'),
        isManager ? authClient.get<Invite[]>('/org/invites') : Promise.resolve(null),
      ])
      setMembers(membersRes.data)
      if (invitesRes) setInvites(invitesRes.data)
    } catch {
      setError('Failed to load members.')
    } finally {
      setLoading(false)
    }
  }, [isManager])

  useEffect(() => { void fetchData() }, [fetchData])

  async function handleRoleChange(memberId: string, newRole: Role) {
    try {
      await authClient.patch(`/org/members/${memberId}`, { role: newRole })
      setMembers(prev => prev.map(m => m.id === memberId ? { ...m, role: newRole } : m))
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Failed to update role.')
    }
  }

  async function handleRemoveMember(memberId: string) {
    if (!confirm('Remove this member from your organization?')) return
    try {
      await authClient.delete(`/org/members/${memberId}`)
      setMembers(prev => prev.filter(m => m.id !== memberId))
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Failed to remove member.')
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
      <div className="flex items-center justify-center h-48">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-primary">Members</h1>
          <p className="text-secondary text-sm mt-0.5">{members.length} member{members.length !== 1 ? 's' : ''} in your organization</p>
        </div>
        {isManager && (
          <button
            onClick={() => { setShowInvite(true); setInviteSuccess(''); setInviteError('') }}
            className="bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 text-white font-semibold text-sm py-2 px-4 rounded-lg transition-all duration-150"
          >
            + Invite member
          </button>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 bg-error/8 border border-error/20 rounded-lg px-4 py-2.5">
          <span className="w-1.5 h-1.5 rounded-full bg-error flex-shrink-0" />
          <p className="text-error text-sm">{error}</p>
        </div>
      )}

      {/* Members table */}
      <div className="bg-card border border-white/[0.08] rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/[0.06]">
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
                <tr key={m.id} className="border-b border-white/[0.04] last:border-0 hover:bg-white/[0.02] transition-colors">
                  <td className="px-5 py-3.5">
                    <div className="font-medium text-primary">{m.display_name ?? m.email}</div>
                    {m.display_name && <div className="text-muted text-xs">{m.email}</div>}
                    {!m.is_verified && (
                      <span className="inline-block mt-0.5 text-xs text-warning bg-warning/10 border border-warning/20 rounded px-1.5 py-0.5">unverified</span>
                    )}
                  </td>
                  <td className="px-5 py-3.5">
                    {isManager && !isSelf ? (
                      <select
                        value={m.role}
                        onChange={(e) => handleRoleChange(m.id, e.target.value as Role)}
                        className="bg-elevated/80 border border-white/[0.1] text-primary text-xs rounded-md px-2 py-1 focus:outline-none focus:ring-1 focus:ring-accent/60"
                      >
                        {VALID_ROLES.map(r => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
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
                          onClick={() => handleRemoveMember(m.id)}
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
          <div className="bg-card border border-white/[0.08] rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  <th className="text-left text-xs font-semibold text-secondary uppercase tracking-widest px-5 py-3">Email</th>
                  <th className="text-left text-xs font-semibold text-secondary uppercase tracking-widest px-5 py-3">Role</th>
                  <th className="text-left text-xs font-semibold text-secondary uppercase tracking-widest px-5 py-3">Expires</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody>
                {invites.map((inv) => (
                  <tr key={inv.id} className="border-b border-white/[0.04] last:border-0 hover:bg-white/[0.02] transition-colors">
                    <td className="px-5 py-3.5 text-primary">{inv.email}</td>
                    <td className="px-5 py-3.5">
                      <span className={`inline-block text-xs font-medium border rounded-full px-2.5 py-0.5 ${ROLE_BADGE[inv.role] ?? ROLE_BADGE['member']}`}>
                        {inv.role}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-secondary">{formatDate(inv.expires_at)}</td>
                    <td className="px-5 py-3.5 text-right">
                      <button
                        onClick={() => handleCancelInvite(inv.id)}
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

      {/* Invite modal */}
      {showInvite && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setShowInvite(false)}>
          <div className="bg-card border border-white/[0.12] rounded-xl p-6 w-full max-w-sm shadow-2xl" onClick={(e) => e.stopPropagation()}>
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
              <form onSubmit={handleSendInvite} className="flex flex-col gap-4">
                <div>
                  <label className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">Email</label>
                  <input
                    type="email"
                    required
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="colleague@company.com"
                    className="w-full bg-elevated/80 border border-white/[0.1] text-primary text-sm px-3.5 py-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent/60 transition-all"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">Role</label>
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value as Role)}
                    className="w-full bg-elevated/80 border border-white/[0.1] text-primary text-sm px-3.5 py-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent/60 transition-all"
                  >
                    <option value="member">Member</option>
                    <option value="admin">Admin</option>
                    {currentRole === 'owner' && <option value="owner">Owner</option>}
                  </select>
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
                    className="flex-1 border border-white/[0.1] text-secondary hover:text-primary text-sm font-medium py-2.5 rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={inviteSubmitting}
                    className="flex-1 bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 disabled:opacity-50 text-white font-semibold text-sm py-2.5 rounded-lg transition-all"
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

export default Members
