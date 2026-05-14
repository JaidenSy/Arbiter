import React, { useState, useRef, useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

// ── Icons ─────────────────────────────────────────────────────────────────────

const DashboardIcon = (): React.ReactElement => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="3" y="3" width="7" height="7"/>
    <rect x="14" y="3" width="7" height="7"/>
    <rect x="3" y="14" width="7" height="7"/>
    <rect x="14" y="14" width="7" height="7"/>
  </svg>
)

const AgentsIcon = (): React.ReactElement => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="9" cy="7" r="4"/>
    <path d="M2 21v-2a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v2"/>
    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
    <path d="M22 21v-2a4 4 0 0 0-3-3.87"/>
  </svg>
)

const SessionsIcon = (): React.ReactElement => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>
  </svg>
)

const MCPServersIcon = (): React.ReactElement => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="2" y="3" width="20" height="5" rx="1"/>
    <rect x="2" y="10" width="20" height="5" rx="1"/>
    <rect x="2" y="17" width="20" height="5" rx="1"/>
    <circle cx="18" cy="5.5" r="0.75" fill="currentColor"/>
    <circle cx="18" cy="12.5" r="0.75" fill="currentColor"/>
    <circle cx="18" cy="19.5" r="0.75" fill="currentColor"/>
  </svg>
)

const PermissionsIcon = (): React.ReactElement => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="3" y="11" width="18" height="11" rx="1"/>
    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
  </svg>
)

const VaultIcon = (): React.ReactElement => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="2" y="3" width="20" height="18" rx="1"/>
    <circle cx="12" cy="12" r="4"/>
    <path d="M12 8v1M12 15v1M8 12h1M15 12h1"/>
    <path d="M18 3v18"/>
  </svg>
)

const SettingsIcon = (): React.ReactElement => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="12" cy="12" r="3"/>
    <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
  </svg>
)

// ── Nav link helper ───────────────────────────────────────────────────────────

interface NavItemProps {
  to: string
  icon: React.ReactElement
  title: string
  end?: boolean
}

function NavItem({ to, icon, title, end }: NavItemProps): React.ReactElement {
  return (
    <NavLink
      to={to}
      end={end}
      title={title}
      aria-label={title}
      className={({ isActive }) =>
        `flex items-center justify-center w-full h-10 transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-accent ${
          isActive
            ? 'text-primary bg-highlight border-r-2 border-accent'
            : 'text-secondary hover:text-primary hover:bg-elevated border-r-2 border-transparent'
        }`
      }
    >
      {icon}
    </NavLink>
  )
}

// ── User avatar + popover ─────────────────────────────────────────────────────

function UserAvatar(): React.ReactElement | null {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    if (!open) return
    function handler(e: MouseEvent): void {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  if (!user) return null

  const initial = user.email[0]?.toUpperCase() ?? '?'
  const planLabel = (user.org_plan ?? 'free').charAt(0).toUpperCase() + (user.org_plan ?? 'free').slice(1)

  const handleLogout = (): void => {
    setOpen(false)
    void logout().then(() => {
      window.location.href = '/login'
    })
  }

  return (
    <div ref={ref} className="relative flex items-center justify-center mb-2">
      <button
        type="button"
        title={user.email}
        onClick={() => setOpen(!open)}
        className="w-8 h-8 rounded-full bg-accent/20 border border-accent/40 text-accent-light font-mono text-xs font-semibold flex items-center justify-center hover:bg-accent/30 transition-colors"
      >
        {initial}
      </button>

      {open && (
        <div className="absolute left-[52px] bottom-0 ml-1 w-56 bg-surface border border-white/[0.1] rounded shadow-xl z-50 py-2 font-mono text-xs">
          <div className="px-3 pb-2 border-b border-white/[0.07]">
            <p className="text-primary truncate">{user.email}</p>
            <p className="text-secondary mt-0.5 capitalize">{user.role}</p>
            <p className="text-muted mt-0.5 truncate">{user.org_name}</p>
          </div>
          <div className="px-3 pt-2 pb-1">
            <span className="inline-block text-accent-light border border-accent/30 rounded px-1.5 py-0.5 text-[10px]">
              {planLabel}
            </span>
          </div>
          <div className="border-t border-white/[0.07] mt-1 pt-1">
            <button
              type="button"
              onClick={handleLogout}
              className="w-full text-left px-3 py-1.5 text-secondary hover:text-red-400 hover:bg-elevated transition-colors"
            >
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

function Sidebar(): React.ReactElement {
  return (
    <aside className="fixed left-0 top-0 h-screen w-[52px] bg-surface border-r border-white/[0.07] flex flex-col z-40">
      {/* Logo */}
      <div className="bg-gradient-to-b from-violet-950/20 to-transparent">
        <NavLink
          to="/"
          className="flex items-center justify-center h-[52px] font-mono font-bold text-accent text-lg"
        >
          NX
        </NavLink>
      </div>

      {/* Main nav */}
      <nav className="flex flex-col flex-1 pt-2">
        <NavItem to="/" icon={<DashboardIcon />} title="Dashboard" end />
        <NavItem to="/agents" icon={<AgentsIcon />} title="Agents" />
        <NavItem to="/mcp-servers" icon={<MCPServersIcon />} title="MCP Servers" />
        <NavItem to="/vault" icon={<VaultIcon />} title="Vault" />
        <NavItem to="/sessions" icon={<SessionsIcon />} title="Sessions" />
        <NavItem to="/permissions" icon={<PermissionsIcon />} title="Permissions" />
      </nav>

      {/* Settings + user at bottom */}
      <div className="pb-2 flex flex-col items-center">
        <NavItem to="/settings" icon={<SettingsIcon />} title="Settings" />
        <UserAvatar />
      </div>
    </aside>
  )
}

export default Sidebar
