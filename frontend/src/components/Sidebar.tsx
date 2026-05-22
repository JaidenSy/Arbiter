import React, { useState, useRef, useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { ArbiterMark } from './ArbiterLogo'
import { useTour } from '../hooks/useTour'

const SUPPORT_EMAIL: string = import.meta.env.VITE_SUPPORT_EMAIL ?? 'jaidensy07@gmail.com'

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

const MissionControlIcon = (): React.ReactElement => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="9"/>
    <path d="M12 3v3M12 18v3M3 12h3M18 12h3"/>
    <circle cx="12" cy="12" r="3"/>
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

const UsersIcon = (): React.ReactElement => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
    <circle cx="9" cy="7" r="4"/>
    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
  </svg>
)

const SettingsIcon = (): React.ReactElement => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>
)

// ── Theme toggle ──────────────────────────────────────────────────────────────

function ThemeToggleButton(): React.ReactElement {
  const { theme, toggleTheme } = useTheme()

  return (
    <div className="relative group/nav px-2 py-0.5">
      <button
        type="button"
        onClick={toggleTheme}
        aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        className="w-8 h-8 rounded-lg flex items-center justify-center text-secondary hover:text-primary hover:bg-white/[0.05] transition-all"
      >
        {theme === 'dark' ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="5"/>
            <line x1="12" y1="1" x2="12" y2="3"/>
            <line x1="12" y1="21" x2="12" y2="23"/>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
            <line x1="1" y1="12" x2="3" y2="12"/>
            <line x1="21" y1="12" x2="23" y2="12"/>
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
        )}
      </button>
      {/* Tooltip */}
      <div className="pointer-events-none absolute left-[52px] top-1/2 -translate-y-1/2 ml-1 z-50 opacity-0 group-hover/nav:opacity-100 transition-opacity duration-150">
        <div className="bg-overlay border border-white/[0.12] text-primary text-xs font-medium px-2.5 py-1.5 rounded-md shadow-xl whitespace-nowrap">
          {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          <span className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-overlay" />
        </div>
      </div>
    </div>
  )
}

// ── Nav link helper ───────────────────────────────────────────────────────────

interface NavItemProps {
  to: string
  icon: React.ReactElement
  title: string
  end?: boolean
  id?: string
}

function NavItem({ to, icon, title, end, id }: NavItemProps): React.ReactElement {
  return (
    <div id={id} className="relative group/nav px-2 py-0.5">
      <NavLink
        to={to}
        end={end}
        aria-label={title}
        className={({ isActive }) =>
          `relative flex items-center justify-center w-full h-9 rounded-lg transition-all duration-150 focus:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-accent ${
            isActive
              ? 'text-accent-light bg-accent/10 shadow-[0_0_12px_rgba(124,58,237,0.2)]'
              : 'text-secondary hover:text-primary hover:bg-white/[0.05]'
          }`
        }
      >
        {({ isActive }) => (
          <>
            {isActive && (
              <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-accent-light rounded-full -ml-2 shadow-[0_0_8px_rgba(167,139,250,0.8)]" />
            )}
            {icon}
          </>
        )}
      </NavLink>
      {/* Tooltip */}
      <div className="pointer-events-none absolute left-[52px] top-1/2 -translate-y-1/2 ml-1 z-50 opacity-0 group-hover/nav:opacity-100 transition-opacity duration-150">
        <div className="bg-overlay border border-white/[0.12] text-primary text-xs font-medium px-2.5 py-1.5 rounded-md shadow-xl whitespace-nowrap">
          {title}
          <span className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-overlay" />
        </div>
      </div>
    </div>
  )
}

// ── User avatar + popover ─────────────────────────────────────────────────────

