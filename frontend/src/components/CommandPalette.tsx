import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { usePalette } from '../context/PaletteContext'
import { useAuth } from '../context/AuthContext'
import type { Agent, Page } from '../api/types'

// ── Static item catalog ───────────────────────────────────────────────────────

interface PaletteItem {
  id:    string
  label: string
  path:  string
  group: 'navigation' | 'actions' | 'agents'
  icon:  React.ReactElement
}

const DashIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
    <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
  </svg>
)
const AgentsIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
  </svg>
)
const ServersIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/>
    <line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/>
  </svg>
)
const SessionsIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
  </svg>
)
const VaultIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="3" y="11" width="18" height="11" rx="1"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
  </svg>
)
const PermissionsIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
  </svg>
)
const SettingsIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
  </svg>
)
const PlusIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
  </svg>
)

const NAV_ITEMS: PaletteItem[] = [
  { id: 'dashboard',   label: 'Dashboard',   path: '/',            group: 'navigation', icon: <DashIcon /> },
  { id: 'agents',      label: 'Agents',      path: '/agents',      group: 'navigation', icon: <AgentsIcon /> },
  { id: 'mcp-servers', label: 'MCP Servers', path: '/mcp-servers', group: 'navigation', icon: <ServersIcon /> },
  { id: 'sessions',    label: 'Sessions',    path: '/sessions',    group: 'navigation', icon: <SessionsIcon /> },
  { id: 'vault',       label: 'Vault',       path: '/vault',       group: 'navigation', icon: <VaultIcon /> },
  { id: 'permissions', label: 'Permissions', path: '/permissions', group: 'navigation', icon: <PermissionsIcon /> },
  { id: 'settings',    label: 'Settings',    path: '/settings',    group: 'navigation', icon: <SettingsIcon /> },
]

const ACTION_ITEMS: PaletteItem[] = [
  { id: 'new-agent',  label: 'Register Agent',  path: '/agents',      group: 'actions', icon: <PlusIcon /> },
  { id: 'new-server', label: 'Add MCP Server',  path: '/mcp-servers', group: 'actions', icon: <PlusIcon /> },
  { id: 'new-secret', label: 'Add Secret',      path: '/vault',       group: 'actions', icon: <PlusIcon /> },
]

// ── Item row component ────────────────────────────────────────────────────────

function PaletteRow({
  item,
  isSelected,
  onActivate,
}: {
  item: PaletteItem
  isSelected: boolean
  onActivate: () => void
}): React.ReactElement {
  return (
    <button
      onMouseDown={(e) => { e.preventDefault(); onActivate() }}
      className={[
        'flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-left transition-colors',
        'duration-[var(--duration-instant)] ease-[var(--ease-out-expo)]',
        isSelected
          ? 'bg-accent/[0.08] text-primary'
          : 'text-secondary hover:bg-white/[0.04] hover:text-primary',
      ].join(' ')}
    >
      <span className="text-muted flex-shrink-0">{item.icon}</span>
      <span className="text-sm truncate">{item.label}</span>
    </button>
  )
}

// ── Group header ──────────────────────────────────────────────────────────────

function GroupLabel({ label }: { label: string }): React.ReactElement {
  return (
    <p className="text-muted text-[10px] uppercase tracking-[0.1em] px-3 py-2 select-none">
      {label}
    </p>
  )
}

// ── Command palette ───────────────────────────────────────────────────────────

