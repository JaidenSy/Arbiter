import React from 'react'

interface ArbiterLogoProps {
  size?: number
  className?: string
}

export function ArbiterMark({ size = 36, className = '' }: ArbiterLogoProps): React.ReactElement {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 200 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Arbiter"
    >
      <defs>
        <linearGradient id="arbiter-bg" x1="0" y1="0" x2="200" y2="200" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#1a1030" />
          <stop offset="100%" stopColor="#0a0a18" />
        </linearGradient>
        <linearGradient id="arbiter-mark" x1="40" y1="36" x2="160" y2="164" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#C4B5FD" />
          <stop offset="55%" stopColor="#8B5CF6" />
          <stop offset="100%" stopColor="#6D28D9" />
        </linearGradient>
        <linearGradient id="arbiter-bar" x1="62" y1="116" x2="138" y2="116" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#7C3AED" />
          <stop offset="50%" stopColor="#C4B5FD" />
          <stop offset="100%" stopColor="#7C3AED" />
        </linearGradient>
        <filter id="arbiter-apex-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Background rounded square */}
      <rect width="200" height="200" rx="44" fill="url(#arbiter-bg)" />

      {/* Subtle border */}
      <rect width="200" height="200" rx="44" fill="none" stroke="#8B5CF6" strokeWidth="1.5" strokeOpacity="0.25" />

      {/* Left leg of A */}
      <line x1="34" y1="164" x2="100" y2="38" stroke="url(#arbiter-mark)" strokeWidth="18" strokeLinecap="round" />

      {/* Right leg of A */}
      <line x1="100" y1="38" x2="166" y2="164" stroke="url(#arbiter-mark)" strokeWidth="18" strokeLinecap="round" />

      {/* Crossbar left half */}
      <line x1="62" y1="116" x2="88" y2="116" stroke="url(#arbiter-bar)" strokeWidth="13" strokeLinecap="round" />

      {/* Crossbar right half */}
      <line x1="112" y1="116" x2="138" y2="116" stroke="url(#arbiter-bar)" strokeWidth="13" strokeLinecap="round" />

      {/* Gate posts at the gap */}
      <line x1="88" y1="109" x2="88" y2="123" stroke="#A78BFA" strokeWidth="2.5" strokeLinecap="round" strokeOpacity="0.9" />
      <line x1="112" y1="109" x2="112" y2="123" stroke="#A78BFA" strokeWidth="2.5" strokeLinecap="round" strokeOpacity="0.9" />

      {/* Apex glow dot */}
      <circle cx="100" cy="38" r="7" fill="#EDE9FE" filter="url(#arbiter-apex-glow)" opacity="0.85" />
    </svg>
  )
}

interface ArbiterWordmarkProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export function ArbiterWordmark({ size = 'md', className = '' }: ArbiterWordmarkProps): React.ReactElement {
  const iconSize = size === 'sm' ? 28 : size === 'lg' ? 48 : 36
  const textClass = size === 'sm' ? 'text-base' : size === 'lg' ? 'text-2xl' : 'text-lg'

  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <ArbiterMark size={iconSize} />
      <span className={`font-bold tracking-tight text-primary ${textClass}`}>
        Arbiter
      </span>
    </div>
  )
}
