/**
 * Arbiter: Org switcher.
 *
 * Rendered inside the sidebar user popover.  Lists every organization the
 * user belongs to (GET /me/orgs), switches the active one (POST /org/switch
 * → fresh token pair → hard reload so all org-scoped views rehydrate), and
 * offers a "New organization" modal (POST /org: the backend switches the
 * active org on creation, so a reload is enough).
 *
 * Mounted only while the popover is open, so the list is fetched lazily.
 */

import React, { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { authClient } from '../api/client'
import { useAuth } from '../context/AuthContext'

const ACCESS_KEY = 'arbiter_access_token'
const REFRESH_KEY = 'arbiter_refresh_token'

interface MyOrg {
  org_id: string
  name: string
  slug: string
  plan_tier: string
  role: string
  joined_at: string
  is_current: boolean
}

function CreateOrgModal({ onClose }: { onClose: () => void }): React.ReactElement {
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleCreate(e: React.FormEvent): Promise<void> {
    e.preventDefault()
    if (!name.trim()) {
      setError('Name cannot be empty.')
      return
    }
    setError('')
    setSubmitting(true)
    try {
      // The backend creates the org, adds an owner membership, and switches
      // the active org: the current JWT stays valid, so reload is enough.
      await authClient.post('/org', { name: name.trim() })
      window.location.href = '/'
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Failed to create organization.')
      setSubmitting(false)
    }
  }

  return createPortal(
    // data-org-modal: the sidebar popover's outside-click handler must not
    // treat clicks in this portal as "outside" (it would unmount the modal).
    <div
      data-org-modal
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-surface border border-border-strong rounded-xl p-6 w-full max-w-sm shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-base font-bold text-primary mb-1">New organization</h2>
        <p className="text-secondary text-xs mb-4">
          Starts on the Free plan with its own agents, servers, vault, and quota.
        </p>
        <form onSubmit={(e) => void handleCreate(e)} className="flex flex-col gap-4">
          <div>
            <input
              type="text"
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={255}
              placeholder="Acme Corp"
              className="w-full bg-base border border-border-strong text-primary text-sm px-3.5 py-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent/60 transition-all placeholder:text-muted"
            />
            {name.length > 0 && (
              <p className={`text-right text-xs mt-1 tabular-nums ${name.length >= 240 ? 'text-warning' : 'text-muted'}`}>
                {name.length}/255
              </p>
            )}
          </div>
          {error && (
            <div className="flex items-center gap-2 bg-error/8 border border-error/20 rounded-lg px-3 py-2">
              <span className="w-1.5 h-1.5 rounded-full bg-error flex-shrink-0" />
              <p className="text-error text-xs">{error}</p>
            </div>
          )}
          <div className="flex gap-3">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 border border-border text-secondary hover:text-primary text-sm font-medium py-2.5 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 bg-accent hover:bg-accent-light disabled:opacity-50 text-white font-semibold text-sm py-2.5 rounded-lg transition-all"
            >
              {submitting ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  )
}

function OrgSwitcher(): React.ReactElement | null {
  const { user } = useAuth()
  const [orgs, setOrgs] = useState<MyOrg[] | null>(null)
  const [error, setError] = useState('')
  const [switchingTo, setSwitchingTo] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)

  useEffect(() => {
    let cancelled = false
    authClient
      .get<MyOrg[]>('/me/orgs')
      .then((res) => {
        if (!cancelled) setOrgs(res.data)
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load organizations.")
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (!user) return null

  async function handleSwitch(orgId: string): Promise<void> {
    setError('')
    setSwitchingTo(orgId)
    try {
      const res = await authClient.post<{ access_token: string; refresh_token: string }>(
        '/org/switch',
        { org_id: orgId }
      )
      localStorage.setItem(ACCESS_KEY, res.data.access_token)
      localStorage.setItem(REFRESH_KEY, res.data.refresh_token)
      // Hard reload: every org-scoped view must rehydrate for the new org.
      window.location.href = '/'
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Failed to switch organization.')
      setSwitchingTo(null)
    }
  }

  return (
    <div className="border-t border-border mt-1 pt-2 px-1">
      <p className="px-2 pb-1 text-[10px] font-semibold text-muted uppercase tracking-widest">
        Organizations
      </p>

      {error && <p className="px-2 pb-1 text-error text-xs">{error}</p>}

      {orgs === null && !error && (
        <div className="px-2 py-1.5 space-y-1.5">
          <div className="h-3 skeleton-shimmer rounded w-32" />
          <div className="h-3 skeleton-shimmer rounded w-24" />
        </div>
      )}

      <div className="max-h-44 overflow-y-auto">
        {orgs?.map((org) => (
          <button
            key={org.org_id}
            type="button"
            disabled={org.is_current || switchingTo !== null}
            onClick={() => void handleSwitch(org.org_id)}
            className={`flex items-center gap-2 w-full px-2 py-1.5 rounded-md text-left transition-colors duration-150 ${
              org.is_current
                ? 'bg-accent/[0.07] cursor-default'
                : 'hover:bg-white/[0.04] disabled:opacity-50'
            }`}
          >
            <span className="w-5 h-5 rounded bg-elevated border border-border-strong text-muted font-mono text-[10px] font-semibold flex items-center justify-center flex-shrink-0">
              {org.name[0]?.toUpperCase() ?? '?'}
            </span>
            <span className="flex-1 min-w-0">
              <span className="flex items-center gap-1.5 min-w-0">
                <span className="block text-xs text-primary truncate">
                  {switchingTo === org.org_id ? 'Switching…' : org.name}
                </span>
                <span
                  className={`flex-shrink-0 inline-flex items-center px-1.5 py-0 rounded text-[9px] font-semibold uppercase tracking-wider border ${
                    org.plan_tier === 'pro'
                      ? 'bg-accent/15 text-accent-light border-border-accent'
                      : org.plan_tier === 'enterprise'
                        ? 'bg-purple-500/15 text-purple-300 border-purple-500/30'
                        : 'bg-white/5 text-muted border-border'
                  }`}
                >
                  {org.plan_tier}
                </span>
              </span>
              <span className="block text-[10px] text-muted capitalize">
                {org.role}
              </span>
            </span>
            {org.is_current && (
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                className="text-accent-light flex-shrink-0"
              >
                <polyline points="20 6 9 17 4 12" />
              </svg>
            )}
          </button>
        ))}
      </div>

      <button
        type="button"
        onClick={() => setShowCreate(true)}
        className="flex items-center gap-2 w-full px-2 py-1.5 mt-0.5 rounded-md text-left text-xs text-secondary hover:text-primary hover:bg-white/[0.04] transition-colors duration-150"
      >
        <span className="w-5 h-5 rounded border border-dashed border-border-strong text-muted flex items-center justify-center flex-shrink-0 text-sm leading-none">
          +
        </span>
        New organization
      </button>

      {showCreate && <CreateOrgModal onClose={() => setShowCreate(false)} />}
    </div>
  )
}

export default OrgSwitcher
