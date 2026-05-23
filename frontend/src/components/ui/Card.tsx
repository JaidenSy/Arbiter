import React from 'react'

export type CardVariant = 'default' | 'elevated' | 'accent' | 'ghost'

export interface CardProps {
  variant?:   CardVariant
  className?: string
  children:   React.ReactNode
  onClick?:   () => void
}

interface CardHeaderProps {
  title:     string
  subtitle?: string
  action?:   React.ReactNode
  className?: string
}

interface CardSectionProps {
  className?: string
  children:   React.ReactNode
}

const variantClasses: Record<CardVariant, string> = {
  default:  'bg-surface border border-border',
  elevated: 'bg-elevated border border-border-strong',
  accent:   'bg-surface border border-border-accent shadow-[var(--glow-subtle)]',
  ghost:    'bg-transparent border border-transparent',
}

const hoverClasses: Record<CardVariant, string> = {
  default:  'hover:border-border-strong',
  elevated: 'hover:border-border-accent',
  accent:   'hover:shadow-[var(--glow-standard)]',
  ghost:    'hover:bg-white/[0.025] hover:border-border',
}

function Card({ variant = 'default', className = '', children, onClick }: CardProps) {
  const clickable = !!onClick
  return (
    <div
      role={clickable ? 'button' : undefined}
      tabIndex={clickable ? 0 : undefined}
      onClick={onClick}
      onKeyDown={clickable ? (e) => { if (e.key === 'Enter' || e.key === ' ') onClick() } : undefined}
      className={[
        'rounded-xl',
        variantClasses[variant],
        'transition-[border-color,box-shadow] duration-[var(--duration-fast)] ease-[var(--ease-out-expo)]',
        clickable ? `cursor-pointer ${hoverClasses[variant]}` : '',
        className,
      ].filter(Boolean).join(' ')}
    >
      {children}
    </div>
  )
}

function CardHeader({ title, subtitle, action, className = '' }: CardHeaderProps) {
  return (
    <div className={`flex items-start justify-between px-5 pt-5 ${className}`}>
      <div>
        <h3 className="text-sm font-semibold text-primary">{title}</h3>
        {subtitle && <p className="text-xs text-muted mt-0.5">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0 ml-4">{action}</div>}
    </div>
  )
}

function CardBody({ className = '', children }: CardSectionProps) {
  return (
    <div className={`px-5 py-4 ${className}`}>
      {children}
    </div>
  )
}

function CardFooter({ className = '', children }: CardSectionProps) {
  return (
    <div className={`px-5 pb-5 ${className}`}>
      {children}
    </div>
  )
}

Card.Header = CardHeader
Card.Body   = CardBody
Card.Footer = CardFooter

export { Card }
