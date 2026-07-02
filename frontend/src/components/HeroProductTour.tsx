import React, { useEffect, useLayoutEffect, useRef, useState } from 'react'

/**
 * HeroProductTour: Railway-style interactive product tour.
 *
 * All five product surfaces (Agents, Servers, Vault, Access, Live) live as
 * windows on one large board. A camera glides across the board, zooming and
 * panning to frame each chapter of the story: register an agent, connect an
 * MCP server, store a secret, grant a permission, then watch a live call get
 * allowed and a second one get denied by per-agent RBAC.
 *
 * The camera is a requestAnimationFrame loop that interpolates a
 * {centerX, centerY, scale} camera toward a target rect on the board:
 *   - pan is eased with easeInOutCubic (no bounce, ease family per DESIGN.md)
 *   - zoom interpolates logarithmically (perceptually linear)
 *   - long moves dip the zoom mid-flight, pulling back to show the whole
 *     board before pushing in on the destination (the Railway glide)
 * The transform is applied directly to the stage layer, so React never
 * re-renders during a camera move.
 *
 * Bottom tabs mark the chapters, highlight as it plays, and are clickable to
 * jump. Hover pauses playback. Respects prefers-reduced-motion by rendering
 * the finished board with no camera motion and instant jumps.
 *
 * ponytail: cursor coordinates and camera sub-rects are board-px estimates;
 * nudge them if the panel markup spacing changes.
 */

// ── Board geometry ──────────────────────────────────────────────────────────────

const BOARD_W = 2560
const BOARD_H = 1440
const VIEW_W = 1200
const VIEW_H = 660

interface Rect { x: number; y: number; w: number; h: number }

const PANEL_W = 720
const PANEL_H = 460

// Clockwise around the board, finale in the center.
const PANEL_RECTS: Rect[] = [
  { x: 140, y: 110, w: PANEL_W, h: PANEL_H },   // 0 Agents (top left)
  { x: 1700, y: 110, w: PANEL_W, h: PANEL_H },  // 1 Servers (top right)
  { x: 1700, y: 870, w: PANEL_W, h: PANEL_H },  // 2 Vault (bottom right)
  { x: 140, y: 870, w: PANEL_W, h: PANEL_H },   // 3 Access (bottom left)
  { x: 900, y: 490, w: 760, h: 460 },           // 4 Live (center)
]

const WIDE: Rect = { x: -30, y: -30, w: BOARD_W + 60, h: BOARD_H + 60 }

/** Frame a panel with breathing room. */
function focus(p: number): Rect {
  const r = PANEL_RECTS[p]
  return { x: r.x - 70, y: r.y - 70, w: r.w + 140, h: r.h + 140 }
}

/** Push in on the centered modal of a panel. */
function modalRect(p: number): Rect {
  const r = PANEL_RECTS[p]
  return { x: r.x + 100, y: r.y + 15, w: 520, h: 430 }
}

/** Cursor position in board coordinates from panel-local coordinates. */
function at(p: number, lx: number, ly: number, click?: boolean): { x: number; y: number; click?: boolean } {
  const r = PANEL_RECTS[p]
  return { x: r.x + lx, y: r.y + ly, click }
}

// ── Camera ──────────────────────────────────────────────────────────────────────

interface Cam { cx: number; cy: number; s: number }

function cameraFor(rect: Rect, vw: number, vh: number): Cam {
  return {
    cx: rect.x + rect.w / 2,
    cy: rect.y + rect.h / 2,
    s: Math.min(vw / rect.w, vh / rect.h),
  }
}

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
}

const lerp = (a: number, b: number, t: number): number => a + (b - a) * t

// ── Tiny primitives (shared with the panel pages) ───────────────────────────────

function Typewriter({ text }: { text: string }): React.ReactElement {
  const [n, setN] = useState(0)
  useEffect(() => {
    setN(0)
    const id = setInterval(() => setN((v) => (v >= text.length ? v : v + 1)), 45)
    return () => clearInterval(id)
  }, [text])
  return (
    <span>
      {text.slice(0, n)}
      <span className="text-accent-light animate-pulse">▌</span>
    </span>
  )
}

