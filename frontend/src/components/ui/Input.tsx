import React, { forwardRef } from 'react'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?:          string
  label?:          string
  helperText?:     string
  leftAdornment?:  React.ReactNode
  rightAdornment?: React.ReactNode
  inputClassName?: string
}

const Input = forwardRef<HTMLInputElement, InputProps>(({
  error,
  label,
  helperText,
  leftAdornment,
  rightAdornment,
  inputClassName = '',
  className = '',
  id,
  ...props
}, ref) => {
  const inputId = id ?? (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined)

  const baseClass = [
    'bg-base border text-primary text-sm',
    'px-3 py-2 rounded-lg w-full',
    'focus:outline-none focus:ring-1',
    'transition-[border-color,box-shadow]',
    'duration-[var(--duration-fast)] ease-[var(--ease-out-expo)]',
    'placeholder:text-muted',
    error
      ? 'border-error/50 focus:border-error/70 focus:ring-error/20'
      : 'border-border focus:border-border-accent focus:ring-accent/25',
    leftAdornment  ? 'pl-9' : '',
    rightAdornment ? 'pr-9' : '',
    inputClassName,
  ].filter(Boolean).join(' ')

  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      {label && (
        <label
          htmlFor={inputId}
          className="text-sm font-medium text-secondary"
        >
          {label}
        </label>
      )}
      <div className="relative">
        {leftAdornment && (
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none">
            {leftAdornment}
          </span>
        )}
        <input
          ref={ref}
          id={inputId}
          className={baseClass}
          {...props}
        />
        {rightAdornment && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted">
            {rightAdornment}
          </span>
        )}
      </div>
      {error && (
        <p className="text-error text-xs mt-0.5">{error}</p>
      )}
      {helperText && !error && (
        <p className="text-muted text-xs">{helperText}</p>
      )}
    </div>
  )
})

Input.displayName = 'Input'

export { Input }
