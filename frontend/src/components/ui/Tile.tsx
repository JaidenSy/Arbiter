import React from 'react'
import { Link } from 'react-router-dom'
import { AreaChart, Area, ResponsiveContainer } from 'recharts'

export type TileVariant = 'default' | 'amber' | 'teal' | 'warning' | 'error'
export type TileSpan    = 1 | 2 | 3

export interface TileProps {
  variant?:       TileVariant
  colSpan?:       TileSpan
  label:          string
  value:          string | number
  valueClass?:    string
  trend?:         'up' | 'down' | 'neutral'
  trendValue?:    string
  to?:            string
  sparklineData?: number[]
  sparklineColor?: string
  mountDelay?:    number
  className?:     string
  children?:      React.ReactNode
}

const variantBg: Record<TileVariant, string> = {
  default: 'bg-surface',
  amber:   'tile-amber',
  teal:    'tile-teal',
  warning: 'tile-warning',
  error:   'tile-error',
}

const trendIcon = {
  up:      '↑',
  down:    '↓',
  neutral: '—',
}

const trendColor = {
  up:      'text-success',
  down:    'text-error',
  neutral: 'text-muted',
}

const staggerClass: Record<number, string> = {
  0: '',
  1: 'stagger-1',
  2: 'stagger-2',
  3: 'stagger-3',
  4: 'stagger-4',
  5: 'stagger-5',
}

export function Tile({
  variant     = 'default',
  colSpan     = 1,
  label,
  value,
  valueClass  = '',
  trend,
  trendValue,
  to,
  sparklineData,
  sparklineColor = 'var(--color-accent)',
  mountDelay  = 0,
  className   = '',
  children,
}: TileProps) {
  const spanClass = colSpan === 2 ? 'col-span-2' : colSpan === 3 ? 'col-span-3' : ''
  const stagger   = staggerClass[mountDelay] ?? ''
  const isLink    = !!to

  const inner = (
    <>
      <p className="text-muted text-[11px] font-mono tracking-wider uppercase mb-2">
        {label}
      </p>
      <div className="flex items-baseline gap-2">
        <span className={`text-2xl font-mono font-light tabular-nums text-primary ${valueClass}`}>
          {value}
        </span>
        {trend && trendValue && (
          <span className={`text-xs font-mono ${trendColor[trend]}`}>
            {trendIcon[trend]} {trendValue}
          </span>
        )}
      </div>
      {sparklineData && sparklineData.length > 0 && (
        <div className="mt-3">
          <ResponsiveContainer width="100%" height={32}>
            <AreaChart
              data={sparklineData.map((v) => ({ value: v }))}
              margin={{ top: 2, right: 0, left: 0, bottom: 0 }}
            >
              <defs>
                <linearGradient id={`grad-${label}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={sparklineColor} stopOpacity={0.18} />
                  <stop offset="95%" stopColor={sparklineColor} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="value"
                stroke={sparklineColor}
                strokeWidth={1.5}
                fill={`url(#grad-${label})`}
                dot={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
      {children}
      {isLink && (
        <p className="text-muted text-[10px] font-mono mt-2 opacity-0 group-hover:opacity-100 transition-opacity duration-[var(--duration-fast)]">
          View all →
        </p>
      )}
    </>
  )

  const tileClass = [
    'p-4 rounded-xl border border-border group',
    variantBg[variant],
    'tile-mount',
    stagger,
    isLink ? 'transition-[border-color] duration-[var(--duration-fast)] hover:border-border-accent cursor-pointer' : '',
    spanClass,
    className,
  ].filter(Boolean).join(' ')

  if (isLink) {
    return (
      <Link to={to!} className={tileClass}>
        {inner}
      </Link>
    )
  }

  return <div className={tileClass}>{inner}</div>
}