function TourCursor({ x, y, clicking, hidden }: { x: number; y: number; clicking: boolean; hidden: boolean }): React.ReactElement {
  return (
    <div
      className="absolute top-0 left-0 z-30 pointer-events-none"
      style={{
        transform: `translate(${x}px, ${y}px)`,
        transition: 'transform 650ms cubic-bezier(0.22,1,0.36,1), opacity 300ms ease-out',
        opacity: hidden ? 0 : 1,
      }}
    >
      {clicking && !hidden && (
        <span className="absolute -left-1.5 -top-1.5 w-8 h-8 rounded-full bg-accent-light/30 animate-ping" />
      )}
      <svg width="26" height="26" viewBox="0 0 24 24" className="drop-shadow-[0_2px_5px_rgba(0,0,0,0.7)]">
        <path d="M5 3l14 7.5-6 1.5-2.5 6L5 3z" fill="#fff" stroke="#0b0b12" strokeWidth="1.2" strokeLinejoin="round" />
      </svg>
    </div>
  )
}

function PanelModal({ title, children }: { title: string; children: React.ReactNode }): React.ReactElement {
  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center animate-fade-in">
      <div className="absolute inset-0 bg-black/55" />
      <div className="relative w-[400px] bg-surface border border-border-strong rounded-xl p-5" style={{ boxShadow: '0 24px 60px rgba(0,0,0,0.55)' }}>
        <p className="text-primary font-semibold text-sm mb-4">{title}</p>
        {children}
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }): React.ReactElement {
  return (
    <div className="mb-4">
      <span className="block text-[10px] font-mono uppercase tracking-wider text-muted mb-1.5">{label}</span>
      <div className="bg-elevated border border-border-accent rounded-lg px-3 py-2 text-sm font-mono text-primary min-h-[38px]">{children}</div>
    </div>
  )
}

function PrimaryBtn({ label }: { label: string }): React.ReactElement {
  return <div className="bg-accent text-white text-xs font-semibold px-3.5 py-2 rounded-lg inline-block">{label}</div>
}

function Th({ children }: { children: React.ReactNode }): React.ReactElement {
  return <th className="py-2.5 px-4 text-left text-[10px] font-mono text-muted uppercase tracking-wider font-medium">{children}</th>
}

function StatusBadge(): React.ReactElement {
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[10px] px-1.5 py-0.5 rounded border bg-success/10 text-success border-success/20">
      <span className="w-1.5 h-1.5 rounded-full bg-success" />
      active
    </span>
  )
}

function Chip({ tone, children }: { tone: 'ok' | 'bad'; children: React.ReactNode }): React.ReactElement {
  const cls = tone === 'ok' ? 'bg-success/10 text-success border-success/20' : 'bg-error/10 text-error border-error/20'
  return <span className={`font-mono text-[10px] px-1.5 py-0.5 rounded border ${cls}`}>{children}</span>
}

function PageHeader({ title, subtitle, action }: { title: string; subtitle: string; action?: string }): React.ReactElement {
  return (
    <div className="flex items-start justify-between mb-5">
      <div>
        <h3 className="font-display text-base font-semibold tracking-tight text-primary">{title}</h3>
        <p className="text-secondary text-xs mt-0.5">{subtitle}</p>
      </div>
      {action && <PrimaryBtn label={action} />}
    </div>
  )
}

function EmptyState({ title, body }: { title: string; body: string }): React.ReactElement {
  return (
    <div className="py-10 text-center">
      <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center mx-auto mb-3">
        <span className="w-3.5 h-3.5 rounded bg-accent-light/40" />
      </div>
      <p className="text-primary text-xs font-medium mb-1">{title}</p>
      <p className="text-secondary text-[11px] max-w-[260px] mx-auto leading-relaxed">{body}</p>
    </div>
  )
}

// ── Panel pages (driven by `phase`) ─────────────────────────────────────────────

type Phase = string

