/**
 * Arbiter — Terms of Service page.
 *
 * Route: /terms (public, no auth required)
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

function P({ children }: { children: React.ReactNode }): React.ReactElement {
  return <p className="text-secondary text-sm leading-relaxed mb-3">{children}</p>
}

function UL({ children }: { children: React.ReactNode }): React.ReactElement {
  return <ul className="list-disc list-outside pl-5 space-y-1 text-secondary text-sm leading-relaxed mb-3">{children}</ul>
}

function LI({ children }: { children: React.ReactNode }): React.ReactElement {
  return <li>{children}</li>
}

function Warning({ children }: { children: React.ReactNode }): React.ReactElement {
  return (
    <div className="bg-warning/5 border border-warning/20 rounded-xl p-4 mb-4">
      <p className="text-secondary text-sm leading-relaxed font-mono text-xs">{children}</p>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function TermsOfService(): React.ReactElement {
  return (
    <div className="min-h-screen bg-base text-primary">
      <Navbar />

      <main className="pt-20 pb-20 px-6">
        <div className="max-w-3xl mx-auto">
          {/* Header */}
          <div className="mb-8 pt-8 border-b border-border pb-6">
            <p className="text-muted text-xs font-mono uppercase tracking-widest mb-2">Legal</p>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-primary mb-2">
              Terms of Service
            </h1>
            <p className="text-secondary text-sm">
              <span className="font-medium">Last updated:</span> May 28, 2026
              <span className="mx-2 text-border-strong">·</span>
              <span className="font-medium">Effective date:</span> May 28, 2026
            </p>
          </div>

          {/* Intro */}
          <P>
            Please read these Terms of Service ("Terms") carefully before using the ArbiterAI platform at{' '}
            <a href="https://arbiterai.dev" className="text-accent-light hover:text-primary transition-colors">arbiterai.dev</a>{' '}
            ("Service") operated by Jaiden Sy ("Arbiter," "we," "us," or "our").
          </P>

          <div className="bg-surface border border-border-strong rounded-xl p-4 mb-6">
            <p className="text-primary text-sm font-semibold">
              BY CREATING AN ACCOUNT OR CLICKING "I AGREE," YOU AGREE TO BE BOUND BY THESE TERMS. IF YOU DO NOT AGREE, DO NOT USE THE SERVICE.
            </p>
          </div>

          {/* 1 */}
          <H2>1. Acceptance of Terms</H2>
          <P>
            These Terms constitute a legally binding agreement between you and Arbiter. You must be at least 13 years of age to use the Service. If you are using the Service on behalf of an organization, you represent that you have authority to bind that organization to these Terms.
          </P>

          {/* 2 */}
          <H2>2. Description of Service</H2>
          <P>ArbiterAI is a software-as-a-service platform that provides:</P>
          <UL>
            <LI>An MCP (Model Context Protocol) gateway that proxies tool calls from AI agents to connected MCP servers</LI>
            <LI>A secrets vault for storing encrypted API keys and credentials</LI>
            <LI>Role-based access control (RBAC) for AI agent tool permissions</LI>
            <LI>Semantic caching of tool call responses</LI>
            <LI>Session audit logging and observability</LI>
          </UL>
          <P>
            Arbiter is an <strong className="text-primary">infrastructure intermediary</strong>. Arbiter does not generate AI outputs, does not operate the MCP servers you connect, and does not control the behavior of AI agents you configure.
          </P>

          {/* 3 */}
          <H2>3. Account Registration</H2>
          <P>To use the Service, you must register an account. You agree to:</P>
          <UL>
            <LI>Provide accurate, current, and complete information</LI>
            <LI>Maintain the security of your password and API keys</LI>
            <LI>Notify us immediately of any unauthorized use of your account</LI>
            <LI>Be responsible for all activity that occurs under your account</LI>
          </UL>
          <P>We reserve the right to refuse registration or terminate accounts at our discretion.</P>

          {/* 4 */}
          <H2>4. Acceptable Use Policy</H2>
          <P>You agree NOT to use the Service to:</P>
          <UL>
            <LI>a) Violate any applicable local, state, national, or international law or regulation.</LI>
            <LI>b) Store credentials for services you are not authorized to use.</LI>
            <LI>c) Route tool calls that violate the terms of service of any third-party API or service.</LI>
            <LI>d) Launch or facilitate cyberattacks, denial-of-service attacks, credential stuffing, or any unauthorized access to third-party systems via tool calls.</LI>
            <LI>e) Attempt to circumvent, bypass, or defeat Arbiter's RBAC controls, vault encryption, or authentication mechanisms.</LI>
            <LI>f) Reverse-engineer, decompile, or disassemble any component of the Service.</LI>
            <LI>g) Scrape, crawl, or extract data from the Service in bulk.</LI>
            <LI>h) Resell, sublicense, or provide access to the Service to third parties without our written consent.</LI>
            <LI>i) Use the Service in life-critical systems (medical devices, nuclear facilities, aircraft, emergency response systems) without our prior written agreement.</LI>
            <LI>j) Allow minors under the age of 13 to use the Service.</LI>
            <LI>k) Impersonate any person or entity or misrepresent your affiliation.</LI>
          </UL>
          <P>Violation of this policy may result in immediate account termination without refund.</P>

          {/* 5 */}
          <H2>5. AI Proxy Disclaimer</H2>
          <div className="bg-surface border border-border rounded-xl p-4 mb-4">
            <p className="text-primary text-sm font-semibold mb-3">IMPORTANT: Arbiter is a proxy service. You acknowledge and agree that:</p>
            <ul className="space-y-2 text-secondary text-sm">
              <li>a) Arbiter does not generate, create, review, or endorse the content of tool calls made by AI agents through the Service.</li>
              <li>b) Arbiter is not responsible for the actions taken by AI agents via connected MCP servers, including but not limited to: data access, data modification, data deletion, financial transactions, API calls to third-party services, or any real-world consequences of tool call execution.</li>
              <li>c) You are solely responsible for: (i) the AI agents you configure and connect to Arbiter, (ii) the MCP servers you register and the permissions you grant, (iii) the content of tool call payloads routed through Arbiter, and (iv) any harm caused by tool calls executed under your account.</li>
              <li>d) Arbiter does not guarantee the security, availability, accuracy, or compliance of any connected MCP server.</li>
              <li>e) You are responsible for ensuring that the AI agents you connect comply with all applicable laws and the terms of service of any third-party API accessed via tool calls.</li>
            </ul>
          </div>

          {/* 6 */}
          <H2>6. Intellectual Property</H2>
          <P>
            <strong className="text-primary">Arbiter's IP:</strong> The Service, including all software, design, UI, algorithms, and infrastructure, is owned by Arbiter and protected by intellectual property laws. You receive a limited, non-exclusive, non-transferable license to use the Service for your internal business purposes.
          </P>
          <P>
            <strong className="text-primary">Your Data:</strong> You retain all rights to your data — including vault secrets, MCP server configurations, agent records, and tool call content. You grant Arbiter a limited license to process your data solely as necessary to provide the Service.
          </P>
          <P>
            <strong className="text-primary">Feedback:</strong> If you provide feedback or suggestions about the Service, you grant us an irrevocable, royalty-free license to use that feedback without restriction.
          </P>

          {/* 7 */}
          <H2>7. Payment Terms</H2>
          <UL>
            <LI>a) <strong className="text-primary">Subscription:</strong> The Pro plan is billed monthly at the price displayed at the time of subscription. Billing is through Stripe. Your subscription auto-renews monthly unless cancelled.</LI>
            <LI>b) <strong className="text-primary">Cancellation:</strong> You may cancel at any time via your account settings. Cancellation takes effect at the end of the current billing period. No prorated refunds are provided for partial months.</LI>
            <LI>c) <strong className="text-primary">Price changes:</strong> We will provide 30 days advance notice of price changes. Continued use after the notice period constitutes acceptance of the new price.</LI>
            <LI>d) <strong className="text-primary">Payment processing:</strong> Stripe processes all payments. Arbiter does not receive or store your full credit card information. Your card data is subject to Stripe's Privacy Policy and Terms.</LI>
            <LI>e) <strong className="text-primary">Taxes:</strong> You are responsible for all applicable taxes. Prices do not include taxes unless stated.</LI>
            <LI>f) <strong className="text-primary">Free tier:</strong> If a free tier is offered, it is provided as-is without warranty, and we reserve the right to modify or discontinue it at any time.</LI>
          </UL>

          {/* 8 */}
          <H2>8. Data and Privacy</H2>
          <P>
            Our collection and use of your personal information is governed by our{' '}
            <Link to="/privacy" className="text-accent-light hover:text-primary transition-colors">Privacy Policy</Link>,
            which is incorporated into these Terms by reference. By using the Service, you agree to our Privacy Policy.
          </P>
          <P>
            <strong className="text-primary">You</strong> are the data controller for any personal data you introduce into tool call payloads. Arbiter processes such data only as your data processor. You are responsible for ensuring you have the legal right to process such data and for providing any required notices to data subjects.
          </P>

          {/* 9 */}
          <H2>9. Confidentiality</H2>
          <P>
            Each party agrees to keep confidential any non-public information disclosed by the other party that is designated as confidential or that reasonably should be understood to be confidential. This obligation does not apply to information that: (a) is or becomes publicly known through no breach of this agreement; (b) was rightfully known before disclosure; (c) is independently developed without use of the confidential information; or (d) must be disclosed by law.
          </P>

          {/* 10 */}
          <H2>10. Service Availability</H2>
          <Warning>
            THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE." WE DO NOT WARRANT THAT THE SERVICE WILL BE UNINTERRUPTED, ERROR-FREE, OR AVAILABLE AT ANY PARTICULAR TIME OR LOCATION. WE DO NOT MAKE ANY GUARANTEES REGARDING UPTIME OR PERFORMANCE LEVELS. PLANNED AND UNPLANNED MAINTENANCE MAY CAUSE TEMPORARY UNAVAILABILITY.
          </Warning>
          <P>
            We will use commercially reasonable efforts to maintain Service availability but shall not be liable for any losses arising from Service unavailability.
          </P>

          {/* 11 */}
          <H2>11. Disclaimer of Warranties</H2>
          <Warning>
            TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, THE SERVICE IS PROVIDED WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, NON-INFRINGEMENT, AND ACCURACY. ARBITER DOES NOT WARRANT THAT: (A) THE SERVICE WILL MEET YOUR REQUIREMENTS; (B) THE SERVICE WILL BE SECURE OR FREE FROM BUGS OR ERRORS; (C) ANY TOOL CALL OUTPUTS WILL BE ACCURATE, COMPLETE, OR SUITABLE FOR ANY PARTICULAR PURPOSE; OR (D) ANY SECURITY VULNERABILITIES IN CONNECTED MCP SERVERS WILL BE DETECTED OR PREVENTED.
          </Warning>

          {/* 12 */}
          <H2>12. Limitation of Liability</H2>
          <Warning>
            TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, IN NO EVENT SHALL ARBITER, ITS OFFICERS, DIRECTORS, EMPLOYEES, CONTRACTORS, OR AGENTS BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING WITHOUT LIMITATION LOSS OF PROFITS, DATA, USE, GOODWILL, BUSINESS INTERRUPTION, OR OTHER INTANGIBLE LOSSES, ARISING OUT OF OR RELATED TO:{'\n\n'}
            (i) YOUR ACCESS TO OR USE OF (OR INABILITY TO ACCESS OR USE) THE SERVICE;{'\n'}
            (ii) ANY CONDUCT OR CONTENT OF ANY THIRD PARTY ACCESSED THROUGH THE SERVICE;{'\n'}
            (iii) ANY TOOL CALL EXECUTED BY AN AI AGENT THROUGH THE ARBITER PROXY, AND ANY DOWNSTREAM CONSEQUENCES THEREOF;{'\n'}
            (iv) UNAUTHORIZED ACCESS, USE, OR ALTERATION OF YOUR TRANSMISSIONS OR DATA;{'\n'}
            (v) ANY ACTIONS OR OMISSIONS OF MCP SERVERS YOU CONNECT TO THE SERVICE.{'\n\n'}
            IN NO EVENT SHALL ARBITER'S TOTAL AGGREGATE LIABILITY TO YOU FOR ALL CLAIMS ARISING OUT OF OR RELATED TO THESE TERMS OR YOUR USE OF THE SERVICE EXCEED THE GREATER OF: (A) THE TOTAL FEES PAID BY YOU TO ARBITER IN THE TWELVE (12) MONTHS IMMEDIATELY PRECEDING THE CLAIM; OR (B) ONE HUNDRED US DOLLARS ($100).{'\n\n'}
            THE LIMITATIONS IN THIS SECTION SHALL APPLY EVEN IF ARBITER HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES. SOME JURISDICTIONS DO NOT ALLOW THE EXCLUSION OR LIMITATION OF INCIDENTAL OR CONSEQUENTIAL DAMAGES, SO THE ABOVE LIMITATIONS MAY NOT APPLY TO YOU.
          </Warning>

          {/* 13 */}
          <H2>13. Indemnification</H2>
          <P>You agree to defend, indemnify, and hold harmless Arbiter and its officers, directors, employees, and agents from and against any claims, damages, losses, liabilities, costs, and expenses (including reasonable attorneys' fees) arising out of or related to:</P>
          <UL>
            <LI>a) Your use of the Service in violation of these Terms;</LI>
            <LI>b) Actions taken by AI agents operating under your account via tool calls routed through the Service;</LI>
            <LI>c) Your breach of any representation, warranty, or obligation in these Terms;</LI>
            <LI>d) Your violation of any third party's rights, including intellectual property rights;</LI>
            <LI>e) Any data you introduce into tool call payloads.</LI>
          </UL>

          {/* 14 */}
          <H2>14. DMCA / Copyright</H2>
          <P>
            We respect intellectual property rights. If you believe content available through the Service infringes your copyright, please send a notice to:{' '}
            <a href="mailto:dmca@arbiterai.dev" className="text-accent-light hover:text-primary transition-colors">dmca@arbiterai.dev</a>
          </P>
          <P>
            Your notice must include: (1) identification of the copyrighted work; (2) identification of the infringing material; (3) your contact information; (4) a statement of good faith belief; (5) a statement of accuracy under penalty of perjury; and (6) your signature.
          </P>
          <P>Our designated agent is registered with the U.S. Copyright Office (Registration No. DMCA-1073513). We have adopted a policy of terminating accounts of repeat copyright infringers.</P>

          {/* 15 */}
          <H2>15. Termination</H2>
          <P>
            <strong className="text-primary">By you:</strong> You may terminate your account at any time via account settings. Termination is effective at the end of the current billing period.
          </P>
          <P>
            <strong className="text-primary">By us:</strong> We may suspend or terminate your account immediately, without notice or liability, if you: (a) violate these Terms; (b) engage in fraudulent or illegal activity; (c) pose a security risk to the Service or other users. We may also terminate the Service entirely upon 30 days notice.
          </P>
          <P>
            <strong className="text-primary">Effect of termination:</strong> Upon termination, your right to use the Service ceases immediately. We will delete your data in accordance with our{' '}
            <Link to="/privacy" className="text-accent-light hover:text-primary transition-colors">Privacy Policy</Link>.
            Provisions that by their nature should survive termination (including Sections 5, 6, 12, 13, 16, and 17) shall survive.
          </P>

          {/* 16 */}
          <H2>16. Dispute Resolution</H2>
          <P>
            <strong className="text-primary">Informal resolution:</strong> Before filing a formal claim, you agree to contact us at{' '}
            <a href="mailto:legal@arbiterai.dev" className="text-accent-light hover:text-primary transition-colors">legal@arbiterai.dev</a>{' '}
            and attempt to resolve the dispute informally for at least 30 days.
          </P>
          <P>
            <strong className="text-primary">Binding arbitration:</strong> If informal resolution fails, any dispute arising out of or relating to these Terms or the Service shall be resolved by binding individual arbitration administered by the American Arbitration Association (AAA) under its Consumer Arbitration Rules, rather than in court.
          </P>
          <P>
            <strong className="text-primary">Class action waiver:</strong> YOU AND ARBITER AGREE THAT EACH MAY BRING CLAIMS AGAINST THE OTHER ONLY IN AN INDIVIDUAL CAPACITY AND NOT AS A PLAINTIFF OR CLASS MEMBER IN ANY PURPORTED CLASS OR REPRESENTATIVE ACTION.
          </P>
          <P>
            <strong className="text-primary">Small claims exception:</strong> Either party may bring an individual claim in small claims court if the claim qualifies.
          </P>
          <P>
            <strong className="text-primary">Jury waiver:</strong> YOU AND ARBITER WAIVE THE RIGHT TO A TRIAL BY JURY FOR ANY CLAIM.
          </P>
          <P>
            <strong className="text-primary">Governing law:</strong> These Terms are governed by the laws of the State of California, without regard to its conflict of law principles.
          </P>
          <P>
            <strong className="text-primary">Venue:</strong> For any claim not subject to arbitration, the exclusive jurisdiction and venue shall be the state and federal courts located in San Francisco County, California.
          </P>

          {/* 17 */}
          <H2>17. General Provisions</H2>
          <UL>
            <LI><strong className="text-primary">Entire agreement:</strong> These Terms, together with the Privacy Policy, constitute the entire agreement between you and Arbiter regarding the Service and supersede all prior agreements.</LI>
            <LI><strong className="text-primary">Severability:</strong> If any provision of these Terms is found unenforceable, the remaining provisions will remain in full force and effect.</LI>
            <LI><strong className="text-primary">Waiver:</strong> Our failure to enforce any right or provision of these Terms will not be considered a waiver of those rights.</LI>
            <LI><strong className="text-primary">Assignment:</strong> You may not assign or transfer these Terms without our prior written consent. We may assign our rights and obligations without restriction.</LI>
            <LI><strong className="text-primary">No agency:</strong> Nothing in these Terms creates a partnership, joint venture, agency, employment, or franchise relationship between you and Arbiter.</LI>
            <LI><strong className="text-primary">Notices:</strong> We may provide notices via email to your registered address or by posting to the Service. You may provide notices to us at <a href="mailto:legal@arbiterai.dev" className="text-accent-light hover:text-primary transition-colors">legal@arbiterai.dev</a>.</LI>
            <LI><strong className="text-primary">Force majeure:</strong> Neither party shall be liable for delays or failures in performance resulting from circumstances beyond their reasonable control.</LI>
            <LI><strong className="text-primary">Changes to Terms:</strong> We may modify these Terms at any time. We will provide 30 days notice of material changes via email and in-app notice. Your continued use of the Service after the effective date of changes constitutes acceptance. If you object to changes, your sole remedy is to stop using the Service and close your account.</LI>
          </UL>

          {/* Contact */}
          <div className="bg-surface border border-border rounded-xl p-5 text-sm text-secondary mt-8">
            <p className="font-semibold text-primary mb-1">ArbiterAI / Jaiden Sy</p>
            <p>California, United States</p>
            <p>Email: <a href="mailto:legal@arbiterai.dev" className="text-accent-light hover:text-primary transition-colors">legal@arbiterai.dev</a></p>
            <p className="mt-2 text-xs text-muted italic">These Terms were last updated May 28, 2026.</p>
          </div>

          {/* Footer links */}
          <div className="mt-12 pt-6 border-t border-border flex items-center gap-4 text-xs text-muted">
            <Link to="/privacy" className="hover:text-secondary transition-colors">Privacy Policy</Link>
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
