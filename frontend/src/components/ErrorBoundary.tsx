import React from 'react'

interface Props {
  children: React.ReactNode
  /** Compact inline fallback instead of full-screen — for isolated sections */
  inline?: boolean
  /** Custom fallback to render instead of the default UI */
  fallback?: React.ReactNode
}

interface State {
  error: Error | null
  componentStack: string | null
  copied: boolean
}

class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null, componentStack: null, copied: false }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    this.setState({ componentStack: info.componentStack ?? null })
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  handleReset = (): void => {
    this.setState({ error: null, componentStack: null, copied: false })
    window.location.href = '/'
  }

  handleCopy = (): void => {
    const { error, componentStack } = this.state
    const text = [
      `Error: ${error?.message}`,
      error?.stack,
      componentStack ? `\nComponent stack:${componentStack}` : '',
    ].filter(Boolean).join('\n')
    navigator.clipboard.writeText(text).then(() => {
      this.setState({ copied: true })
      setTimeout(() => this.setState({ copied: false }), 2000)
    })
  }

  render(): React.ReactNode {
    const { error, componentStack, copied } = this.state
    const { inline, fallback } = this.props

    if (!error) return this.props.children

    if (fallback) return fallback

    if (inline) {
      return (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-error/10 border border-error/20 text-error text-xs">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <span className="font-mono truncate">{error.message || 'Render error'}</span>
        </div>
      )
    }

    return (
      <div className="min-h-screen bg-base flex items-center justify-center px-6">
        <div className="max-w-lg w-full">
          <div className="w-14 h-14 rounded-2xl bg-error/10 flex items-center justify-center mx-auto mb-5">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-error">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
          </div>

          <h1 className="text-primary text-lg font-semibold mb-2 text-center">Something went wrong</h1>
          <p className="text-secondary text-sm mb-4 text-center">An unexpected error occurred. Copy the details below and open an issue if this keeps happening.</p>

          {/* Error detail box */}
          <div className="bg-[#0A0A0B] border border-border rounded-xl p-4 mb-5 text-left space-y-2">
            <p className="text-error text-xs font-mono break-all">{error.message}</p>
            {componentStack && (
              <details className="group">
                <summary className="text-muted text-xs cursor-pointer select-none hover:text-secondary transition-colors">
                  Component stack
                </summary>
                <pre className="text-muted text-[10px] font-mono mt-2 whitespace-pre-wrap break-all leading-relaxed max-h-40 overflow-y-auto">
                  {componentStack.trim()}
                </pre>
              </details>
            )}
          </div>

          <div className="flex gap-3 justify-center">
            <button
              type="button"
              onClick={this.handleCopy}
              className="border border-border-strong hover:border-border-strong text-secondary hover:text-primary text-sm px-4 py-2 rounded-lg transition-colors"
            >
              {copied ? 'Copied!' : 'Copy details'}
            </button>
            <button
              type="button"
              onClick={this.handleReset}
              className="bg-accent hover:bg-accent-light text-white text-sm font-semibold px-5 py-2 rounded-lg transition-all hover-glow-standard"
            >
              Back to Dashboard
            </button>
          </div>
        </div>
      </div>
    )
  }
}

export default ErrorBoundary