function UserAvatar(): React.ReactElement | null {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

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
    <div ref={ref} className="relative flex items-center justify-center mb-2 px-2">
      <button
        type="button"
        title={user.email}
        onClick={() => setOpen(!open)}
        className="w-8 h-8 rounded-full bg-gradient-to-br from-accent/30 to-teal/20 border border-accent/40 text-accent-light font-mono text-xs font-semibold flex items-center justify-center hover:border-accent/70 hover:shadow-[0_0_12px_rgba(124,58,237,0.25)] transition-all duration-150"
      >
        {initial}
      </button>

      {open && (
        <div className="animate-fade-in absolute left-[52px] bottom-0 ml-2 w-60 bg-overlay border border-white/[0.12] rounded-xl shadow-2xl z-50 py-2 overflow-hidden backdrop-blur-sm">
          {/* Subtle top gradient accent */}
          <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent" />
          <div className="px-3 pb-2.5 border-b border-white/[0.07]">
            <p className="text-primary text-sm font-medium truncate">{user.email}</p>
            <p className="text-secondary text-xs mt-0.5 capitalize">{user.role}</p>
            <p className="text-muted text-xs mt-0.5 truncate font-mono">{user.org_name}</p>
          </div>
          <div className="px-3 pt-2 pb-1">
            <span className="inline-flex items-center gap-1 text-accent-light bg-accent/10 border border-accent/25 rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider">
              {planLabel}
            </span>
          </div>
          <div className="border-t border-white/[0.07] mt-1 pt-1">
            <a
              href="/account"
              onClick={() => setOpen(false)}
              className="flex items-center w-full px-3 py-1.5 text-xs text-secondary hover:text-primary hover:bg-white/[0.05] transition-colors"
            >
              My Account
            </a>
            <a
              href={`mailto:${SUPPORT_EMAIL}?subject=Arbiter Support`}
              className="flex items-center w-full px-3 py-1.5 text-xs text-secondary hover:text-primary hover:bg-white/[0.05] transition-colors rounded-md mx-0"
            >
              Contact Support
            </a>
            <button
              type="button"
              onClick={handleLogout}
              className="w-full text-left px-3 py-1.5 text-xs text-secondary hover:text-error hover:bg-error/5 transition-colors"
            >
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Help button ───────────────────────────────────────────────────────────────

function HelpButton({ onStart }: { onStart: () => void }): React.ReactElement {
  return (
    <div id="help-button" className="relative group/nav px-2 py-0.5">
      <button
        type="button"
        aria-label="Product walkthrough"
        onClick={onStart}
        className="w-8 h-8 rounded-lg flex items-center justify-center text-secondary hover:text-primary hover:bg-white/[0.05] transition-all"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
          <line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
      </button>
      <div className="pointer-events-none absolute left-[52px] top-1/2 -translate-y-1/2 ml-1 z-50 opacity-0 group-hover/nav:opacity-100 transition-opacity duration-150">
        <div className="bg-overlay border border-white/[0.12] text-primary text-xs font-medium px-2.5 py-1.5 rounded-md shadow-xl whitespace-nowrap">
          Help / Walkthrough
          <span className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-overlay" />
        </div>
      </div>
    </div>
  )
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

function Sidebar(): React.ReactElement {
  const { startTour } = useTour()
  return (
    <aside className="fixed left-0 top-0 h-screen w-[52px] bg-gradient-to-b from-surface to-base border-r border-white/[0.06] flex flex-col z-40">
      {/* Subtle vertical accent line at top */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-accent/30 to-transparent" />

      {/* Logo */}
      <NavLink
        to="/"
        className="flex items-center justify-center h-[52px] select-none"
        aria-label="Arbiter home"
      >
        <ArbiterMark size={32} />
      </NavLink>

      {/* Top divider */}
      <div className="mx-3 border-t border-white/[0.06]" />

      {/* Main nav */}
      <nav className="flex flex-col flex-1 pt-2 gap-0.5">
        <NavItem id="nav-dashboard" to="/" icon={<DashboardIcon />} title="Dashboard" end />
        <NavItem id="nav-agents" to="/agents" icon={<AgentsIcon />} title="Agents" />
        <NavItem id="nav-mcp-servers" to="/mcp-servers" icon={<MCPServersIcon />} title="MCP Servers" />
        <NavItem id="nav-vault" to="/vault" icon={<VaultIcon />} title="Vault" />
        <NavItem id="nav-sessions" to="/sessions" icon={<SessionsIcon />} title="Sessions" />
        <NavItem id="nav-mission-control" to="/mission-control" icon={<MissionControlIcon />} title="Mission Control" />
        <NavItem id="nav-permissions" to="/permissions" icon={<PermissionsIcon />} title="Permissions" />
        <NavItem id="nav-organization" to="/organization" icon={<UsersIcon />} title="Organization" />
      </nav>

      {/* Bottom divider */}
      <div className="mx-3 border-t border-white/[0.06]" />

      {/* Settings + user at bottom */}
      <div className="pb-2 flex flex-col items-center gap-0.5 pt-2">
        <NavItem id="nav-settings" to="/settings" icon={<SettingsIcon />} title="Settings" />
        <HelpButton onStart={startTour} />
        <ThemeToggleButton />
        <UserAvatar />
      </div>
    </aside>
  )
}

export default Sidebar
