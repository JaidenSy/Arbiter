import React from 'react'
import { NavLink } from 'react-router-dom'

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
      className={({ isActive }) =>
        `flex items-center justify-center w-full h-10 transition-colors ${
          isActive
            ? 'text-primary bg-highlight'
            : 'text-secondary hover:text-primary hover:bg-elevated'
        }`
      }
    >
      {icon}
    </NavLink>
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
        <NavItem to="/sessions" icon={<SessionsIcon />} title="Sessions" />
      </nav>

      {/* Settings at bottom */}
      <div className="pb-2">
        <NavItem to="/settings" icon={<SettingsIcon />} title="Settings" />
      </div>
    </aside>
  )
}

export default Sidebar
