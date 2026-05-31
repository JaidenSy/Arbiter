// Recharts SVG <defs> and JS-object styles cannot consume CSS vars — approved hex exceptions.
export const CHART_COLORS = {
  amber: '#2563EB',
  teal:  '#06B6D4',
} as const

// Recharts Tooltip contentStyle requires JS object — matches token values.
export const CHART_TOOLTIP_STYLE = {
  content: {
    background: '#09090B',              // --color-base
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 8,
    fontSize: 12,
    fontFamily: 'monospace',
  },
  label:  { color: '#7A7A8C', marginBottom: 4 }, // --color-muted approx
  item:   { color: '#F0F0F5' },                   // --color-primary approx
  tick:   { fill: '#3A3A4C', fontSize: 11, fontFamily: 'monospace' }, // sub-muted
} as const
