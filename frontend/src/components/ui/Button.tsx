import React, { forwardRef } from 'react'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive'
export type ButtonSize    = 'sm' | 'md' | 'lg'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?:   ButtonVariant
  size?:      ButtonSize
  isLoading?: boolean
  leftIcon?:  React.ReactNode
  rightIcon?: React.ReactNode
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:     'bg-accent text-white hover:bg-accent-light hover-glow-standard',
  secondary:   'bg-elevated border border-border-strong text-primary hover:bg-white/[0.05] hover:border-border-accent',
  ghost:       'text-secondary hover:text-primary hover:bg-white/[0.04]',
  destructive: 'text-error border border-transparent hover:bg-error/10 hover:border-error/20',
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'h-7 px-3 text-xs font-medium rounded-lg',
  md: 'h-9 px-4 text-sm font-semibold rounded-lg',
  lg: 'h-11 px-6 text-sm font-semibold rounded-xl',
}

const Spinner = () => (
  <svg
    className="animate-spin"
    width="12"
    height="12"
    viewBox="0 0 12 12"
    fill="none"
    aria-hidden="true"
  >
    <circle
      cx="6" cy="6" r="5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeDasharray="20"
      strokeDashoffset="8"
      opacity="0.4"
    />
    <path
      d="M6 1a5 5 0 0 1 5 5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
    />
  </svg>
)

const Button = forwardRef<HTMLButtonElement, ButtonProps>(({
  variant = 'primary',
  size    = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  children,
  className = '',
  disabled,
  ...props
}, ref) => {
  const isDisabled = disabled || isLoading

  return (
    <button
      ref={ref}
      disabled={isDisabled}
      className={[
        'inline-flex items-center justify-center gap-2 select-none',
        'transition-[background-color,border-color,box-shadow,color]',
        'duration-[var(--duration-fast)] ease-[var(--ease-out-expo)]',
        'press',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40',
        'focus-visible:ring-offset-2 focus-visible:ring-offset-base',
        variantClasses[variant],
        sizeClasses[size],
        isDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
        className,
      ].join(' ')}
      {...props}
    >
      {isLoading ? (
        <Spinner />
      ) : (
        <>
          {leftIcon && <span className="shrink-0">{leftIcon}</span>}
          {children}
          {rightIcon && <span className="shrink-0">{rightIcon}</span>}
        </>
      )}
    </button>
  )
})

Button.displayName = 'Button'

export { Button }