export function CommandPalette(): React.ReactElement | null {
  const { isOpen, open, close } = usePalette()
  const { user } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)

  // ⌘K / Ctrl+K global toggle — always active
  useEffect(() => {
    const handleGlobal = (e: KeyboardEvent): void => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        if (isOpen) close(); else open()
      }
    }
    document.addEventListener('keydown', handleGlobal)
    return () => document.removeEventListener('keydown', handleGlobal)
  }, [isOpen, open, close])

  // Agents from React Query cache (no extra fetch)
  const cachedAgents = useMemo<Agent[]>(() => {
    const page = queryClient.getQueryData<Page<Agent>>(['agents'])
    return page?.items ?? []
  }, [queryClient, isOpen]) // recalculate when palette opens

  // Build filtered item list
  const items: PaletteItem[] = useMemo(() => {
    const q = query.toLowerCase()
    const filterFn = (item: PaletteItem) => !q || item.label.toLowerCase().includes(q)

    const navItems = NAV_ITEMS.filter(filterFn)
    // Hide auth-only actions when not logged in
    const actionItems = user ? ACTION_ITEMS.filter(filterFn) : []
    const agentItems: PaletteItem[] = q
      ? cachedAgents
          .filter((a) => a.name.toLowerCase().includes(q))
          .map((a) => ({
            id:    `agent-${a.id}`,
            label: a.name,
            path:  '/agents',
            group: 'agents' as const,
            icon:  <AgentsIcon />,
          }))
      : []

    return [...navItems, ...actionItems, ...agentItems]
  }, [query, user, cachedAgents])

  // Focus + reset on open
  useEffect(() => {
    if (isOpen) {
      setQuery('')
      setSelectedIndex(0)
      // Defer to let the render complete before focusing
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [isOpen])

  // Keyboard navigation inside palette
  const activate = useCallback((item: PaletteItem) => {
    navigate(item.path)
    close()
  }, [navigate, close])

  useEffect(() => {
    if (!isOpen) return
    const handle = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') { close(); return }
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex((i) => Math.min(i + 1, items.length - 1))
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex((i) => Math.max(i - 1, 0))
      }
      if (e.key === 'Enter') {
        const item = items[selectedIndex]
        if (item) activate(item)
      }
    }
    document.addEventListener('keydown', handle)
    return () => document.removeEventListener('keydown', handle)
  }, [isOpen, items, selectedIndex, activate, close])

  // Group the items back for rendering
  const navItems    = items.filter((i) => i.group === 'navigation')
  const actionItems = items.filter((i) => i.group === 'actions')
  const agentItems  = items.filter((i) => i.group === 'agents')

  // Track global indices for selection highlight
  let cursor = 0
  const navStart    = cursor;    cursor += navItems.length
  const actionStart = cursor;    cursor += actionItems.length
  const agentStart  = cursor;

  if (!isOpen) return null

  const isEmpty = items.length === 0

  return (
    <div
      className="fixed inset-0 z-[200]"
      aria-modal="true"
      role="dialog"
      aria-label="Command palette"
    >
      {/* Backdrop */}
      <div
        className="backdrop-enter absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={close}
        aria-hidden="true"
      />

      {/* Panel */}
      <div className="relative z-10 flex items-start justify-center pt-[15vh] px-4">
        <div className="glass-surface border border-border-strong rounded-2xl w-full max-w-xl shadow-2xl palette-open overflow-hidden">

          {/* Search input */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
            <svg className="text-muted flex-shrink-0" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setSelectedIndex(0) }}
              placeholder="Search commands…"
              className="flex-1 bg-transparent text-primary text-sm outline-none placeholder:text-muted"
              aria-label="Command search"
            />
            <kbd className="text-muted text-[10px] font-mono border border-border rounded px-1.5 py-0.5 select-none">ESC</kbd>
          </div>

          {/* Results */}
          <div className="py-1.5 max-h-[360px] overflow-y-auto">
            {isEmpty ? (
              <p className="text-muted text-sm text-center py-8">
                No results for <span className="text-secondary">"{query}"</span>
              </p>
            ) : (
              <>
                {navItems.length > 0 && (
                  <div className="px-1.5">
                    <GroupLabel label="Navigation" />
                    {navItems.map((item, i) => (
                      <PaletteRow
                        key={item.id}
                        item={item}
                        isSelected={selectedIndex === navStart + i}
                        onActivate={() => activate(item)}
                      />
                    ))}
                  </div>
                )}

                {actionItems.length > 0 && (
                  <div className="px-1.5">
                    {navItems.length > 0 && <div className="border-t border-border my-1.5" />}
                    <GroupLabel label="Actions" />
                    {actionItems.map((item, i) => (
                      <PaletteRow
                        key={item.id}
                        item={item}
                        isSelected={selectedIndex === actionStart + i}
                        onActivate={() => activate(item)}
                      />
                    ))}
                  </div>
                )}

                {agentItems.length > 0 && (
                  <div className="px-1.5">
                    <div className="border-t border-border my-1.5" />
                    <GroupLabel label="Agents" />
                    {agentItems.map((item, i) => (
                      <PaletteRow
                        key={item.id}
                        item={item}
                        isSelected={selectedIndex === agentStart + i}
                        onActivate={() => activate(item)}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Footer hint */}
          <div className="border-t border-border px-4 py-2 flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-muted text-[10px] font-mono">
              <kbd className="border border-border rounded px-1 py-0.5">↑↓</kbd> navigate
            </span>
            <span className="flex items-center gap-1.5 text-muted text-[10px] font-mono">
              <kbd className="border border-border rounded px-1 py-0.5">↵</kbd> open
            </span>
            <span className="flex items-center gap-1.5 text-muted text-[10px] font-mono">
              <kbd className="border border-border rounded px-1 py-0.5">ESC</kbd> close
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default CommandPalette
