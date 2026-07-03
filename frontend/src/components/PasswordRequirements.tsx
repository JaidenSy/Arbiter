/**
 * PasswordRequirements: live checklist of the password policy.
 *
 * Pure presentation; the rules live in `utils/password.ts`.
 */

import React from 'react'
import { evaluatePassword } from '../utils/password'

export default function PasswordRequirements({ password }: { password: string }): React.ReactElement {
  return (
    <ul className="space-y-1" aria-label="Password requirements">
      {evaluatePassword(password).map(({ label, met }) => (
        <li
          key={label}
          className={`flex items-center gap-2 text-xs transition-colors duration-150 ${
            met ? 'text-success' : 'text-muted'
          }`}
        >
          <span
            aria-hidden="true"
            className={`flex h-3.5 w-3.5 flex-shrink-0 items-center justify-center rounded-full border transition-colors duration-150 ${
              met ? 'border-success/40 bg-success/15 text-success' : 'border-border-strong text-transparent'
            }`}
          >
            <svg width="8" height="8" viewBox="0 0 12 12" fill="none">
              <path
                d="M2.5 6.5l2.5 2.5 4.5-5"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          {label}
        </li>
      ))}
    </ul>
  )
}
