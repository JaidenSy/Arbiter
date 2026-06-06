import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useScrollReveal } from '../hooks/useScrollReveal'

// ── Token-based line definitions ──────────────────────────────────────────────

type Token = { text: string; color?: string }
type CodeLine = Token[]

const C = {
  primary:   'var(--color-primary)',
  secondary: 'var(--color-secondary)',
  muted:     'var(--color-muted)',
  accent:    'var(--color-accent-light)',
  teal:      'var(--color-teal-light)',
  success:   'var(--color-success)',
  warning:   'var(--color-warning)',
}

const CLI_LINES: CodeLine[] = [
  [{ text: '$ ', color: C.muted }, { text: 'npm install -g @arbiterai/cli', color: C.primary }],
  [{ text: '$ ', color: C.muted }, { text: 'arbiter ', color: C.accent }, { text: 'login', color: C.primary }],
  [{ text: '  ✔ Authenticated as ', color: C.success }, { text: 'you@arbiterai.dev', color: C.teal }],
  [
    { text: '$ ', color: C.muted },
    { text: 'arbiter ', color: C.accent },
    { text: 'agent create ', color: C.primary },
    { text: '--name ', color: C.accent },
    { text: '"claude-local"', color: C.success },
  ],
  [{ text: '  ✔ Agent created · key: ', color: C.success }, { text: 'arb_sk_k7x2m9...', color: C.teal }],
  [
    { text: '$ ', color: C.muted },
    { text: 'arbiter ', color: C.accent },
    { text: 'permissions grant ', color: C.primary },
    { text: '--agent ', color: C.accent },
    { text: 'claude-local ', color: C.success },
    { text: '--server ', color: C.accent },
    { text: 'filesystem', color: C.success },
  ],
  [{ text: '  ✔ Permission granted', color: C.success }],
  [],
  [
    { text: '✓ Connected   ', color: C.success },
    { text: '1 agent · filesystem · logging on', color: C.teal },
  ],
]

const CONFIG_LINES: CodeLine[] = [
  [{ text: '# Add to your MCP client config', color: C.muted }],
  [{ text: '{', color: C.teal }],
  [
    { text: '  ', color: C.primary },
    { text: '"mcpServers"', color: C.accent },
    { text: ': {', color: C.primary },
  ],
  [
    { text: '    ', color: C.primary },
    { text: '"arbiter"', color: C.accent },
    { text: ': {', color: C.primary },
  ],
  [
    { text: '      ', color: C.primary },
    { text: '"url"', color: C.accent },
    { text: ': ', color: C.primary },
    { text: '"https://api.arbiterai.dev/mcp/arb_sk_..."', color: C.success },
  ],
  [{ text: '    }', color: C.primary }],
  [{ text: '  }', color: C.primary }],
  [{ text: '}', color: C.teal }],
  [],
  [
    { text: '✓ Connected   ', color: C.success },
    { text: '2 agents · 3 MCP servers · logging on', color: C.teal },
  ],
]

function lineLen(line: CodeLine): number {
  return line.reduce((s, t) => s + t.text.length, 0)
}

const CHAR_DELAY = 22

// ── Component ─────────────────────────────────────────────────────────────────

interface Props {
  onGetStarted: () => void
}

