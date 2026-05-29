/**
 * Arbiter — Changelog page.
 *
 * Route: /changelog (public, no auth required)
 * Reverse-chronological list of releases and notable changes.
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

function P({ children }: { children: React.ReactNode }): React.ReactElement {
  return <p className="text-secondary text-sm leading-relaxed mb-3">{children}</p>
}

function UL({ children }: { children: React.ReactNode }): React.ReactElement {
  return <ul className="list-disc list-outside pl-5 space-y-1 text-secondary text-sm leading-relaxed mb-3">{children}</ul>
}

function LI({ children }: { children: React.ReactNode }): React.ReactElement {
  return <li>{children}</li>
}

// ── Release entry ──────────────────────────────────────────────────────────────

interface ReleaseProps {
  version: string
  date: string
  children: React.ReactNode
}

function Release({ version, date, children }: ReleaseProps): React.ReactElement {
  return (
    <div className="border-b border-border pb-8">
      <div className="flex items-baseline gap-3 mb-1">
        <span className="font-display text-base font-semibold text-primary tracking-tight">{version}</span>
        <span className="text-muted text-xs font-mono">{date}</span>
      </div>
      {children}
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function Changelog(): React.ReactElement {
  return (
    <div className="min-h-screen bg-base text-primary">
      <Navbar />

      <main className="pt-20 pb-20 px-6">
        <div className="max-w-3xl mx-auto">
          {/* Header */}
          <div className="mb-8 pt-8 border-b border-border pb-6">
            <p className="text-muted text-xs font-mono uppercase tracking-widest mb-2">Product</p>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-primary mb-2">
              Changelog
            </h1>
            <P>Notable changes and releases, newest first.</P>
          </div>

          {/* Releases */}
          <div className="space-y-8 mt-2">

            <Release version="v1.1.0" date="May 29, 2026">
              <UL>
                <LI>Email verification now required before proxy access is granted</LI>
                <LI>Privacy Policy and Terms of Service published at <Link to="/privacy" className="text-accent-light hover:text-primary transition-colors">/privacy</Link> and <Link to="/terms" className="text-accent-light hover:text-primary transition-colors">/terms</Link></LI>
                <LI>DMCA designated agent registered (DMCA-1073513)</LI>
                <LI>API documentation disabled in production for security</LI>
                <LI>Account deletion now cancels active Stripe subscription</LI>
                <LI>Rate limiting added to authentication endpoints</LI>
                <LI>Landing page: static hero background, performance improvements</LI>
              </UL>
            </Release>

          </div>

          {/* Footer links */}
          <div className="mt-12 pt-6 border-t border-border flex items-center gap-4 text-xs text-muted">
            <Link to="/privacy" className="hover:text-secondary transition-colors">Privacy Policy</Link>
            <span>·</span>
            <Link to="/terms" className="hover:text-secondary transition-colors">Terms of Service</Link>
            <span>·</span>
            <Link to="/security" className="hover:text-secondary transition-colors">Security</Link>
            <span>·</span>
            <Link to="/" className="hover:text-secondary transition-colors">Back to Arbiter</Link>
          </div>
        </div>
      </main>
    </div>
  )
}
