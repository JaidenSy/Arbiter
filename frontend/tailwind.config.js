/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        base: 'var(--color-base)',
        surface: 'var(--color-surface)',
        elevated: 'var(--color-elevated)',
        highlight: 'var(--color-highlight)',
        overlay: 'var(--color-overlay)',
        accent: 'var(--color-accent)',
        'accent-light': 'var(--color-accent-light)',
        'accent-dim': 'var(--color-accent-dim)',
        teal: 'var(--color-teal)',
        'teal-light': 'var(--color-teal-light)',
        border: 'rgba(255,255,255,0.06)',
        'border-strong': 'rgba(255,255,255,0.12)',
        'border-accent': 'rgba(124,58,237,0.4)',
        primary: 'var(--color-primary)',
        secondary: 'var(--color-secondary)',
        muted: 'var(--color-muted)',
        error: 'var(--color-error)',
        success: 'var(--color-success)',
        warning: 'var(--color-warning)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['ui-monospace', 'JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
