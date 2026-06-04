import React from 'react'

const SERVERS = [
  { y: 20,  label: 'filesystem', sub: 'read_file · write_file' },
  { y: 83,  label: 'github',     sub: 'list_prs · create_issue' },
  { y: 146, label: 'postgres',   sub: 'query · execute' },
]

export default function HeroArchDiagram(): React.ReactElement {
  return (
    <section className="py-20 px-6">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-primary mb-3">
            Every tool call flows through Arbiter
          </h2>
          <p className="text-secondary text-sm max-w-md mx-auto leading-relaxed">
            Agents connect to one gateway. Arbiter handles routing, access control, caching,
            and logging to every MCP server behind it.
          </p>
        </div>

        <div className="overflow-x-auto">
          <div style={{ minWidth: '520px' }}>
            <svg
              viewBox="0 0 650 215"
              xmlns="http://www.w3.org/2000/svg"
              role="img"
              aria-label="Architecture flow: AI Agent sends requests through Arbiter Gateway, which proxies to filesystem, github, and postgres MCP servers"
              className="w-full"
              style={{ maxHeight: '260px' }}
            >
              <defs>
                {/* Indigo glow filter for Arbiter */}
                <filter id="diag-glow" x="-40%" y="-40%" width="180%" height="180%">
                  <feGaussianBlur stdDeviation="6" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>

                {/* Path refs for animateMotion */}
                <path id="p-in"  d="M 168 108 H 242"    fill="none" />
                <path id="p-s1"  d="M 392 86 L 462 45"  fill="none" />
                <path id="p-s2"  d="M 392 108 H 462"    fill="none" />
                <path id="p-s3"  d="M 392 131 L 462 171" fill="none" />
              </defs>

              {/* ── Edge lines ── */}
              <line x1="168" y1="108" x2="242" y2="108"
                stroke="rgba(82,73,217,0.40)" strokeWidth="1.5" strokeDasharray="5 3" />
              <line x1="392" y1="86"  x2="462" y2="45"
                stroke="rgba(6,182,212,0.30)" strokeWidth="1.5" strokeDasharray="5 3" />
              <line x1="392" y1="108" x2="462" y2="108"
                stroke="rgba(6,182,212,0.30)" strokeWidth="1.5" strokeDasharray="5 3" />
              <line x1="392" y1="131" x2="462" y2="171"
                stroke="rgba(6,182,212,0.30)" strokeWidth="1.5" strokeDasharray="5 3" />

              {/* ── Traveling packets ── */}
              {/* Inbound: Agent → Arbiter (indigo — identity-authenticated) */}
              <circle r="3.5" fill="#3D35CE">
                <animateMotion dur="1.8s" repeatCount="indefinite" begin="0s">
                  <mpath href="#p-in" />
                </animateMotion>
              </circle>
              <circle r="2.5" fill="#5249D9" opacity="0.55">
                <animateMotion dur="1.8s" repeatCount="indefinite" begin="-0.9s">
                  <mpath href="#p-in" />
                </animateMotion>
              </circle>
              {/* Outbound: Arbiter → Servers (cyan — proxied data) */}
              <circle r="3" fill="#06B6D4" opacity="0.90">
                <animateMotion dur="1.2s" repeatCount="indefinite" begin="0.2s">
                  <mpath href="#p-s1" />
                </animateMotion>
              </circle>
              <circle r="3" fill="#06B6D4" opacity="0.90">
                <animateMotion dur="1.2s" repeatCount="indefinite" begin="0.8s">
                  <mpath href="#p-s2" />
                </animateMotion>
              </circle>
              <circle r="3" fill="#06B6D4" opacity="0.90">
                <animateMotion dur="1.2s" repeatCount="indefinite" begin="1.4s">
                  <mpath href="#p-s3" />
                </animateMotion>
              </circle>

              {/* ── AI Agent node ── */}
              <rect x="18" y="78" width="150" height="60" rx="9"
                fill="#0F0F12" stroke="rgba(255,255,255,0.09)" strokeWidth="1" />
              <circle cx="42" cy="108" r="12"
                fill="rgba(61,53,206,0.10)" stroke="rgba(61,53,206,0.28)" strokeWidth="1" />
              {/* Simple agent icon — nested diamond */}
              <rect x="36" y="102" width="12" height="12" rx="2"
                fill="none" stroke="rgba(82,73,217,0.65)" strokeWidth="1.5" />
              <text x="62" y="105" fontSize="11" fontFamily="Geist, Inter, sans-serif"
                fontWeight="600" fill="#FAFAFA">AI Agent</text>
              <text x="62" y="119" fontSize="9" fontFamily="ui-monospace, monospace"
                fill="#52525B">nxai_k7x2m...</text>

              {/* ── Arbiter Gateway node (center, prominent) ── */}
              {/* Animated glow backdrop */}
              <rect x="242" y="63" width="150" height="90" rx="11" fill="rgba(61,53,206,0.06)">
                <animate attributeName="fill"
                  values="rgba(61,53,206,0.04);rgba(61,53,206,0.16);rgba(61,53,206,0.04)"
                  dur="2.8s" repeatCount="indefinite" />
              </rect>
              {/* Main box */}
              <rect x="242" y="63" width="150" height="90" rx="11"
                fill="#0F0F12"
                stroke="rgba(61,53,206,0.55)"
                strokeWidth="1.5"
                filter="url(#diag-glow)"
              />
              {/* MCP GATEWAY badge */}
              <rect x="258" y="73" width="92" height="15" rx="7"
                fill="rgba(61,53,206,0.18)" stroke="rgba(82,73,217,0.38)" strokeWidth="0.75" />
              <text x="304" y="83.5" fontSize="7.5" fontFamily="ui-monospace, monospace"
                fontWeight="500" fill="rgba(130,120,255,0.85)" textAnchor="middle" letterSpacing="0.07em">
                MCP GATEWAY
              </text>
              {/* Name */}
              <text x="317" y="105" fontSize="14.5" fontFamily="Geist, Inter, sans-serif"
                fontWeight="700" fill="#FAFAFA" textAnchor="middle">
                Arbiter
              </text>
              {/* Capabilities line */}
              <text x="317" y="120" fontSize="9" fontFamily="Inter, sans-serif"
                fill="#3F3F46" textAnchor="middle">
                auth · cache · log · vault
              </text>
              {/* Live status dot */}
              <circle cx="374" cy="76" r="3.5" fill="#34D399">
                <animate attributeName="opacity" values="1;0.35;1" dur="2.2s" repeatCount="indefinite" />
              </circle>

              {/* ── MCP Server nodes ── */}
              {SERVERS.map(({ y, label, sub }) => (
                <g key={label}>
                  <rect x="462" y={y} width="170" height="50" rx="8"
                    fill="#0F0F12" stroke="rgba(255,255,255,0.07)" strokeWidth="1" />
                  <circle cx="481" cy={y + 25} r="5"
                    fill="rgba(6,182,212,0.10)" stroke="rgba(6,182,212,0.38)" strokeWidth="1" />
                  <text x="496" y={y + 21} fontSize="11" fontFamily="Inter, sans-serif"
                    fontWeight="500" fill="#FAFAFA">{label}</text>
                  <text x="496" y={y + 35} fontSize="9" fontFamily="ui-monospace, monospace"
                    fill="#3F3F46">{sub}</text>
                </g>
              ))}
            </svg>
          </div>
        </div>
      </div>
    </section>
  )
}
