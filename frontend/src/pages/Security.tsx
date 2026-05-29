/**
 * Arbiter — Security page.
 *
 * Route: /security (public, no auth required)
 * Covers: Responsible Disclosure Policy, Security Practices, SLA/Uptime
 */

import React from 'react'
import { Link } from 'react-router-dom'
import { ArbiterMark } from '../components/ArbiterLogo'

// ── Navbar ─────────────────────────────────────────────────────────────────────

function Navbar(): React.ReactElement {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-base/85 backdrop-blur-md border-b border-border">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5">
          <ArbiterMark size={26} />
          <span className="font-display text-primary font-semibold text-sm tracking-tight">Arbiter</span>
        </Link>
        <div className="flex items-center gap-3">
          <Link
            to="/login"
            className="text-secondary hover:text-primary border border-border hover:border-border-strong px-4 py-1.5 rounded-lg text-sm transition-colors duration-150"
          >
            Sign In
          </Link>
          <Link
            to="/register"
            className="bg-accent hover:bg-accent-light text-white text-sm font-semibold px-4 py-1.5 rounded-lg transition-colors duration-150"
          >
            Get Started
          </Link>
        </div>
      </div>
    </nav>
  )
}

// ── Prose helpers ──────────────────────────────────────────────────────────────

function H2({ children }: { children: React.ReactNode }): React.ReactElement {
  return (
    <h2 className="font-display text-lg font-semibold text-primary mt-10 mb-3 tracking-tight">
      {children}
    </h2>
  )
}

function H3({ children }: { children: React.ReactNode }): React.ReactElement {
  return (
    <h3 className="font-display text-base font-semibold text-primary mt-6 mb-2 tracking-tight">
      {children}
    </h3>
  )
}

function P({ children }: { children: React.ReactNode }): React.ReactElement {
  return <p className="text-secondary text-sm leading-relaxed mb-3">{children}</p>
}

function UL({ children }: { children: React.ReactNode }): React.ReactElement {
  return <ul className="list-disc list-outside pl-5 space-y-1 text-secondary text-sm leading-relaxed mb-3">{children}</ul>
}

