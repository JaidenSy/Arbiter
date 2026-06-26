import React, { useEffect, useRef, useState } from 'react'

/**
 * Above-the-fold product tour (Railway-style), action-driven.
 *
 * Not screenshots: the real Arbiter dashboard pages are rebuilt in DOM at a fixed
 * design width and scaled to fit. A scripted cursor *performs* the setup — register
 * an agent, connect an MCP server, store a secret, grant a permission — then runs a
 * live call that is allowed, and one that per-agent RBAC denies, updating the graph
 * and audit log in place.
 *
 * Bottom tabs mark the chapters, highlight as it plays, and are clickable to jump.
 * Hover pauses. Respects prefers-reduced-motion.
 *
 * ponytail: cursor coordinates are design-px; nudge them if the markup spacing changes.
 */

const DESIGN_W = 1200
const DESIGN_H = 660

// ── Tiny primitives ─────────────────────────────────────────────────────────────

function Typewriter({ text, className }: { text: string; className?: string }): React.ReactElement {
  const [n, setN] = useState(0)
  useEffect(() => {
    setN(0)
    const id = setInterval(() => setN((v) => (v >= text.length ? v : v + 1)), 55)
    return () => clearInterval(id)
  }, [text])
  return (
    <span className={className}>
      {text.slice(0, n)}
      <span className="text-accent-light animate-pulse">▌</span>
    </span>
  )
}

function Cursor({ x, y, clicking }: { x: number; y: number; clicking: boolean }): React.ReactElement {
  return (
    <div
      className="absolute top-0 left-0 z-30 pointer-events-none"
      style={{
        transform: `translate(${x}px, ${y}px)`,
        transformOrigin: 'top left',
        transition: 'transform 700ms cubic-bezier(0.22,1,0.36,1)',
      }}
    >
      {clicking && <span className="absolute -left-1.5 -top-1.5 w-8 h-8 rounded-full bg-accent-light/30 animate-ping" />}
      <svg width="24" height="24" viewBox="0 0 24 24" className="drop-shadow-[0_2px_5px_rgba(0,0,0,0.7)]">
        <path d="M5 3l14 7.5-6 1.5-2.5 6L5 3z" fill="#fff" stroke="#0b0b12" strokeWidth="1.2" strokeLinejoin="round" />
      </svg>
    </div>
  )
}

function Modal({ title, children }: { title: string; children: React.ReactNode }): React.ReactElement {
  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center animate-fade-in">
      <div className="absolute inset-0 bg-black/55" />
      <div className="relative w-[440px] bg-surface border border-border rounded-xl p-6" style={{ boxShadow: '0 24px 60px rgba(0,0,0,0.6)' }}>
        <p className="text-primary font-semibold text-base mb-5">{title}</p>
        {children}
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }): React.ReactElement {
  return (
    <div className="mb-4">
      <span className="block text-xs font-mono uppercase tracking-wider text-muted mb-1.5">{label}</span>
      <div className="bg-elevated border border-border-accent rounded-lg px-3 py-2 text-sm font-mono text-primary min-h-[38px]">{children}</div>
    </div>
  )
}

function PrimaryBtn({ label }: { label: string }): React.ReactElement {
  return <div className="bg-accent text-white text-sm font-semibold px-4 py-2 rounded-lg inline-block">{label}</div>
}

function Th({ children }: { children: React.ReactNode }): React.ReactElement {
  return <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">{children}</th>
}

function StatusBadge({ active }: { active: boolean }): React.ReactElement {
  return (
    <span className={`inline-flex items-center gap-1.5 font-mono text-[10px] px-1.5 py-0.5 rounded border ${active ? 'bg-success/10 text-success border-success/20' : 'bg-elevated text-muted border-border'}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${active ? 'bg-success' : 'bg-muted'}`} />
      {active ? 'active' : 'idle'}
    </span>
  )
}

function PageHeader({ title, subtitle, action }: { title: string; subtitle: string; action?: string }): React.ReactElement {
  return (
    <div className="flex items-start justify-between mb-8">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight text-primary">{title}</h1>
        <p className="text-secondary text-sm mt-1">{subtitle}</p>
      </div>
      {action && <PrimaryBtn label={action} />}
    </div>
  )
}

