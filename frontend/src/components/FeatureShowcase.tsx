import React, { useEffect, useRef, useState } from 'react'
import { useScrollReveal } from '../hooks/useScrollReveal'

// ── Color aliases ─────────────────────────────────────────────────────────────

const T = {
  primary:  'var(--color-primary)',
  muted:    'var(--color-muted)',
  accent:   'var(--color-accent-light)',
  teal:     'var(--color-teal-light)',
  success:  'var(--color-success)',
  warning:  'var(--color-warning)',
  error:    'var(--color-error)',
}

// ── Token-based code renderer (avoids deep JSX nesting) ──────────────────────

type Token = { text: string; color?: string }
type CodeLine = Token[]

function CodePanel({ lines }: { lines: CodeLine[] }): React.ReactElement {
  return (
    <div className="bg-[#0A0A0B] border border-border rounded-xl overflow-hidden">
      <div className="flex items-center gap-1.5 px-4 py-3 border-b border-border">
        <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(248,113,113,0.50)' }} />
        <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(251,191,36,0.50)' }} />
        <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(52,211,153,0.50)' }} />
      </div>
      <div className="font-mono text-xs leading-relaxed px-5 py-4 overflow-x-auto">
        {lines.map((line, i) => (
          <div key={i} style={{ minHeight: '1.25em' }}>
            {line.length === 0
              ? ' '
              : line.map((tok, j) => (
                  <span key={j} style={tok.color ? { color: tok.color } : undefined}>
                    {tok.text}
                  </span>
                ))}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Step content ──────────────────────────────────────────────────────────────

const REGISTER_LINES: CodeLine[] = [
  [{ text: '$ ', color: T.muted }, { text: 'arbiter ', color: T.accent }, { text: 'agent create ', color: T.primary }, { text: '--name ', color: T.accent }, { text: '"claude-local"', color: T.success }],
  [],
  [{ text: '✔ Agent created', color: T.success }],
  [{ text: '{', color: T.teal }],
  [{ text: '  "id":      ', color: T.accent }, { text: '"agt_k7x2m9p3"', color: T.success }, { text: ',', color: T.primary }],
  [{ text: '  "name":    ', color: T.accent }, { text: '"claude-local"', color: T.success }, { text: ',', color: T.primary }],
  [{ text: '  "api_key": ', color: T.accent }, { text: '"arb_sk_k7x2m9p3..."', color: T.success }],
  [{ text: '}', color: T.teal }],
  [],
  [{ text: '⚠ Copy the key — it will not be shown again.', color: T.warning }],
]

const PROXY_LINES: CodeLine[] = [
  [{ text: 'POST', color: T.accent }, { text: ' /api/v1/proxy/tool-call', color: T.primary }],
  [{ text: 'Authorization: Bearer ', color: T.muted }, { text: 'nxai_k7x2m9p3r1...', color: T.success }],
  [],
  [{ text: '{', color: T.teal }],
  [{ text: '  "server_name": ', color: T.accent }, { text: '"filesystem"', color: T.success }, { text: ',', color: T.primary }],
  [{ text: '  "tool_name":   ', color: T.accent }, { text: '"read_file"', color: T.success }, { text: ',', color: T.primary }],
  [{ text: '  "params":      ', color: T.accent }, { text: '{ "path": "/app/config.json" }', color: T.primary }],
  [{ text: '}', color: T.teal }],
  [],
  [
    { text: '→  { ', color: T.teal },
    { text: '"cached"', color: T.accent },
    { text: ': ', color: T.primary },
    { text: 'false', color: T.warning },
    { text: ', ', color: T.primary },
    { text: '"agent_id"', color: T.accent },
    { text: ': ', color: T.primary },
    { text: '"agt_k7x..."', color: T.success },
    { text: ' }', color: T.teal },
  ],
]

function StepPermissions(): React.ReactElement {
  return (
    <div className="bg-elevated border border-border rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <span className="font-mono text-xs text-muted">claude-local · permissions</span>
        <span className="font-mono text-xs" style={{ color: T.accent }}>2 of 6 active</span>
      </div>
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left px-4 py-2.5 font-mono font-normal text-muted">tool</th>
            <th className="text-left px-4 py-2.5 font-mono font-normal text-muted">server</th>
            <th className="text-left px-4 py-2.5 font-mono font-normal text-muted">access</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-b border-border">
            <td className="px-4 py-2.5 font-mono" style={{ color: T.accent }}>read_file</td>
            <td className="px-4 py-2.5 font-mono text-muted">filesystem</td>
            <td className="px-4 py-2.5">
              <span className="inline-flex items-center gap-1 font-mono text-[10px] font-medium px-1.5 py-0.5 rounded border"
                style={{ color: '#34D399', background: 'rgba(52,211,153,0.10)', borderColor: 'rgba(52,211,153,0.20)' }}>
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden>
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                ALLOWED
              </span>
            </td>
          </tr>
          <tr>
            <td className="px-4 py-2.5 font-mono" style={{ color: T.accent }}>write_file</td>
            <td className="px-4 py-2.5 font-mono text-muted">filesystem</td>
            <td className="px-4 py-2.5">
              <span className="inline-flex items-center gap-1 font-mono text-[10px] font-medium px-1.5 py-0.5 rounded border"
                style={{ color: '#F87171', background: 'rgba(248,113,113,0.10)', borderColor: 'rgba(248,113,113,0.20)' }}>
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden>
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
                DENIED
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}

function StepTrace(): React.ReactElement {
  return (
    <div className="bg-elevated border border-border rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
        <span className="font-mono text-xs text-muted">Mission Control — latest call</span>
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-success" style={{ animation: 'blink-cursor 1.8s step-end infinite' }} />
          <span className="font-mono text-xs text-muted">live</span>
        </div>
      </div>
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left px-4 py-2 font-mono font-normal text-muted">agent</th>
            <th className="text-left px-4 py-2 font-mono font-normal text-muted">tool</th>
            <th className="text-left px-4 py-2 font-mono font-normal text-muted hidden sm:table-cell">server</th>
            <th className="text-left px-4 py-2 font-mono font-normal text-muted">status</th>
            <th className="text-right px-4 py-2 font-mono font-normal text-muted hidden sm:table-cell">latency</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td className="px-4 py-3 font-mono text-secondary">claude-local</td>
            <td className="px-4 py-3 font-mono" style={{ color: T.accent }}>read_file</td>
            <td className="px-4 py-3 font-mono text-muted hidden sm:table-cell">filesystem</td>
            <td className="px-4 py-3">
              <span className="inline-flex items-center px-1.5 py-0.5 rounded border text-[10px] font-mono font-medium"
                style={{ color: '#34D399', background: 'rgba(52,211,153,0.10)', borderColor: 'rgba(52,211,153,0.20)' }}>
                ALLOWED
              </span>
            </td>
            <td className="px-4 py-3 font-mono text-muted text-right hidden sm:table-cell">12ms</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}

function renderStepContent(index: number): React.ReactNode {
  switch (index) {
    case 0: return <CodePanel lines={REGISTER_LINES} />
    case 1: return <StepPermissions />
    case 2: return <CodePanel lines={PROXY_LINES} />
    case 3: return <StepTrace />
    default: return null
  }
}

// ── Step definitions ──────────────────────────────────────────────────────────

const STEPS = [
  { id: 'register',    label: 'Register agent',  description: 'One CLI command. Get a scoped API key.'    },
  { id: 'permissions', label: 'Set permissions', description: 'Grant only the tools each agent needs.'    },
  { id: 'proxy',       label: 'Proxy a call',    description: 'Point your MCP client at Arbiter.'         },
  { id: 'trace',       label: 'View the trace',  description: 'Every call logged with full context.'      },
]

const ADVANCE_INTERVAL = 4000

// ── Main component ────────────────────────────────────────────────────────────

export default function FeatureShowcase(): React.ReactElement {
  const [activeStep, setActiveStep] = useState(0)
  const [isHovered,  setIsHovered]  = useState(false)
  const [spineDrawn, setSpineDrawn] = useState(false)
  const [openMobile, setOpenMobile] = useState<number | null>(0)
  const [resetKey,   setResetKey]   = useState(0)

  const sectionRef = useRef<HTMLElement>(null)
  const headingRef = useScrollReveal<HTMLHeadingElement>({ threshold: 0.2 })

  // Spine draw on section entry
  useEffect(() => {
    const el = sectionRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setSpineDrawn(true); observer.disconnect() } },
      { threshold: 0.15 }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  // Auto-advance — restarts when resetKey changes (manual step click)
  useEffect(() => {
    if (isHovered) return
    const timer = setInterval(() => {
      setActiveStep(s => (s + 1) % STEPS.length)
    }, ADVANCE_INTERVAL)
    return () => clearInterval(timer)
  }, [isHovered, resetKey])

  // Pause when tab is hidden
  useEffect(() => {
    function onVisChange() { setIsHovered(document.visibilityState !== 'visible') }
    document.addEventListener('visibilitychange', onVisChange)
    return () => document.removeEventListener('visibilitychange', onVisChange)
  }, [])

  function goTo(i: number) {
    setActiveStep(i)
    setResetKey(k => k + 1)
  }

  return (
    <section ref={sectionRef} className="py-24 px-6 bg-surface/30">
      <div className="max-w-5xl mx-auto">

        <h2
          ref={headingRef}
          className="font-display text-3xl font-semibold tracking-tight text-primary text-center mb-14"
          style={{ textWrap: 'balance' } as React.CSSProperties}
        >
          Up and running in four steps.
        </h2>

        {/* ── Desktop stepper ── */}
        <div
          className="hidden md:flex gap-14 items-start"
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
        >
          {/* Stepper column */}
          <div className="flex-shrink-0 w-52">
            {STEPS.map((step, i) => (
              <div key={step.id} className="flex gap-3">
                {/* Dot + segment */}
                <div className="flex flex-col items-center" style={{ width: '8px' }}>
                  <button
                    onClick={() => goTo(i)}
                    aria-label={`Go to: ${step.label}`}
                    className="flex-shrink-0 rounded-full transition-all duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
                    style={{
                      width: '8px',
                      height: '8px',
                      marginTop: '4px',
                      background: activeStep === i ? 'var(--color-accent)' : 'transparent',
                      border: activeStep === i ? 'none' : '1.5px solid rgba(61,53,206,0.40)',
                      boxShadow: activeStep === i ? '0 0 8px rgba(61,53,206,0.50)' : 'none',
                    }}
                  />
                  {i < STEPS.length - 1 && (
                    <div
                      className="w-px flex-1 mt-1"
                      style={{
                        minHeight: '56px',
                        background: 'rgba(61,53,206,0.28)',
                        transformOrigin: 'top',
                        transform: spineDrawn ? 'scaleY(1)' : 'scaleY(0)',
                        transition: `transform 500ms cubic-bezier(0.16,1,0.3,1) ${i * 110}ms`,
                      }}
                    />
                  )}
                </div>

                {/* Label */}
                <button
                  onClick={() => goTo(i)}
                  className={`text-left group ${i < STEPS.length - 1 ? 'pb-8' : ''}`}
                  style={{ marginLeft: '10px' }}
                >
                  <p className={`font-display text-sm font-semibold transition-colors duration-200 ${
                    activeStep === i ? 'text-primary' : 'text-secondary group-hover:text-primary'
                  }`}>
                    {step.label}
                  </p>
                  <p className={`text-xs mt-0.5 leading-relaxed transition-colors duration-200 ${
                    activeStep === i ? 'text-secondary' : 'text-muted'
                  }`}>
                    {step.description}
                  </p>
                </button>
              </div>
            ))}
          </div>

          {/* Content panel */}
          <div className="flex-1 min-w-0" style={{ minHeight: '260px' }}>
            <div key={activeStep} className="panel-enter">
              {renderStepContent(activeStep)}
            </div>
          </div>
        </div>

        {/* ── Mobile accordion ── */}
        <div className="md:hidden space-y-2">
          {STEPS.map((step, i) => {
            const isOpen = openMobile === i
            return (
              <div
                key={step.id}
                className="border border-border rounded-xl overflow-hidden transition-colors duration-200"
                style={{ background: isOpen ? 'var(--color-elevated)' : 'transparent' }}
              >
                <button
                  className="w-full flex items-center justify-between px-4 py-3.5 text-left gap-3"
                  onClick={() => setOpenMobile(isOpen ? null : i)}
                  aria-expanded={isOpen}
                  aria-controls={`step-panel-${step.id}`}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className="w-2 h-2 rounded-full flex-shrink-0 transition-all duration-200"
                      style={{
                        background: isOpen ? 'var(--color-accent)' : 'transparent',
                        border: isOpen ? 'none' : '1.5px solid rgba(61,53,206,0.40)',
                        boxShadow: isOpen ? '0 0 8px rgba(61,53,206,0.50)' : 'none',
                      }}
                    />
                    <span className={`font-display text-sm font-semibold transition-colors duration-200 ${
                      isOpen ? 'text-primary' : 'text-secondary'
                    }`}>
                      {step.label}
                    </span>
                  </div>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" strokeWidth="2" aria-hidden
                    className={`text-secondary flex-shrink-0 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}>
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>
                {isOpen && (
                  <div id={`step-panel-${step.id}`} className="px-4 pb-4" role="region" aria-label={step.label}>
                    {renderStepContent(i)}
                  </div>
                )}
              </div>
            )
          })}
        </div>

      </div>
    </section>
  )
}
