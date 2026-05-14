/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        base: '#07080C',
        surface: '#0E0F16',
        elevated: '#161822',
        highlight: '#1E1B35',
        overlay: '#12131A',
        accent: '#7C3AED',
        'accent-light': '#A78BFA',
        'accent-dim': '#4C1D95',
        teal: '#14B8A6',
        'teal-light': '#5EEAD4',
        border: 'rgba(255,255,255,0.06)',
        'border-strong': 'rgba(255,255,255,0.12)',
        'border-accent': 'rgba(124,58,237,0.4)',
        primary: '#F0F0F5',
        secondary: '#7A7A8C',
        muted: '#3A3A4C',
        error: '#F87171',
        success: '#34D399',
        warning: '#FBBF24',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['ui-monospace', 'JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