export default function GatewayConnectedCTA({ onGetStarted }: Props): React.ReactElement {
  const prefersReduced =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  const [activeTab,   setActiveTab]   = useState<'cli' | 'config'>('cli')
  const [started,     setStarted]     = useState(false)
  const [chars,       setChars]       = useState(0)
  const [ctasVisible, setCtasVisible] = useState(prefersReduced)
  const sectionRef  = useRef<HTMLElement>(null)
  const headingRef  = useScrollReveal<HTMLHeadingElement>()

  const LINES      = activeTab === 'cli' ? CLI_LINES : CONFIG_LINES
  const TOTAL_CHARS = LINES.reduce((s, l) => s + lineLen(l), 0)
  const done       = chars >= TOTAL_CHARS

  // Start typing when section enters viewport
  useEffect(() => {
    if (prefersReduced) return
    const el = sectionRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setStarted(true); observer.disconnect() } },
      { threshold: 0.3 }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [prefersReduced])

  // Typewriter loop
  useEffect(() => {
    if (!started || done) return
    const t = setTimeout(() => setChars(n => n + 1), CHAR_DELAY)
    return () => clearTimeout(t)
  }, [started, chars, done])

  // Show CTAs 600ms after typing completes
  useEffect(() => {
    if (!done || ctasVisible) return
    const t = setTimeout(() => setCtasVisible(true), 600)
    return () => clearTimeout(t)
  }, [done, ctasVisible])

  function switchTab(tab: 'cli' | 'config') {
    setActiveTab(tab)
    setChars(0)
    setCtasVisible(false)
  }

  // Render lines up to `chars`
  let consumed = 0
  const renderedLines = LINES.map((line, li) => {
    const len     = lineLen(line)
    const show    = Math.max(0, Math.min(len, chars - consumed))
    const isActive = done
      ? li === LINES.length - 1
      : chars > consumed && chars <= consumed + len && len > 0
    consumed += len

    let rem = show
    const spans = line.map((tok, ti) => {
      if (rem <= 0) return null
      const visible = tok.text.slice(0, rem)
      rem -= tok.text.length
      return <span key={ti} style={tok.color ? { color: tok.color } : undefined}>{visible}</span>
    })

    return (
      <div key={li} style={{ minHeight: '1.35em' }}>
        {spans}
        {isActive && (
          <span className="blink-cursor" style={{ color: 'var(--color-accent-light)' }}>▋</span>
        )}
      </div>
    )
  })

  return (
    <section
      ref={sectionRef}
      className="py-32 px-6 border-t border-border"
      style={{ background: 'rgba(15,15,18,0.6)' }}
    >
      <div className="max-w-2xl mx-auto text-center">
        <h2
          ref={headingRef}
          className="font-display text-3xl font-semibold tracking-tight text-primary mb-10"
          style={{ textWrap: 'balance' } as React.CSSProperties}
        >
          Thirty seconds to a secured gateway.
        </h2>

        {/* Tab switcher */}
        <div className="flex items-center justify-center gap-1 mb-4">
          {(['cli', 'config'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => switchTab(tab)}
              className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-colors duration-150 ${
                activeTab === tab
                  ? 'bg-accent/15 text-accent border border-accent/25'
                  : 'text-muted hover:text-secondary border border-transparent'
              }`}
            >
              {tab === 'cli' ? 'CLI' : 'Config'}
            </button>
          ))}
        </div>

        {/* Terminal */}
        <div className="bg-elevated border border-border-strong rounded-lg p-5 text-left mb-10">
          <div className="flex items-center gap-1.5 mb-4">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(248,113,113,0.60)' }} />
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(251,191,36,0.60)' }} />
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(52,211,153,0.60)' }} />
          </div>
          <div className="font-mono text-xs leading-relaxed">
            {renderedLines}
          </div>
        </div>

        {/* CTAs */}
        <div
          className="flex flex-col sm:flex-row items-center justify-center gap-3"
          style={{
            opacity:    ctasVisible ? 1 : 0,
            transform:  ctasVisible ? 'translateY(0)' : 'translateY(8px)',
            transition: 'opacity 300ms cubic-bezier(0.16,1,0.3,1), transform 300ms cubic-bezier(0.16,1,0.3,1)',
          }}
        >
          <button
            onClick={onGetStarted}
            className="press bg-accent hover:bg-accent-light text-white font-semibold px-6 py-3 rounded-xl transition-[background-color,box-shadow] duration-150 ease-[var(--ease-out-expo)] hover-glow-standard text-sm"
          >
            Start for Free
          </button>
          <Link
            to="/docs"
            className="press border border-border-strong hover:border-border-accent text-secondary hover:text-primary px-6 py-3 rounded-xl text-sm transition-colors duration-150 ease-[var(--ease-out-expo)]"
          >
            Read the docs
          </Link>
        </div>
      </div>
    </section>
  )
}