function LI({ children }: { children: React.ReactNode }): React.ReactElement {
  return <li>{children}</li>
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function Security(): React.ReactElement {
  return (
    <div className="min-h-screen bg-base text-primary">
      <Navbar />

      <main className="pt-20 pb-20 px-6">
        <div className="max-w-3xl mx-auto">
          {/* Header */}
          <div className="mb-8 pt-8 border-b border-border pb-6">
            <p className="text-muted text-xs font-mono uppercase tracking-widest mb-2">Trust & Safety</p>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-primary mb-2">
              Security
            </h1>
            <p className="text-secondary text-sm">
              <span className="font-medium">Last updated:</span> May 28, 2026
            </p>
          </div>

          {/* ── Responsible Disclosure ───────────────────────────────────────── */}
          <H2>Responsible Disclosure Policy</H2>
          <P>
            We take security seriously. If you believe you have found a security vulnerability in Arbiter,
            we encourage you to report it to us responsibly. We are committed to working with the security
            research community to verify, reproduce, and address any discovered vulnerabilities.
          </P>

          <H3>How to report</H3>
          <P>
            Email your findings to{' '}
            <a href="mailto:security@arbiterai.dev" className="text-accent-light hover:text-primary transition-colors">
              security@arbiterai.dev
            </a>
            . Please include a clear description of the vulnerability, steps to reproduce, and your
            assessment of the potential impact. PGP encryption is not required but is welcome if you
            prefer it.
          </P>

          <H3>Our commitments</H3>
          <UL>
            <LI>
              <strong className="text-primary">Acknowledgment within 48 hours:</strong> We will confirm receipt
              of your report and provide an initial assessment.
            </LI>
            <LI>
              <strong className="text-primary">Critical fixes within 7 days:</strong> Vulnerabilities assessed
              as critical severity will be patched within 7 calendar days of confirmation.
            </LI>
            <LI>
              <strong className="text-primary">Safe harbor:</strong> Researchers acting in good faith under this
              policy will not face legal action from Arbiter. We will not pursue civil or criminal action
              against you for security testing that stays within the scope defined below.
            </LI>
            <LI>
              <strong className="text-primary">Credit:</strong> With your permission, we will publicly acknowledge
              your contribution once the vulnerability is resolved.
            </LI>
          </UL>

          <H3>In scope</H3>
          <UL>
            <LI>Authentication and session management flaws</LI>
            <LI>Authorization bypasses and privilege escalation</LI>
            <LI>Secrets vault exposure or cross-tenant data leaks</LI>
            <LI>Injection vulnerabilities (SQL, command, etc.)</LI>
            <LI>Insecure direct object reference (IDOR) on API endpoints</LI>
            <LI>Significant information disclosure vulnerabilities</LI>
          </UL>

          <H3>Out of scope</H3>
          <UL>
            <LI>Denial-of-service (DoS/DDoS) attacks</LI>
            <LI>Social engineering or phishing attacks targeting Arbiter staff</LI>
            <LI>Physical attacks against infrastructure</LI>
            <LI>Vulnerabilities in third-party services we depend on (report those to the respective vendor)</LI>
            <LI>Automated scanning without prior coordination</LI>
            <LI>Issues that require physical access to a user's device</LI>
          </UL>

          {/* ── Security Practices ───────────────────────────────────────────── */}
          <H2>Security Practices</H2>
          <P>
            We apply security controls throughout the Arbiter stack. Below is a summary of the measures
            in place.
          </P>

          <H3>Secrets and encryption</H3>
          <UL>
            <LI>
              <strong className="text-primary">AES-256-GCM vault encryption:</strong> All secrets stored in
              the Arbiter vault are encrypted at rest using AES-256-GCM with a unique IV per secret.
              Secrets are decrypted in memory only at the moment of injection into a proxy call and are
              never persisted in plaintext.
            </LI>
            <LI>
              <strong className="text-primary">Agent API keys:</strong> Each agent is issued a unique API key
              with an <code className="text-teal-light font-mono text-xs">nxai_</code> prefix. We store only
              a SHA-256 hash of the key — the full value is shown once at creation and never retrievable again.
              Keys are never shared across agents or organizations.
            </LI>
            <LI>
              <strong className="text-primary">TLS in transit:</strong> All communication between clients,
              the Arbiter API, and MCP servers is encrypted in transit using TLS 1.2+.
            </LI>
          </UL>

          <H3>Authentication</H3>
          <UL>
            <LI>
              <strong className="text-primary">JWT with 60-minute TTL:</strong> Access tokens expire after
              60 minutes. A refresh token flow is used to issue new access tokens without requiring
              re-authentication.
            </LI>
            <LI>
              <strong className="text-primary">Email verification:</strong> New accounts require email
              verification before proxy access is granted.
            </LI>
            <LI>
              <strong className="text-primary">OAuth providers:</strong> Google and GitHub OAuth are
              supported. OAuth tokens are never stored in plaintext.
            </LI>
            <LI>
              <strong className="text-primary">Rate limiting:</strong> Authentication endpoints are rate-limited
              to mitigate brute-force and credential-stuffing attacks.
            </LI>
          </UL>

          <H3>Access control</H3>
          <UL>
            <LI>
              <strong className="text-primary">Role-based access control (RBAC):</strong> Organizations have
              owner, admin, and member roles. Write operations on agents, permissions, and servers require
              at minimum admin role.
            </LI>
            <LI>
              <strong className="text-primary">Tool-level permissions:</strong> Each agent has explicit
              allow-listed tool permissions. A tool call is rejected at the gateway if the calling agent
              has not been granted that specific tool.
            </LI>
            <LI>
              <strong className="text-primary">Tenant isolation:</strong> All data queries are scoped to
              the authenticated organization. Cross-organization data access is not possible through the
              API.
            </LI>
          </UL>

          <H3>Infrastructure</H3>
          <UL>
            <LI>
              <strong className="text-primary">Railway (SOC 2 Type II):</strong> The Arbiter backend is
              deployed on Railway, which maintains SOC 2 Type II certification. See{' '}
              <a
                href="https://railway.app/security"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent-light hover:text-primary transition-colors"
              >
                railway.app/security
              </a>{' '}
              for their security documentation.
            </LI>
            <LI>
              <strong className="text-primary">Audit logging:</strong> All tool calls, permission changes,
              and administrative actions are logged with agent identity, timestamp, and outcome.
            </LI>
          </UL>

          {/* ── SLA / Uptime ─────────────────────────────────────────────────── */}
          <H2>Service Level &amp; Uptime</H2>
          <P>
            We are committed to keeping the Arbiter proxy gateway reliable for production workloads.
          </P>
          <UL>
            <LI>
              <strong className="text-primary">Uptime target:</strong> We target 99.5% monthly uptime for
              the proxy gateway.
            </LI>
            <LI>
              <strong className="text-primary">Planned maintenance:</strong> Scheduled downtime will be
              announced at least 24 hours in advance via our status page (status page coming soon).
            </LI>
            <LI>
              <strong className="text-primary">Free tier:</strong> No SLA guarantees are provided on the
              Free tier. Best-effort availability applies.
            </LI>
            <LI>
              <strong className="text-primary">Pro tier:</strong> Commercially reasonable uptime efforts
              apply. No financial SLA credits are offered at this time. Enterprise customers may negotiate
              a custom SLA — contact{' '}
              <a href="mailto:support@arbiterai.dev" className="text-accent-light hover:text-primary transition-colors">
                support@arbiterai.dev
              </a>
              .
            </LI>
          </UL>

          {/* Contact box */}
          <div className="mt-10 bg-surface border border-border rounded-xl p-5 text-sm text-secondary">
            <p className="font-semibold text-primary mb-1">Security Contact</p>
            <p>
              Email:{' '}
              <a href="mailto:security@arbiterai.dev" className="text-accent-light hover:text-primary transition-colors">
                security@arbiterai.dev
              </a>
            </p>
            <p className="mt-1 text-xs text-muted">
              For general support enquiries, use{' '}
              <a href="mailto:support@arbiterai.dev" className="hover:text-secondary transition-colors">
                support@arbiterai.dev
              </a>
              .
            </p>
          </div>

          {/* Footer links */}
          <div className="mt-12 pt-6 border-t border-border flex items-center gap-4 text-xs text-muted">
            <Link to="/privacy" className="hover:text-secondary transition-colors">Privacy Policy</Link>
            <span>·</span>
            <Link to="/terms" className="hover:text-secondary transition-colors">Terms of Service</Link>
            <span>·</span>
            <Link to="/changelog" className="hover:text-secondary transition-colors">Changelog</Link>
            <span>·</span>
            <Link to="/" className="hover:text-secondary transition-colors">Back to Arbiter</Link>
          </div>
        </div>
      </main>
    </div>
  )
}
