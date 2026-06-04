import React from 'react'

const ROWS = [
  { agent: 'claude-local',  tool: 'read_file',   server: 'filesystem', status: 'ALLOWED', latency: '12ms'  },
  { agent: 'agt-prod-001',  tool: 'query',        server: 'postgres',   status: 'CACHED',  latency: '0ms'   },
  { agent: 'agt-dev-042',   tool: 'list_prs',     server: 'github',     status: 'ALLOWED', latency: '84ms'  },
  { agent: 'agt-prod-001',  tool: 'write_file',   server: 'filesystem', status: 'BLOCKED', latency: '2ms'   },
  { agent: 'claude-local',  tool: 'create_issue', server: 'github',     status: 'ALLOWED', latency: '110ms' },
]

const STATUS_STYLES: Record<string, string> = {
  ALLOWED: 'bg-[rgba(52,211,153,0.10)] text-[#34D399] border-[rgba(52,211,153,0.20)]',
  CACHED:  'bg-[rgba(6,182,212,0.10)]  text-[#22D3EE] border-[rgba(6,182,212,0.20)]',
  BLOCKED: 'bg-[rgba(248,113,113,0.10)] text-[#F87171] border-[rgba(248,113,113,0.20)]',
}

function StatusBadge({ status }: { status: string }): React.ReactElement {
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded border text-[10px] font-mono font-medium leading-none ${STATUS_STYLES[status] ?? ''}`}>
      {status}
    </span>
  )
}

export default function DashboardPreview(): React.ReactElement {
  return (
    <section className="py-24 px-6">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-14">
          <h2 className="font-display text-3xl font-semibold tracking-tight text-primary mb-3">
            Full observability, from day one
          </h2>
          <p className="text-secondary text-base max-w-lg mx-auto leading-relaxed">
            Every tool call surfaces in Mission Control: the agent, the tool, the server, the result,
            and whether it was served from cache or blocked by a permission rule.
          </p>
        </div>

        {/* Floating dashboard mock */}
        <div
          className="relative mx-auto animate-float"
          style={{
            borderRadius: '14px',
            boxShadow: [
              '0 0 0 1px rgba(61,53,206,0.32)',
              '0 0 40px rgba(61,53,206,0.14)',
              '0 0 80px rgba(61,53,206,0.07)',
              '0 32px 80px rgba(0,0,0,0.45)',
            ].join(', '),
            background: 'var(--color-surface)',
          }}
        >
          {/* Window chrome */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full" style={{ background: 'rgba(248,113,113,0.50)' }} />
              <span className="w-3 h-3 rounded-full" style={{ background: 'rgba(251,191,36,0.50)' }} />
              <span className="w-3 h-3 rounded-full" style={{ background: 'rgba(52,211,153,0.50)' }} />
            </div>
            <span className="font-mono text-xs text-muted">Mission Control — Arbiter</span>
            {/* Live indicator */}
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-success" style={{ animation: 'blink-cursor 1.8s step-end infinite' }} />
              <span className="font-mono text-xs text-muted">live</span>
            </div>
          </div>

          {/* Metrics strip */}
          <div className="grid grid-cols-3 divide-x border-b" style={{ borderColor: 'var(--color-border)', '--tw-divide-opacity': '1' } as React.CSSProperties}>
            <div className="px-5 py-4">
              <p className="font-mono text-xs text-muted mb-1">tool_calls_today</p>
              <p className="font-display font-semibold text-2xl text-primary">1,247</p>
            </div>
            <div className="px-5 py-4">
              <p className="font-mono text-xs text-muted mb-1">cache_rate</p>
              <p className="font-display font-semibold text-2xl text-teal-light">34%</p>
            </div>
            <div className="px-5 py-4">
              <p className="font-mono text-xs text-muted mb-1">blocked</p>
              <p className="font-display font-semibold text-2xl text-error">3</p>
            </div>
          </div>

          {/* Tool call table */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left px-5 py-2.5 font-mono font-normal text-muted">agent</th>
                  <th className="text-left px-4 py-2.5 font-mono font-normal text-muted">tool</th>
                  <th className="text-left px-4 py-2.5 font-mono font-normal text-muted hidden sm:table-cell">server</th>
                  <th className="text-left px-4 py-2.5 font-mono font-normal text-muted">status</th>
                  <th className="text-right px-5 py-2.5 font-mono font-normal text-muted hidden sm:table-cell">latency</th>
                </tr>
              </thead>
              <tbody>
                {ROWS.map((row, i) => (
                  <tr
                    key={i}
                    className="border-b border-border last:border-0 transition-colors duration-150"
                    style={{ background: i % 2 === 0 ? 'rgba(255,255,255,0.012)' : 'transparent' }}
                  >
                    <td className="px-5 py-2.5 font-mono text-secondary">{row.agent}</td>
                    <td className="px-4 py-2.5 font-mono" style={{ color: 'var(--color-accent-light)' }}>{row.tool}</td>
                    <td className="px-4 py-2.5 font-mono text-muted hidden sm:table-cell">{row.server}</td>
                    <td className="px-4 py-2.5"><StatusBadge status={row.status} /></td>
                    <td className="px-5 py-2.5 font-mono text-muted text-right hidden sm:table-cell">{row.latency}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  )
}