function AgentsPanel({ phase }: { phase: Phase }): React.ReactElement {
  const added = phase === 'added'
  return (
    <div className="p-6">
      <PageHeader title="Agents" subtitle="Registered agent identities and their API keys" action="Register Agent" />
      <div className="bg-base/40 border border-border rounded-xl overflow-hidden">
        <table className="min-w-full">
          <thead><tr className="border-b border-border"><Th>Name</Th><Th>Status</Th><Th>Scope</Th><Th>Rate limit</Th></tr></thead>
          <tbody>
            {added ? (
              <tr className="animate-fade-in">
                <td className="py-3 px-4 text-sm font-mono text-accent-light">claude-code-demo</td>
                <td className="py-3 px-4"><StatusBadge /></td>
                <td className="py-3 px-4 text-sm text-secondary">Scoped</td>
                <td className="py-3 px-4 text-sm font-mono text-secondary tabular-nums">60/min</td>
              </tr>
            ) : (
              <tr><td colSpan={4}><EmptyState title="No agents registered yet" body="Register your first agent to start routing tool calls through Arbiter." /></td></tr>
            )}
          </tbody>
        </table>
      </div>
      {added && (
        <p className="text-muted text-[11px] mt-3 font-mono">key: <span className="text-secondary">arb_live_</span>9f2c…e81a <span className="text-muted">(shown once, hashed at rest)</span></p>
      )}
      {phase === 'modal' && (
        <PanelModal title="Register Agent">
          <Field label="Name"><Typewriter text="claude-code-demo" /></Field>
          <div className="mb-4">
            <span className="block text-[10px] font-mono uppercase tracking-wider text-muted mb-1.5">Scope</span>
            <div className="flex gap-2">
              <div className="flex-1 border border-border-accent bg-accent/10 text-accent-light rounded-lg px-3 py-2 text-xs font-medium">Scoped</div>
              <div className="flex-1 border border-border text-muted rounded-lg px-3 py-2 text-xs">Full</div>
            </div>
          </div>
          <div className="flex justify-end"><PrimaryBtn label="Create agent" /></div>
        </PanelModal>
      )}
    </div>
  )
}

function ServersPanel({ phase }: { phase: Phase }): React.ReactElement {
  const added = phase === 'added'
  return (
    <div className="p-6">
      <PageHeader title="MCP Servers" subtitle="Connected tool servers proxied through Arbiter" action="Add Server" />
      <div className="bg-base/40 border border-border rounded-xl overflow-hidden">
        <table className="min-w-full">
          <thead><tr className="border-b border-border"><Th>Name</Th><Th>Base URL</Th><Th>Cache</Th><Th>Status</Th></tr></thead>
          <tbody>
            {added ? (
              <tr className="animate-fade-in">
                <td className="py-3 px-4 text-sm font-mono text-accent-light">deepwiki</td>
                <td className="py-3 px-4 text-sm font-mono text-secondary">mcp.deepwiki.com</td>
                <td className="py-3 px-4"><Chip tone="ok">semantic</Chip></td>
                <td className="py-3 px-4"><StatusBadge /></td>
              </tr>
            ) : (
              <tr><td colSpan={4}><EmptyState title="No MCP servers registered" body="Add a server to start routing tool calls through Arbiter." /></td></tr>
            )}
          </tbody>
        </table>
      </div>
      {added && (
        <p className="text-muted text-[11px] mt-3">3 tools discovered: <span className="font-mono text-secondary">ask_question, read_wiki_structure, read_wiki_contents</span></p>
      )}
      {phase === 'modal' && (
        <PanelModal title="Add MCP Server">
          <Field label="Name"><Typewriter text="deepwiki" /></Field>
          <Field label="Base URL"><span className="text-secondary">https://mcp.deepwiki.com</span></Field>
          <div className="flex justify-end"><PrimaryBtn label="Add server" /></div>
        </PanelModal>
      )}
    </div>
  )
}

