import React from 'react'
import { useScrollReveal } from '../hooks/useScrollReveal'
import { RevealGroup } from './RevealGroup'

const CLIENTS = [
  'Claude Desktop',
  'Cursor',
  'Continue',
  'Cline',
  'Zed',
]

export default function WorksWith(): React.ReactElement {
  const labelRef = useScrollReveal<HTMLParagraphElement>({ delay: 0 })

  return (
    <section className="px-6 border-t border-b border-border">
      <div className="max-w-3xl mx-auto py-10 flex flex-col items-center gap-5">
        <p ref={labelRef} className="text-muted text-xs">
          Works with any MCP client
        </p>

        <RevealGroup
          className="flex flex-wrap justify-center gap-2.5"
          stagger={60}
        >
          {CLIENTS.map(name => (
            <span
              key={name}
              className="font-mono text-xs font-medium px-3 py-1.5 border border-border rounded-md transition-colors duration-150"
              style={{ color: 'rgba(161,161,170,0.55)' }}
              onMouseEnter={e => (e.currentTarget.style.color = 'rgba(161,161,170,0.85)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(161,161,170,0.55)')}
            >
              {name}
            </span>
          ))}
        </RevealGroup>
      </div>
    </section>
  )
}