function EmptyState({ title, body }: { title: string; body: string }): React.ReactElement {
  return (
    <div className="py-16 text-center">
      <div className="w-11 h-11 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-3">
        <span className="w-4 h-4 rounded bg-accent-light/40" />
      </div>
      <p className="text-primary text-sm font-medium mb-1">{title}</p>
      <p className="text-secondary text-xs max-w-xs mx-auto">{body}</p>
    </div>
  )
}

// ── Sidebar ─────────────────────────────────────────────────────────────────────

const SIDEBAR_ICONS = [
  'M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z',
  'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
  'M4 4h16v6H4zM4 14h16v6H4zM8 7h.01M8 17h.01',
  'M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2zM7 11V7a5 5 0 0 1 10 0v4',
  'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01',
  'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
]

function SidebarRail({ active }: { active: number }): React.ReactElement {
  return (
    <div className="w-[52px] shrink-0 h-full border-r border-border bg-surface/60 flex flex-col items-center py-3">
      <div className="w-7 h-7 rounded-lg bg-accent/15 border border-accent/25 flex items-center justify-center mb-4">
        <span className="text-accent-light font-display font-bold text-sm">A</span>
      </div>
      <div className="flex flex-col gap-0.5 w-full px-1.5">
        {SIDEBAR_ICONS.map((p, idx) => (
          <div key={idx} className="relative h-9 flex items-center justify-center">
            {idx === active && <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-accent-light" />}
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className={idx === active ? 'text-primary' : 'text-muted'}>
              <path d={p} />
            </svg>
          </div>
        ))}
      </div>
      <div className="mt-auto w-7 h-7 rounded-full bg-elevated border border-border flex items-center justify-center text-muted text-[11px] font-mono">D</div>
    </div>
  )
}

function AgentListPanel({ selected }: { selected: number }): React.ReactElement {
  const items = ['claude-code-demo', 'agt-prod-001', 'agt-dev-042']
  return (
    <div className="w-[210px] shrink-0">
      <p className="text-muted text-xs uppercase tracking-widest mb-3">Agents</p>
      <div className="border border-border rounded-xl overflow-hidden">
        {items.map((name, idx) => (
          <div key={name} className={`px-4 py-3 border-b border-border last:border-0 flex items-center gap-2 ${idx === selected ? 'bg-accent/10' : ''}`}>
            <span className="w-1.5 h-1.5 rounded-full bg-success" />
            <span className={`text-sm font-mono ${idx === selected ? 'text-primary' : 'text-secondary'}`}>{name}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Chapter pages (driven by `phase`) ───────────────────────────────────────────

type Phase = string

function AgentsPage({ phase }: { phase: Phase }): React.ReactElement {
  const added = phase === 'added'
  return (
    <div className="p-8">
      <PageHeader title="Agents" subtitle="Registered agent identities and their API keys" action="Register Agent" />
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <table className="min-w-full">
          <thead><tr className="border-b border-border"><Th>Name</Th><Th>Description</Th><Th>Status</Th><Th>Scope</Th><Th>Rate limit</Th></tr></thead>
          <tbody>
            {added ? (
              <tr className="border-b border-border animate-fade-in">
                <td className="py-3 px-4 text-sm font-mono text-accent-light">claude-code-demo</td>
                <td className="py-3 px-4 text-sm text-secondary">Local Claude Code agent</td>
                <td className="py-3 px-4"><StatusBadge active /></td>
                <td className="py-3 px-4 text-sm text-secondary">Scoped</td>
                <td className="py-3 px-4 text-sm font-mono text-secondary tabular-nums">60/min</td>
              </tr>
            ) : (
              <tr><td colSpan={5}><EmptyState title="No agents registered yet" body="Register your first agent to start routing tool calls through Arbiter." /></td></tr>
            )}
          </tbody>
        </table>
      </div>
      {phase === 'modal' && (
        <Modal title="Register Agent">
          <Field label="Name"><Typewriter text="claude-code-demo" /></Field>
          <div className="mb-5">
            <span className="block text-xs font-mono uppercase tracking-wider text-muted mb-1.5">Scope</span>
            <div className="flex gap-2">
              <div className="flex-1 border border-border-accent bg-accent/10 text-accent-light rounded-lg px-3 py-2 text-sm font-medium">Scoped</div>
              <div className="flex-1 border border-border text-muted rounded-lg px-3 py-2 text-sm">Full</div>
            </div>
          </div>
          <div className="flex justify-end"><PrimaryBtn label="Create agent" /></div>
        </Modal>
      )}
    </div>
  )
}

function ServersPage({ phase }: { phase: Phase }): React.ReactElement {
  const added = phase === 'added'
  return (
    <div className="p-8">
      <PageHeader title="MCP Servers" subtitle="Connected tool servers proxied through Arbiter" action="Add Server" />
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <table className="min-w-full">
          <thead><tr className="border-b border-border"><Th>Name</Th><Th>Base URL</Th><Th>Cache</Th><Th>Status</Th></tr></thead>
          <tbody>
            {added ? (
              <tr className="border-b border-border animate-fade-in">
                <td className="py-3 px-4 text-sm font-mono text-accent-light">deepwiki</td>
                <td className="py-3 px-4 text-sm font-mono text-secondary">mcp.deepwiki.com</td>
                <td className="py-3 px-4"><span className="font-mono text-[10px] px-1.5 py-0.5 rounded border bg-success/10 text-success border-success/20">semantic</span></td>
                <td className="py-3 px-4"><StatusBadge active /></td>
              </tr>
            ) : (
              <tr><td colSpan={4}><EmptyState title="No MCP servers registered" body="Add a server to start routing tool calls through Arbiter." /></td></tr>
            )}
          </tbody>
        </table>
      </div>
      {phase === 'modal' && (
        <Modal title="Add MCP Server">
          <Field label="Name"><Typewriter text="deepwiki" /></Field>
          <Field label="Base URL"><span className="text-secondary">https://mcp.deepwiki.com</span></Field>
          <div className="flex justify-end"><PrimaryBtn label="Add server" /></div>
        </Modal>
      )}
    </div>
  )
}

function VaultPage({ phase }: { phase: Phase }): React.ReactElement {
  const added = phase === 'added'
  return (
    <div className="p-8">
      <PageHeader title="Vault" subtitle="AES-256-GCM encrypted secrets per agent" action="Add Secret" />
      <div className="flex gap-6">
        <AgentListPanel selected={0} />
        <div className="flex-1 min-w-0">
          <p className="text-primary text-sm mb-3">Vault — <span className="font-mono text-accent-light">claude-code-demo</span></p>
          <div className="bg-surface border border-border rounded-xl overflow-hidden">
            <table className="min-w-full">
              <thead><tr className="border-b border-border"><Th>Name</Th><Th>Stored</Th><Th>Value</Th><Th>Encryption</Th></tr></thead>
              <tbody>
                {added ? (
                  <tr className="border-b border-border animate-fade-in">
                    <td className="py-3 px-4 text-sm font-mono text-accent-light">DATABASE_URL</td>
                    <td className="py-3 px-4 text-sm text-secondary">just now</td>
                    <td className="py-3 px-4 text-sm font-mono text-muted tracking-widest">••••••••••</td>
                    <td className="py-3 px-4"><span className="font-mono text-[10px] px-1.5 py-0.5 rounded border bg-success/10 text-success border-success/20">AES-256-GCM</span></td>
                  </tr>
                ) : (
                  <tr><td colSpan={4}><EmptyState title="No secrets stored" body="Add a secret to inject into tool calls using {{SECRET_NAME}}." /></td></tr>
                )}
              </tbody>
            </table>
          </div>
          <p className="text-muted text-xs mt-3">Injected into tool calls as <span className="font-mono text-accent-light">{'{{SECRET_NAME}}'}</span> — never returned to the agent.</p>
        </div>
      </div>
      {phase === 'modal' && (
        <Modal title="Add Secret — claude-code-demo">
          <Field label="Name"><Typewriter text="DATABASE_URL" /></Field>
          <Field label="Value"><span className="text-muted tracking-widest">••••••••••••••••</span></Field>
          <div className="flex justify-end"><PrimaryBtn label="Store secret" /></div>
        </Modal>
      )}
    </div>
  )
}

function AccessPage({ phase }: { phase: Phase }): React.ReactElement {
  const granted = phase === 'granted'
  return (
    <div className="p-8">
      <PageHeader title="Tool Permissions" subtitle="Control which tools each agent is allowed to invoke" />
      <div className="flex gap-6">
        <AgentListPanel selected={0} />
        <div className="flex-1 min-w-0 border border-border rounded-xl p-5 bg-surface">
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm font-mono text-accent-light">deepwiki</p>
            <span className="text-muted text-xs">{granted ? '1 tool granted' : 'select tools to grant'}</span>
          </div>
          <div className="space-y-1">
            <div className={`flex items-center gap-3 px-3 py-2.5 rounded-lg ${granted ? 'bg-success/8' : ''}`}>
              <span className={`w-4 h-4 rounded border flex items-center justify-center ${granted ? 'bg-success border-success' : 'border-border-accent'}`}>
                {granted && <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#0b0b12" strokeWidth="3.5"><path d="M5 13l4 4L19 7" /></svg>}
              </span>
              <span className={`font-mono text-xs ${granted ? 'text-success' : 'text-primary'}`}>ask_question</span>
              {granted && <span className="font-mono text-[10px] px-1.5 py-0.5 rounded border bg-success/10 text-success border-success/20 ml-auto">ALLOW</span>}
            </div>
            <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg">
              <span className="w-4 h-4 rounded border border-border-accent" />
              <span className="font-mono text-xs text-secondary">read_wiki_structure</span>
            </div>
            <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg">
              <span className="w-4 h-4 rounded border border-border" />
              <span className="font-mono text-xs text-muted">read_wiki_contents</span>
              <span className="font-mono text-[10px] px-1.5 py-0.5 rounded border bg-error/10 text-error border-error/20 ml-auto">DENY</span>
            </div>
          </div>
          <div className="flex justify-end mt-4"><PrimaryBtn label="Save permissions" /></div>
        </div>
      </div>
    </div>
  )
}

// ── Live call chapter ───────────────────────────────────────────────────────────

function GraphNode({ label, sub, tone }: { label: string; sub: string; tone: 'base' | 'accent' | 'green' | 'red' }): React.ReactElement {
  const ring = tone === 'accent' ? 'border-accent/40 bg-accent/10' : tone === 'green' ? 'border-success/40 bg-success/10' : tone === 'red' ? 'border-error/40 bg-error/10' : 'border-border bg-surface'
  const txt = tone === 'green' ? 'text-success' : tone === 'red' ? 'text-error' : tone === 'accent' ? 'text-accent-light' : 'text-primary'
  return (
    <div className={`rounded-xl border px-5 py-4 text-center min-w-[150px] transition-colors duration-300 ${ring}`}>
      <p className={`font-mono text-sm font-semibold ${txt}`}>{label}</p>
      <p className="text-muted text-[11px] mt-1">{sub}</p>
    </div>
  )
}

function Link({ tone }: { tone: 'idle' | 'green' | 'red' }): React.ReactElement {
  const color = tone === 'green' ? 'bg-success' : tone === 'red' ? 'bg-error' : 'bg-border'
  return (
    <div className="flex-1 relative h-px mx-2 self-center">
      <div className={`absolute inset-0 ${color} transition-colors duration-300`} />
      {tone === 'red' && <span className="absolute left-1/2 -translate-x-1/2 -top-2.5 text-error text-sm">✕</span>}
    </div>
  )
}

function LivePage({ phase }: { phase: Phase }): React.ReactElement {
  const denied = phase === 'denied'
  return (
    <div className="p-8">
      <PageHeader title="Live" subtitle="A client calling tools through the Arbiter gateway" />

      {/* Architecture graph */}
      <div className="bg-surface border border-border rounded-xl p-6 mb-6">
        <div className="flex items-stretch">
          <GraphNode label="Claude Code" sub={denied ? 'read_wiki_contents' : 'ask_question'} tone="base" />
          <Link tone="green" />
          <GraphNode label="Arbiter" sub={denied ? 'RBAC · blocked' : 'RBAC · cache · audit'} tone={denied ? 'red' : 'accent'} />
          <Link tone={denied ? 'red' : 'green'} />
          <GraphNode label="deepwiki" sub="MCP server" tone={denied ? 'base' : 'green'} />
        </div>
      </div>

      {/* Audit log */}
      <p className="text-secondary text-xs uppercase tracking-widest mb-3">Audit log</p>
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <table className="min-w-full">
          <tbody>
            <tr className="border-b border-border animate-fade-in">
              <td className="py-2.5 px-4 text-sm font-mono text-accent-light">ask_question</td>
              <td className="py-2.5 px-4 text-sm text-muted">deepwiki</td>
              <td className="py-2.5 px-4"><span className="font-mono text-[10px] px-1.5 py-0.5 rounded border bg-success/10 text-success border-success/20">ALLOWED</span></td>
              <td className="py-2.5 px-4 text-sm font-mono text-muted text-right">10610ms</td>
            </tr>
            {denied && (
              <tr className="bg-error/8 animate-fade-in">
                <td className="py-2.5 px-4 text-sm font-mono text-error">read_wiki_contents</td>
                <td className="py-2.5 px-4 text-sm text-muted">deepwiki</td>
                <td className="py-2.5 px-4"><span className="font-mono text-[10px] px-1.5 py-0.5 rounded border bg-error/10 text-error border-error/20">DENIED</span></td>
                <td className="py-2.5 px-4 text-sm font-mono text-muted text-right">4ms</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {denied && <p className="text-error text-xs font-mono mt-3">Error: agent &lsquo;claude-code-demo&rsquo; is not permitted to call &lsquo;read_wiki_contents&rsquo; on &lsquo;deepwiki&rsquo;.</p>}
    </div>
  )
}

// ── Tabs ────────────────────────────────────────────────────────────────────────

const TABS = [
  { label: 'Agents', sidebar: 1, icon: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z' },
  { label: 'Servers', sidebar: 2, icon: 'M4 4h16v6H4zM4 14h16v6H4zM8 7h.01M8 17h.01' },
  { label: 'Vault', sidebar: 3, icon: 'M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2zM7 11V7a5 5 0 0 1 10 0v4' },
  { label: 'Access', sidebar: 5, icon: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' },
  { label: 'Live', sidebar: 4, icon: 'M22 12h-4l-3 9L9 3l-3 9H2' },
]

function BottomTabs({ active, onSelect }: { active: number; onSelect: (c: number) => void }): React.ReactElement {
  return (
    <div className="absolute left-1/2 -translate-x-1/2 z-10" style={{ bottom: 20 }}>
      <div className="flex items-center bg-surface/95 backdrop-blur border border-border rounded-xl px-1.5 py-1.5" style={{ boxShadow: '0 12px 30px rgba(0,0,0,0.5)' }}>
        {TABS.map((t, idx) => (
          <React.Fragment key={t.label}>
            {idx > 0 && <span className="w-px h-5 bg-border mx-0.5" />}
            <button type="button" onClick={() => onSelect(idx)} aria-label={t.label}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${idx === active ? 'bg-accent/15 text-accent-light' : 'text-muted hover:text-secondary'}`}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={t.icon} /></svg>
              {t.label}
            </button>
          </React.Fragment>
        ))}
      </div>
    </div>
  )
}

// ── Scripted walkthrough ────────────────────────────────────────────────────────

interface Step {
  tab: number
  phase: Phase
  caption: string
  cursor?: { x: number; y: number; click?: boolean }
  hold: number
}

const STEPS: Step[] = [
  // 1 — Register an agent
  { tab: 0, phase: 'empty', caption: 'Register an agent — it gets its own cryptographic identity and key.', cursor: { x: 1040, y: 78 }, hold: 1700 },
  { tab: 0, phase: 'modal', caption: 'Name it and choose a scope.', cursor: { x: 470, y: 250 }, hold: 2200 },
  { tab: 0, phase: 'modal', caption: 'Create the agent.', cursor: { x: 720, y: 405, click: true }, hold: 800 },
  { tab: 0, phase: 'added', caption: 'claude-code-demo is live — active, scoped, rate-limited.', cursor: { x: 300, y: 205 }, hold: 2000 },

  // 2 — Connect an MCP server
  { tab: 1, phase: 'empty', caption: 'Connect an MCP server to proxy its tools through Arbiter.', cursor: { x: 1055, y: 78 }, hold: 1700 },
  { tab: 1, phase: 'modal', caption: 'Point Arbiter at the upstream server.', cursor: { x: 720, y: 425, click: true }, hold: 1900 },
  { tab: 1, phase: 'added', caption: 'deepwiki is connected, with semantic caching on.', cursor: { x: 300, y: 205 }, hold: 1900 },

  // 3 — Store a secret
  { tab: 2, phase: 'empty', caption: 'Store secrets in the per-agent vault.', cursor: { x: 1050, y: 78 }, hold: 1700 },
  { tab: 2, phase: 'modal', caption: 'Secrets are encrypted with AES-256-GCM.', cursor: { x: 720, y: 430, click: true }, hold: 1900 },
  { tab: 2, phase: 'added', caption: 'Injected at the gateway as {{NAME}} — never returned to the agent.', cursor: { x: 480, y: 250 }, hold: 2000 },

  // 4 — Grant a permission
  { tab: 3, phase: 'select', caption: 'Choose exactly which tools the agent may call.', cursor: { x: 600, y: 250, click: true }, hold: 1900 },
  { tab: 3, phase: 'granted', caption: 'ask_question is allowed — read_wiki_contents stays denied.', cursor: { x: 720, y: 360, click: true }, hold: 2200 },

  // 5 — Live calls: allowed vs denied
  { tab: 4, phase: 'allowed', caption: 'The client calls ask_question — allowed, served, and logged.', hold: 2200 },
  { tab: 4, phase: 'denied', caption: 'It tries read_wiki_contents — blocked at call time by RBAC.', hold: 3600 },
]

const chapterStart = (tab: number): number => STEPS.findIndex((s) => s.tab === tab)

// ── Component ───────────────────────────────────────────────────────────────────

export default function HeroDashboardSim(): React.ReactElement {
  const prefersReduced =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  const frameRef = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(0.64)
  const [idx, setIdx] = useState(prefersReduced ? STEPS.length - 1 : 0)
  const [hovered, setHovered] = useState(false)

  useEffect(() => {
    const el = frameRef.current
    if (!el) return
    const update = () => setScale(el.clientWidth / DESIGN_W)
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    if (prefersReduced || hovered) return
    const t = setTimeout(() => setIdx((i) => (i + 1) % STEPS.length), STEPS[idx].hold)
    return () => clearTimeout(t)
  }, [idx, hovered, prefersReduced])

  const step = STEPS[idx]

  const renderPage = (): React.ReactElement => {
    switch (step.tab) {
      case 0: return <AgentsPage phase={step.phase} />
      case 1: return <ServersPage phase={step.phase} />
      case 2: return <VaultPage phase={step.phase} />
      case 3: return <AccessPage phase={step.phase} />
      default: return <LivePage phase={step.phase} />
    }
  }

  return (
    <div onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
      <div
        ref={frameRef}
        className="relative rounded-lg overflow-hidden bg-base"
        style={{
          border: '1px solid rgba(255,255,255,0.09)',
          boxShadow: '0 0 0 1px rgba(61,53,206,0.12) inset, 0 24px 60px rgba(0,0,0,0.45)',
          aspectRatio: `${DESIGN_W} / ${DESIGN_H}`,
        }}
      >
        <div className="absolute top-0 left-0" style={{ width: DESIGN_W, height: DESIGN_H, transform: `scale(${scale})`, transformOrigin: 'top left' }}>
          {/* Content + cursor */}
          <div className="absolute inset-0 flex">
            <SidebarRail active={TABS[step.tab].sidebar} />
            <div className="flex-1 min-w-0 relative">{renderPage()}</div>
            {step.cursor && !prefersReduced && (
              <Cursor x={step.cursor.x} y={step.cursor.y} clicking={!!step.cursor.click} />
            )}
          </div>

          {/* Fixed bottom tabs */}
          <BottomTabs active={step.tab} onSelect={(c) => setIdx(chapterStart(c))} />
        </div>
      </div>

      <p className="mt-3 text-muted text-xs leading-relaxed min-h-[2rem]" aria-live="polite">
        <span className="text-secondary font-medium">{TABS[step.tab].label}.</span> {step.caption}{' '}
        <span className="text-muted/70">Hover to explore.</span>
      </p>
    </div>
  )
}