function VaultPanel({ phase }: { phase: Phase }): React.ReactElement {
  const added = phase === 'added'
  return (
    <div className="p-6">
      <PageHeader title="Vault" subtitle="Per-agent secrets, encrypted at rest" action="Add Secret" />
      <p className="text-secondary text-xs mb-3">Agent: <span className="font-mono text-accent-light">claude-code-demo</span></p>
      <div className="bg-base/40 border border-border rounded-xl overflow-hidden">
        <table className="min-w-full">
          <thead><tr className="border-b border-border"><Th>Name</Th><Th>Value</Th><Th>Encryption</Th></tr></thead>
          <tbody>
            {added ? (
              <tr className="animate-fade-in">
                <td className="py-3 px-4 text-sm font-mono text-accent-light">DATABASE_URL</td>
                <td className="py-3 px-4 text-sm font-mono text-muted tracking-widest">••••••••••</td>
                <td className="py-3 px-4"><Chip tone="ok">AES-256-GCM</Chip></td>
              </tr>
            ) : (
              <tr><td colSpan={3}><EmptyState title="No secrets stored" body="Store a secret to inject it into tool calls at the gateway." /></td></tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-muted text-[11px] mt-3">
        Injected at the gateway as <span className="font-mono text-accent-light">{'{{DATABASE_URL}}'}</span>, never returned to the agent.
      </p>
      {phase === 'modal' && (
        <PanelModal title="Add Secret: claude-code-demo">
          <Field label="Name"><Typewriter text="DATABASE_URL" /></Field>
          <Field label="Value"><span className="text-muted tracking-widest">••••••••••••••••</span></Field>
          <div className="flex justify-end"><PrimaryBtn label="Store secret" /></div>
        </PanelModal>
      )}
    </div>
  )
}

function AccessPanel({ phase }: { phase: Phase }): React.ReactElement {
  const granted = phase === 'granted'
  return (
    <div className="p-6">
      <PageHeader title="Tool Permissions" subtitle="Control which tools each agent may invoke" />
      <div className="border border-border rounded-xl p-4 bg-base/40">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-mono text-accent-light">claude-code-demo · deepwiki</p>
          <span className="text-muted text-[11px]">{granted ? '1 tool granted' : 'select tools to grant'}</span>
        </div>
        <div className="space-y-0.5">
          <div className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors duration-300 ${granted ? 'bg-success/10' : ''}`}>
            <span className={`w-4 h-4 rounded border flex items-center justify-center ${granted ? 'bg-success border-success' : 'border-border-strong'}`}>
              {granted && <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#0b0b12" strokeWidth="3.5"><path d="M5 13l4 4L19 7" /></svg>}
            </span>
            <span className={`font-mono text-xs ${granted ? 'text-success' : 'text-primary'}`}>ask_question</span>
            {granted && <span className="ml-auto"><Chip tone="ok">ALLOW</Chip></span>}
          </div>
          <div className="flex items-center gap-3 px-3 py-2 rounded-lg">
            <span className="w-4 h-4 rounded border border-border-strong" />
            <span className="font-mono text-xs text-secondary">read_wiki_structure</span>
          </div>
          <div className="flex items-center gap-3 px-3 py-2 rounded-lg">
            <span className="w-4 h-4 rounded border border-border" />
            <span className="font-mono text-xs text-muted">read_wiki_contents</span>
            <span className="ml-auto"><Chip tone="bad">DENY</Chip></span>
          </div>
        </div>
        <div className="flex justify-end mt-3"><PrimaryBtn label="Save permissions" /></div>
      </div>
      <p className="text-muted text-[11px] mt-3">Deny by default: anything not granted here is blocked at the gateway.</p>
    </div>
  )
}

function GraphNode({ label, sub, tone }: { label: string; sub: string; tone: 'base' | 'accent' | 'green' | 'red' }): React.ReactElement {
  const ring = tone === 'accent' ? 'border-accent/40 bg-accent/10' : tone === 'green' ? 'border-success/40 bg-success/10' : tone === 'red' ? 'border-error/40 bg-error/10' : 'border-border bg-elevated/50'
  const txt = tone === 'green' ? 'text-success' : tone === 'red' ? 'text-error' : tone === 'accent' ? 'text-accent-light' : 'text-primary'
  return (
    <div className={`rounded-xl border px-4 py-3 text-center min-w-[150px] transition-colors duration-300 ${ring}`}>
      <p className={`font-mono text-xs font-semibold ${txt}`}>{label}</p>
      <p className="text-muted text-[10px] mt-0.5">{sub}</p>
    </div>
  )
}

function GraphLink({ tone }: { tone: 'idle' | 'green' | 'red' }): React.ReactElement {
  const color = tone === 'green' ? 'bg-success' : tone === 'red' ? 'bg-error' : 'bg-border-strong'
  return (
    <div className="flex-1 relative h-px mx-2 self-center">
      <div className={`absolute inset-0 ${color} transition-colors duration-300`} />
      {tone === 'red' && (
        <svg width="12" height="12" viewBox="0 0 24 24" className="absolute left-1/2 -translate-x-1/2 -top-[15px] text-error" fill="none" stroke="currentColor" strokeWidth="3">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      )}
    </div>
  )
}

function LivePanel({ phase }: { phase: Phase }): React.ReactElement {
  const idle = phase === 'idle'
  const denied = phase === 'denied'
  return (
    <div className="p-6">
      <PageHeader title="Live" subtitle="A client calling tools through the Arbiter gateway" />
      <div className="bg-base/40 border border-border rounded-xl p-4 mb-4">
        <div className="flex items-stretch">
          <GraphNode label="Claude Code" sub={idle ? 'MCP client' : denied ? 'read_wiki_contents' : 'ask_question'} tone="base" />
          <GraphLink tone={idle ? 'idle' : 'green'} />
          <GraphNode label="Arbiter" sub={idle ? 'gateway' : denied ? 'RBAC · blocked' : 'RBAC · cache · audit'} tone={idle ? 'base' : denied ? 'red' : 'accent'} />
          <GraphLink tone={idle ? 'idle' : denied ? 'red' : 'green'} />
          <GraphNode label="deepwiki" sub="MCP server" tone={idle || denied ? 'base' : 'green'} />
        </div>
      </div>
      <p className="text-muted text-[10px] font-mono uppercase tracking-widest mb-2">Audit log</p>
      <div className="bg-base/40 border border-border rounded-xl overflow-hidden">
        <table className="min-w-full">
          <tbody>
            {idle ? (
              <tr><td className="py-4 px-4 text-xs text-muted text-center">No calls yet. Traffic appears here in real time.</td></tr>
            ) : (
              <>
                <tr className="border-b border-border animate-fade-in">
                  <td className="py-2 px-4 text-xs font-mono text-accent-light">ask_question</td>
                  <td className="py-2 px-4 text-xs text-muted">deepwiki</td>
                  <td className="py-2 px-4"><Chip tone="ok">ALLOWED</Chip></td>
                  <td className="py-2 px-4 text-xs font-mono text-muted text-right tabular-nums">1240ms</td>
                </tr>
                {denied && (
                  <tr className="bg-error/10 animate-fade-in">
                    <td className="py-2 px-4 text-xs font-mono text-error">read_wiki_contents</td>
                    <td className="py-2 px-4 text-xs text-muted">deepwiki</td>
                    <td className="py-2 px-4"><Chip tone="bad">DENIED</Chip></td>
                    <td className="py-2 px-4 text-xs font-mono text-muted text-right tabular-nums">4ms</td>
                  </tr>
                )}
              </>
            )}
          </tbody>
        </table>
      </div>
      {phase === 'allowed' && (
        <p className="text-muted text-[11px] mt-3 animate-fade-in">
          Response embedded and cached: a semantically similar question now returns in ~12ms.
        </p>
      )}
      {denied && (
        <p className="text-error text-[11px] font-mono mt-3 animate-fade-in">
          403: agent &lsquo;claude-code-demo&rsquo; is not permitted to call &lsquo;read_wiki_contents&rsquo; on &lsquo;deepwiki&rsquo;.
        </p>
      )}
    </div>
  )
}

// ── Panel window chrome ─────────────────────────────────────────────────────────

const PANEL_META = [
  { title: 'arbiter / agents', icon: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z' },
  { title: 'arbiter / servers', icon: 'M4 4h16v6H4zM4 14h16v6H4zM8 7h.01M8 17h.01' },
  { title: 'arbiter / vault', icon: 'M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2zM7 11V7a5 5 0 0 1 10 0v4' },
  { title: 'arbiter / permissions', icon: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' },
  { title: 'arbiter / live', icon: 'M22 12h-4l-3 9L9 3l-3 9H2' },
]

function PanelWindow({ index, active, children }: { index: number; active: boolean; children: React.ReactNode }): React.ReactElement {
  const rect = PANEL_RECTS[index]
  const meta = PANEL_META[index]
  return (
    <section
      className="absolute rounded-2xl border bg-surface overflow-hidden"
      style={{
        left: rect.x,
        top: rect.y,
        width: rect.w,
        height: rect.h,
        borderColor: active ? 'var(--color-border-accent)' : 'var(--color-border)',
        boxShadow: active ? '0 32px 80px rgba(0,0,0,0.5), var(--glow-subtle)' : '0 24px 60px rgba(0,0,0,0.35)',
        transition: 'border-color 500ms var(--ease-out-quart), box-shadow 500ms var(--ease-out-quart)',
      }}
    >
      <header className="h-10 flex items-center gap-2.5 px-4 border-b border-border bg-elevated/70">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={active ? 'text-accent-light' : 'text-muted'}>
          <path d={meta.icon} />
        </svg>
        <span className="font-mono text-[11px] tracking-wide text-secondary">{meta.title}</span>
        <span className="ml-auto font-mono text-[10px] text-muted tabular-nums">0{index + 1} / 05</span>
      </header>
      <div className="relative" style={{ height: rect.h - 40 }}>{children}</div>
    </section>
  )
}

// ── Board connections (lit as chapters complete) ────────────────────────────────

const CONNECTIONS = [
  'M 870 340 C 1150 380, 1420 380, 1690 340',    // Agents to Servers
  'M 2060 580 C 2100 680, 2100 760, 2060 860',   // Servers to Vault
  'M 1690 1100 C 1420 1150, 1150 1150, 870 1100', // Vault to Access
  'M 500 860 C 520 760, 720 720, 890 720',        // Access to Live
]

function BoardConnections({ chapter }: { chapter: number }): React.ReactElement {
  return (
    <svg className="absolute inset-0 pointer-events-none" width={BOARD_W} height={BOARD_H} viewBox={`0 0 ${BOARD_W} ${BOARD_H}`} aria-hidden>
      {CONNECTIONS.map((d, i) => {
        const lit = chapter > i
        return (
          <path
            key={d}
            d={d}
            fill="none"
            stroke={lit ? 'var(--color-accent-light)' : 'var(--color-border-strong)'}
            strokeOpacity={lit ? 0.55 : 0.9}
            strokeWidth={2}
            strokeDasharray={lit ? 'none' : '4 10'}
            strokeLinecap="round"
            style={{ transition: 'stroke 600ms var(--ease-out-quart), stroke-opacity 600ms var(--ease-out-quart)' }}
          />
        )
      })}
    </svg>
  )
}

// ── Script ──────────────────────────────────────────────────────────────────────

interface Step {
  /** Active bottom tab. -1 highlights none (wide establishing shot). */
  tab: number
  /** World-state chapter: panels before it show final state, after it initial. */
  chapter: number
  phase: Phase
  caption: string
  camera: Rect
  cursor?: { x: number; y: number; click?: boolean }
  hold: number
}

const STEPS: Step[] = [
  // Establishing shot
  { tab: -1, chapter: -1, phase: 'none', camera: WIDE, hold: 2200, caption: 'One gateway between your agents and every MCP tool. Watch the setup, then a live call.' },

  // 1: Agents
  { tab: 0, chapter: 0, phase: 'empty', camera: focus(0), cursor: at(0, 630, 82), hold: 1500, caption: 'Register an agent: it gets its own cryptographic identity and key.' },
  { tab: 0, chapter: 0, phase: 'modal', camera: modalRect(0), cursor: at(0, 300, 195), hold: 2100, caption: 'Name it, choose a scope.' },
  { tab: 0, chapter: 0, phase: 'modal', camera: modalRect(0), cursor: at(0, 500, 328, true), hold: 800, caption: 'Create the agent.' },
  { tab: 0, chapter: 0, phase: 'added', camera: focus(0), cursor: at(0, 210, 185), hold: 1800, caption: 'claude-code-demo is live: active, scoped, rate-limited.' },

  // 2: Servers
  { tab: 1, chapter: 1, phase: 'empty', camera: focus(1), cursor: at(1, 638, 82), hold: 1400, caption: 'Connect an MCP server to proxy its tools through Arbiter.' },
  { tab: 1, chapter: 1, phase: 'modal', camera: modalRect(1), cursor: at(1, 500, 330, true), hold: 1900, caption: 'Point Arbiter at the upstream server.' },
  { tab: 1, chapter: 1, phase: 'added', camera: focus(1), cursor: at(1, 210, 185), hold: 1700, caption: 'deepwiki is connected, with semantic caching on.' },

  // 3: Vault
  { tab: 2, chapter: 2, phase: 'empty', camera: focus(2), cursor: at(2, 640, 82), hold: 1400, caption: 'Store secrets in the per-agent vault.' },
  { tab: 2, chapter: 2, phase: 'modal', camera: modalRect(2), cursor: at(2, 500, 322, true), hold: 1900, caption: 'Encrypted with AES-256-GCM before it ever touches disk.' },
  { tab: 2, chapter: 2, phase: 'added', camera: focus(2), cursor: at(2, 210, 215), hold: 1900, caption: 'Injected at the gateway as {{NAME}}, never returned to the agent.' },

  // 4: Access
  { tab: 3, chapter: 3, phase: 'select', camera: focus(3), cursor: at(3, 185, 190, true), hold: 1600, caption: 'Grant exactly which tools the agent may call.' },
  { tab: 3, chapter: 3, phase: 'granted', camera: focus(3), cursor: at(3, 620, 340, true), hold: 2100, caption: 'ask_question is allowed. read_wiki_contents stays denied.' },

  // 5: Live
  { tab: 4, chapter: 4, phase: 'allowed', camera: focus(4), hold: 2100, caption: 'The agent calls ask_question: allowed, served, and logged.' },
  { tab: 4, chapter: 4, phase: 'denied', camera: focus(4), hold: 2600, caption: 'It tries read_wiki_contents: blocked at call time by per-agent RBAC.' },

  // Closing shot
  { tab: 4, chapter: 5, phase: 'none', camera: WIDE, hold: 3400, caption: 'Identity, permissions, secrets, and a full audit trail: one gateway in front of every tool.' },
]

const INITIAL_PHASE: Phase[] = ['empty', 'empty', 'empty', 'select', 'idle']
const FINAL_PHASE: Phase[] = ['added', 'added', 'added', 'granted', 'denied']

function phaseFor(panel: number, step: Step): Phase {
  if (step.chapter === panel) return step.phase
  return step.chapter > panel ? FINAL_PHASE[panel] : INITIAL_PHASE[panel]
}

const chapterStart = (tab: number): number => Math.max(0, STEPS.findIndex((s) => s.tab === tab))

/** Last step of a chapter (used for reduced motion: show the finished state). */
const chapterEnd = (tab: number): number => {
  for (let i = STEPS.length - 1; i >= 0; i -= 1) {
    if (STEPS[i].tab === tab && STEPS[i].chapter === tab) return i
  }
  return STEPS.length - 1
}

// ── Bottom tabs ─────────────────────────────────────────────────────────────────

const TAB_LABELS = ['Agents', 'Servers', 'Vault', 'Access', 'Live']

function BottomTabs({ active, onSelect }: { active: number; onSelect: (tab: number) => void }): React.ReactElement {
  return (
    <div className="absolute left-1/2 -translate-x-1/2 bottom-3 z-20">
      <div className="flex items-center glass-surface border border-border rounded-xl px-1 py-1" style={{ boxShadow: '0 12px 30px rgba(0,0,0,0.45)' }}>
        {TAB_LABELS.map((label, idx) => (
          <React.Fragment key={label}>
            {idx > 0 && <span className="w-px h-4 bg-border mx-0.5" aria-hidden />}
            <button
              type="button"
              onClick={() => onSelect(idx)}
              aria-label={`Jump to ${label} chapter`}
              aria-current={idx === active ? 'step' : undefined}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors duration-150 ease-[var(--ease-out-quart)] ${idx === active ? 'bg-accent/15 text-accent-light' : 'text-muted hover:text-secondary'}`}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d={PANEL_META[idx].icon} />
              </svg>
              {label}
            </button>
          </React.Fragment>
        ))}
      </div>
    </div>
  )
}

