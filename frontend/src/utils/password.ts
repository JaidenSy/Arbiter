/**
 * Shared password-strength policy for the frontend.
 *
 * Mirrors the backend rules in `backend/app/core/password.py`. Keep the two
 * in sync: any change here must be reflected there (and vice versa).
 */

export const PASSWORD_MIN_LENGTH = 12

export interface PasswordRuleStatus {
  label: string
  met: boolean
}

const RULES: { label: string; test: (password: string) => boolean }[] = [
  { label: `At least ${PASSWORD_MIN_LENGTH} characters`, test: (pw) => pw.length >= PASSWORD_MIN_LENGTH },
  { label: 'One lowercase letter', test: (pw) => /[a-z]/.test(pw) },
  { label: 'One uppercase letter', test: (pw) => /[A-Z]/.test(pw) },
  { label: 'One number', test: (pw) => /[0-9]/.test(pw) },
  { label: 'One special character', test: (pw) => /[^A-Za-z0-9]/.test(pw) },
]

/** Per-rule pass/fail status, for rendering a live checklist. */
export function evaluatePassword(password: string): PasswordRuleStatus[] {
  return RULES.map((rule) => ({ label: rule.label, met: rule.test(password) }))
}

/** True when the password satisfies every rule in the policy. */
export function isPasswordValid(password: string): boolean {
  return RULES.every((rule) => rule.test(password))
}
