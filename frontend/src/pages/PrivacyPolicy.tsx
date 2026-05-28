/**
 * Arbiter — Privacy Policy page.
 *
 * Route: /privacy (public, no auth required)
 * Content sourced from legal research (research-legal.md) — May 28, 2026.
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

// ── Legal prose helpers ────────────────────────────────────────────────────────

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

// ── Table component ────────────────────────────────────────────────────────────

function LegalTable({ headers, rows }: { headers: string[]; rows: string[][] }): React.ReactElement {
  return (
    <div className="overflow-x-auto mb-4">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b border-border-strong">
            {headers.map((h) => (
              <th key={h} className="text-left py-2 pr-4 text-xs font-semibold text-secondary uppercase tracking-widest">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-border">
              {row.map((cell, j) => (
                <td key={j} className="py-2.5 pr-4 text-secondary text-sm align-top">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function PrivacyPolicy(): React.ReactElement {
  return (
    <div className="min-h-screen bg-base text-primary">
      <Navbar />

      <main className="pt-20 pb-20 px-6">
        <div className="max-w-3xl mx-auto">
          {/* Header */}
          <div className="mb-8 pt-8 border-b border-border pb-6">
            <p className="text-muted text-xs font-mono uppercase tracking-widest mb-2">Legal</p>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-primary mb-2">
              Privacy Policy
            </h1>
            <p className="text-secondary text-sm">
              <span className="font-medium">Last updated:</span> May 28, 2026
            </p>
          </div>

          {/* Intro */}
          <P>
            This Privacy Policy describes how ArbiterAI ("Arbiter," "we," "us," or "our"), operated by Jaiden Sy, collects, uses, and discloses information about you when you use our website at{' '}
            <a href="https://arbiterai.dev" className="text-accent-light hover:text-primary transition-colors">arbiterai.dev</a>{' '}
            and our software-as-a-service platform (collectively, the "Service").
          </P>
          <P>
            <strong className="text-primary">Contact:</strong> For privacy-related questions or to exercise your rights, email us at{' '}
            <a href="mailto:privacy@arbiterai.dev" className="text-accent-light hover:text-primary transition-colors">privacy@arbiterai.dev</a>.
          </P>

          {/* 1. Information We Collect */}
          <H2>1. Information We Collect</H2>

          <H3>Information you provide directly:</H3>
          <UL>
            <LI><strong className="text-primary">Account information:</strong> email address, name, and password (stored as a bcrypt hash) when you register.</LI>
            <LI><strong className="text-primary">OAuth profile data:</strong> if you sign up via Google or GitHub, we receive your name, email address, and OAuth provider user ID.</LI>
            <LI><strong className="text-primary">Vault secrets:</strong> API keys, tokens, and credentials you choose to store in the Arbiter secrets vault. These are encrypted at rest using AES-256-GCM encryption. We never transmit vault secrets in plaintext outside of the proxy pipeline.</LI>
            <LI><strong className="text-primary">MCP server configurations:</strong> URLs, authentication metadata, and tool permission settings you configure.</LI>
            <LI><strong className="text-primary">Support communications:</strong> any information you provide when you contact us.</LI>
          </UL>

          <H3>Information collected automatically:</H3>
          <UL>
            <LI><strong className="text-primary">Agent API keys:</strong> when you create an AI agent in Arbiter, we generate a unique API key (<code className="text-teal-light font-mono text-xs">nxai_</code> prefix). We store only a SHA-256 hash of this key — the full key is shown to you once at creation.</LI>
            <LI><strong className="text-primary">Session events and audit logs:</strong> for each tool call routed through Arbiter, we log: the tool name, the MCP server used, the AI agent that made the call, request timestamp, response time, cache hit/miss status, and success/failure outcome. We also log the tool call parameters and response payload for session trace functionality. These logs may contain data you introduce into tool call payloads.</LI>
            <LI><strong className="text-primary">Semantic cache data:</strong> tool call parameters and responses may be stored in our caching layer (Redis and PostgreSQL) to optimize performance. Cache entries expire per the TTL you configure.</LI>
            <LI><strong className="text-primary">Usage metrics:</strong> tool call counts, plan tier usage, quota consumption.</LI>
            <LI><strong className="text-primary">IP addresses:</strong> collected in server access logs and retained for 90 days, then anonymized.</LI>
            <LI><strong className="text-primary">Technical data:</strong> browser type, operating system, referrer URL, and page interaction data for operational purposes.</LI>
          </UL>

          <H3>Information from third parties:</H3>
          <UL>
            <LI><strong className="text-primary">Stripe:</strong> when you subscribe, Stripe provides us with a customer ID, subscription status, and masked payment method information (last four digits, card brand, billing name). Stripe processes your full payment card data directly; we never receive or store raw card numbers. See Stripe's Privacy Policy at <a href="https://stripe.com/privacy" className="text-accent-light hover:text-primary transition-colors" target="_blank" rel="noopener noreferrer">stripe.com/privacy</a>.</LI>
          </UL>

          {/* 2. How We Use Your Information */}
          <H2>2. How We Use Your Information</H2>
          <P>We use information we collect to:</P>
          <LegalTable
            headers={['Purpose', 'Legal Basis (GDPR)']}
            rows={[
              ['Provide, operate, and maintain the Service', 'Contract (Art. 6(1)(b))'],
              ['Process payments and manage subscriptions', 'Contract + Legal obligation (Art. 6(1)(b)(c))'],
              ['Authenticate users and verify agent identity', 'Contract (Art. 6(1)(b))'],
              ['Route tool calls through the proxy pipeline', 'Contract (Art. 6(1)(b))'],
              ['Store and retrieve vault secrets on your behalf', 'Contract (Art. 6(1)(b))'],
              ['Enforce RBAC permissions', 'Contract (Art. 6(1)(b))'],
              ['Maintain session audit logs and traces', 'Legitimate interests — security, debugging (Art. 6(1)(f))'],
              ['Detect and prevent fraud, abuse, and security threats', 'Legitimate interests (Art. 6(1)(f))'],
              ['Comply with legal obligations', 'Legal obligation (Art. 6(1)(c))'],
              ['Send transactional communications (receipts, alerts)', 'Contract (Art. 6(1)(b))'],
              ['Improve the Service through aggregate analytics', 'Legitimate interests (Art. 6(1)(f))'],
            ]}
          />
          <P>
            We do <strong className="text-primary">not</strong> sell, rent, or share your personal information with third parties for their own marketing purposes.
          </P>

          {/* 3. How We Share Your Information */}
          <H2>3. How We Share Your Information</H2>
          <P>We share your information only in the following circumstances:</P>
          <UL>
            <LI><strong className="text-primary">Service providers:</strong> we share information with vendors who help operate the Service: Railway (cloud infrastructure), Vercel (frontend hosting), Stripe (payment processing), and any transactional email provider we use. Each is bound by data processing agreements and is authorized to use your information only as needed to provide services to us.</LI>
            <LI><strong className="text-primary">MCP servers you connect:</strong> when you configure an MCP server and grant an agent permission to call its tools, your agent's tool call requests are proxied to that server. The content of those requests is your responsibility.</LI>
            <LI><strong className="text-primary">Legal compliance:</strong> we may disclose information if required by law, court order, or governmental authority, or if we believe in good faith that disclosure is necessary to protect our rights, your safety, or the safety of others.</LI>
            <LI><strong className="text-primary">Business transfers:</strong> if Arbiter is acquired or merges with another entity, your information may be transferred as part of that transaction. We will notify you before your information is subject to a different privacy policy.</LI>
            <LI><strong className="text-primary">With your consent:</strong> we will share information for any other purpose with your explicit consent.</LI>
          </UL>

          {/* 4. Data Retention */}
          <H2>4. Data Retention</H2>
          <P>We retain your information for as long as necessary to provide the Service and comply with our legal obligations:</P>
          <LegalTable
            headers={['Data Type', 'Retention Period']}
            rows={[
              ['Account data (email, name)', 'Duration of account + 30 days after deletion'],
              ['Vault secrets', 'Deleted immediately upon account deletion or manual removal'],
              ['Session events and audit logs', '12 months from creation'],
              ['Tool call cache entries', 'Per your configured TTL (default varies by server)'],
              ['IP addresses', '90 days, then anonymized'],
              ['Billing records', '7 years (tax and legal obligation)'],
              ['OAuth tokens', 'Until refreshed or account deleted'],
            ]}
          />
          <P>
            When you delete your account, we delete all personal data associated with your account within 30 days, except billing records which are anonymized (your email is removed; the transaction record is retained for tax compliance).
          </P>

          {/* 5. Your Privacy Rights */}
          <H2>5. Your Privacy Rights</H2>

          <H3>For users in the European Economic Area (EEA) and UK:</H3>
          <P>Under GDPR, you have the following rights:</P>
          <UL>
            <LI><strong className="text-primary">Access:</strong> request a copy of the personal data we hold about you.</LI>
            <LI><strong className="text-primary">Rectification:</strong> request correction of inaccurate data.</LI>
            <LI><strong className="text-primary">Erasure:</strong> request deletion of your personal data (see "Account Deletion" below).</LI>
            <LI><strong className="text-primary">Restriction:</strong> request that we limit processing of your data while a dispute is resolved.</LI>
            <LI><strong className="text-primary">Portability:</strong> receive your data in a machine-readable format.</LI>
            <LI><strong className="text-primary">Object:</strong> object to processing based on legitimate interests.</LI>
            <LI><strong className="text-primary">Withdraw consent:</strong> where processing is based on consent, withdraw it at any time.</LI>
            <LI><strong className="text-primary">Lodge a complaint:</strong> with your national data protection supervisory authority.</LI>
          </UL>

          <H3>For California residents (CCPA/CPRA):</H3>
          <UL>
            <LI><strong className="text-primary">Right to Know:</strong> request details about the categories and specific pieces of personal information we have collected.</LI>
            <LI><strong className="text-primary">Right to Delete:</strong> request deletion of your personal information.</LI>
            <LI><strong className="text-primary">Right to Correct:</strong> request correction of inaccurate personal information.</LI>
            <LI><strong className="text-primary">Right to Non-Discrimination:</strong> we will not discriminate against you for exercising these rights.</LI>
            <LI><strong className="text-primary">Do Not Sell or Share:</strong> we do not sell or share your personal information for targeted advertising purposes.</LI>
          </UL>

          <P>
            <strong className="text-primary">How to exercise your rights:</strong> Email{' '}
            <a href="mailto:privacy@arbiterai.dev" className="text-accent-light hover:text-primary transition-colors">privacy@arbiterai.dev</a>{' '}
            with your request. We will respond within 30 days. We may need to verify your identity before processing your request.
          </P>

          {/* 6. Account Deletion */}
          <H2>6. Account Deletion</H2>
          <P>You may delete your account at any time via the Settings page. Account deletion triggers:</P>
          <ol className="list-decimal list-outside pl-5 space-y-1 text-secondary text-sm leading-relaxed mb-3">
            <li>Immediate deactivation of your account and all associated agent API keys.</li>
            <li>Deletion of all vault secrets.</li>
            <li>Deletion of all MCP server configurations, agent records, and session data within 30 days.</li>
            <li>Anonymization of billing records (email removed; transaction records retained for legal compliance).</li>
          </ol>

          {/* 7. Security */}
          <H2>7. Security</H2>
          <P>We implement appropriate technical and organizational measures to protect your personal information:</P>
          <UL>
            <LI>AES-256-GCM encryption for vault secrets at rest</LI>
            <LI>TLS/HTTPS for all data in transit</LI>
            <LI>SHA-256 hashing of agent API keys (full key is never stored)</LI>
            <LI>RBAC enforcement before any vault decryption occurs</LI>
            <LI>Access controls and audit logging on all administrative operations</LI>
          </UL>
          <P>
            Despite these measures, no system is completely secure. If you discover a security vulnerability, please report it to{' '}
            <a href="mailto:security@arbiterai.dev" className="text-accent-light hover:text-primary transition-colors">security@arbiterai.dev</a>.
          </P>
          <P>
            In the event of a personal data breach that is likely to result in a risk to your rights and freedoms, we will notify the relevant supervisory authority within 72 hours of becoming aware of the breach, and we will notify affected users without undue delay.
          </P>

          {/* 8. International Data Transfers */}
          <H2>8. International Data Transfers</H2>
          <P>
            Arbiter is operated from the United States. If you are located in the EEA, UK, or other regions with data protection laws, your information may be transferred to and processed in the United States. We rely on Standard Contractual Clauses (SCCs) as the legal mechanism for such transfers where required. You may request a copy of the relevant SCCs by contacting{' '}
            <a href="mailto:privacy@arbiterai.dev" className="text-accent-light hover:text-primary transition-colors">privacy@arbiterai.dev</a>.
          </P>

          {/* 9. Cookies and Tracking */}
          <H2>9. Cookies and Tracking</H2>
          <P>Arbiter uses minimal tracking. We use:</P>
          <UL>
            <LI><strong className="text-primary">Functional storage:</strong> your authentication token is stored in browser localStorage (not a cookie) to maintain your session.</LI>
            <LI><strong className="text-primary">Analytics:</strong> if we use aggregate usage analytics tools, they do not receive personally identifiable information. We will update this section before enabling any such service.</LI>
          </UL>
          <P>If you are in the EU, we will request consent before setting any non-essential tracking.</P>

          {/* 10. Children's Privacy */}
          <H2>10. Children's Privacy</H2>
          <P>
            The Service is not directed to children under the age of 13. We do not knowingly collect personal information from children under 13. If we become aware that a user is under 13, we will immediately delete their account and all associated data. If you believe a child under 13 has provided us with personal information, please contact us at{' '}
            <a href="mailto:privacy@arbiterai.dev" className="text-accent-light hover:text-primary transition-colors">privacy@arbiterai.dev</a>.
          </P>

          {/* 11. Changes to This Policy */}
          <H2>11. Changes to This Policy</H2>
          <P>
            We may update this Privacy Policy from time to time. We will notify you of material changes by email (to the address on your account) and by updating the "Last updated" date at the top of this page. For EU users, material changes that affect how we process your personal data will require your affirmative re-consent.
          </P>

          {/* 12. Contact Us */}
          <H2>12. Contact Us</H2>
          <div className="bg-surface border border-border rounded-xl p-5 text-sm text-secondary">
            <p className="font-semibold text-primary mb-1">ArbiterAI / Jaiden Sy</p>
            <p>Email: <a href="mailto:privacy@arbiterai.dev" className="text-accent-light hover:text-primary transition-colors">privacy@arbiterai.dev</a></p>
            <p>California, United States</p>
            <p className="mt-2 text-xs text-muted">For EEA users: You have the right to contact your local data protection authority if you have concerns about how we process your data.</p>
          </div>

          {/* Footer links */}
          <div className="mt-12 pt-6 border-t border-border flex items-center gap-4 text-xs text-muted">
            <Link to="/terms" className="hover:text-secondary transition-colors">Terms of Service</Link>
            <span>·</span>
            <a href="mailto:support@arbiterai.dev" className="hover:text-secondary transition-colors">support@arbiterai.dev</a>
            <span>·</span>
            <Link to="/" className="hover:text-secondary transition-colors">Back to Arbiter</Link>
          </div>
        </div>
      </main>
    </div>
  )
}
