/**
 * NexVault E2E — Auth setup.
 *
 * Registers a shared test user (once per test run), logs in via the UI,
 * and saves the browser storage state to e2e/.auth/user.json.
 * All subsequent test files load this state to skip the login flow.
 */

import { test as setup, expect } from '@playwright/test'
import path from 'path'

const AUTH_FILE = path.join(__dirname, '.auth/user.json')

// Stable test credentials — use unique email to avoid conflicts across runs
const EMAIL = `e2e-${process.env.TEST_RUN_ID ?? Date.now()}@nexvault.test`
const PASSWORD = 'TestPass123!'
const ORG_NAME = 'E2E Test Org'

setup('register and authenticate test user', async ({ page }) => {
  // Register via UI (also validates the register page works)
  await page.goto('/register')
  await page.getByLabel(/org.*name/i).fill(ORG_NAME)
  await page.getByLabel(/email/i).fill(EMAIL)
  await page.getByLabel(/password/i).fill(PASSWORD)
  await page.getByRole('button', { name: /register|sign up|create/i }).click()

  // After registration, should land on onboarding or dashboard
  await expect(page).toHaveURL(/\/(onboarding|dashboard|\s*)$/, { timeout: 10_000 })

  // Save auth state
  await page.context().storageState({ path: AUTH_FILE })
})
