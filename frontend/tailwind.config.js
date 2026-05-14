/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        base: '#080808',
        surface: '#111111',
        elevated: '#1a1a1a',
        highlight: '#221c36',
        accent: '#7c3aed',
        'accent-light': '#a78bfa',
        border: 'rgba(255,255,255,0.07)',
        'border-strong': 'rgba(255,255,255,0.14)',
        primary: '#efefef',
        secondary: '#888888',
        muted: '#444444',
        error: '#f87171',
      },
      fontFamily: {
        mono: ['ui-monospace', 'JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
