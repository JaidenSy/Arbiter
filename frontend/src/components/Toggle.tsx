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
        className={`relative inline-flex items-center rounded-full transition-colors focus:outline-none ${
          checked
            ? 'bg-accent'
            : 'bg-elevated border border-white/[0.14]'
        }`}
        style={{ width: 36, height: 20 }}
      >
        <span
          className={`w-3.5 h-3.5 rounded-full bg-white transition-transform ${
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