// ── Component ───────────────────────────────────────────────────────────────────

export default function HeroProductTour(): React.ReactElement {
  const prefersReduced =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  const frameRef = useRef<HTMLDivElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const camRef = useRef<Cam>({ cx: BOARD_W / 2, cy: BOARD_H / 2, s: 0.3 })
  const rafRef = useRef<number>(0)

  const [vp, setVp] = useState({ w: 0, h: 0 })
  const [idx, setIdx] = useState(prefersReduced ? STEPS.length - 1 : 0)
  const [hovered, setHovered] = useState(false)
  const [visible, setVisible] = useState(true)

  // Measure the viewport (frame keeps a fixed aspect ratio, width is fluid).
  useLayoutEffect(() => {
    const el = frameRef.current
    if (!el) return
    const update = (): void => setVp({ w: el.clientWidth, h: el.clientHeight })
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Pause playback while offscreen.
  useEffect(() => {
    const el = frameRef.current
    if (!el || typeof IntersectionObserver === 'undefined') return
    const io = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0.15 })
    io.observe(el)
    return () => io.disconnect()
  }, [])

  useEffect(() => () => cancelAnimationFrame(rafRef.current), [])

  const applyCam = (cam: Cam, vw: number, vh: number): void => {
    camRef.current = cam
    const stage = stageRef.current
    if (!stage) return
    stage.style.transform = `translate3d(${vw / 2 - cam.cx * cam.s}px, ${vh / 2 - cam.cy * cam.s}px, 0) scale(${cam.s})`
  }

  /**
   * Glide the camera to `target`. Returns the travel duration in ms.
   * Long moves dip the zoom mid-flight (pull back, pan, push in).
   */
  const glideTo = (target: Cam, vw: number, vh: number, snap: boolean): number => {
    cancelAnimationFrame(rafRef.current)
    const from = { ...camRef.current }
    const dist = Math.hypot(target.cx - from.cx, target.cy - from.cy)
    const zoomDelta = Math.abs(Math.log(target.s / from.s))
    if (snap || (dist < 1 && zoomDelta < 0.01)) {
      applyCam(target, vw, vh)
      return 0
    }
    const dur = Math.min(900, Math.max(500, 460 + dist * 0.28 + zoomDelta * 220))
    const dip = Math.min(0.45, (dist / BOARD_W) * 0.75)
    const t0 = performance.now()
    const tick = (now: number): void => {
      const t = Math.min(1, (now - t0) / dur)
      const e = easeInOutCubic(t)
      const s = Math.exp(lerp(Math.log(from.s), Math.log(target.s), e)) * (1 - dip * Math.sin(Math.PI * e))
      applyCam({ cx: lerp(from.cx, target.cx, e), cy: lerp(from.cy, target.cy, e), s }, vw, vh)
      if (t < 1) rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return dur
  }

  // Drive the camera and the step clock.
  useEffect(() => {
    if (vp.w === 0 || vp.h === 0) return
    const step = STEPS[idx]
    const dur = glideTo(cameraFor(step.camera, vp.w, vp.h), vp.w, vp.h, prefersReduced)
    if (prefersReduced || hovered || !visible) return
    const t = setTimeout(() => setIdx((i) => (i + 1) % STEPS.length), dur + step.hold)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idx, vp, hovered, visible, prefersReduced])

  const step = STEPS[idx]
  const cursor = step.cursor
  const panels = [AgentsPanel, ServersPanel, VaultPanel, AccessPanel, LivePanel]

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div
        ref={frameRef}
        className="relative rounded-xl overflow-hidden bg-base border border-border-strong"
        style={{
          boxShadow: '0 24px 60px rgba(0,0,0,0.45)',
          aspectRatio: `${VIEW_W} / ${VIEW_H}`,
        }}
        role="group"
        aria-label="Arbiter product tour"
      >
        {/* Stage: the board the camera glides across */}
        <div
          ref={stageRef}
          className="absolute top-0 left-0"
          style={{
            width: BOARD_W,
            height: BOARD_H,
            transformOrigin: '0 0',
            willChange: 'transform',
            backgroundImage: 'radial-gradient(var(--color-highlight) 1.5px, transparent 1.5px)',
            backgroundSize: '36px 36px',
          }}
        >
          <BoardConnections chapter={step.chapter} />
          {panels.map((Panel, i) => (
            <PanelWindow key={PANEL_META[i].title} index={i} active={step.chapter === i}>
              <Panel phase={phaseFor(i, step)} />
            </PanelWindow>
          ))}
          {!prefersReduced && (
            <TourCursor
              x={cursor?.x ?? BOARD_W / 2}
              y={cursor?.y ?? BOARD_H / 2}
              clicking={!!cursor?.click}
              hidden={!cursor}
            />
          )}
        </div>

        {/* Overlay chrome: chapter tabs in screen space, unaffected by the camera */}
        <BottomTabs active={step.tab} onSelect={(tab) => setIdx(prefersReduced ? chapterEnd(tab) : chapterStart(tab))} />
      </div>

      <p className="mt-3 text-muted text-xs leading-relaxed min-h-[2rem]" aria-live="polite">
        {step.tab >= 0 && <span className="text-secondary font-medium">{TAB_LABELS[step.tab]}. </span>}
        {step.caption} <span className="text-muted/70">Hover to pause.</span>
      </p>
    </div>
  )
}
