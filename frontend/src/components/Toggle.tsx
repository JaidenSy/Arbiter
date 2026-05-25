import React from 'react'

interface ToggleProps {
  checked: boolean
  onChange: (val: boolean) => void
  label?: string
}

function Toggle({ checked, onChange, label }: ToggleProps): React.ReactElement {
  return (
    <div className="flex items-center">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex items-center rounded-full transition-colors duration-150 ease-[var(--ease-out-expo)] focus:outline-none focus-visible:ring-1 focus-visible:ring-accent ${
          checked
            ? 'bg-accent'
            : 'bg-elevated border border-border-strong'
        }`}
        style={{ width: 36, height: 20 }}
      >
        <span
          className={`w-3.5 h-3.5 rounded-full bg-white transition-transform duration-150 ease-[var(--ease-out-expo)] ${
            checked ? 'translate-x-[18px]' : 'translate-x-1'
          }`}
        />
      </button>
      {label && (
        <span className="text-secondary text-xs ml-2">{label}</span>
      )}
    </div>
  )
}

export default Toggle
