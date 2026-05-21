/**
 * Arbiter E2E — Staging auth setup.
 *
 * Logs in with pre-existing staging credentials (E2E_EMAIL / E2E_PASSWORD).
 * Saves browser storage state so all subsequent tests skip the login flow.
 *
 * Unlike auth.setup.ts this does NOT register a new user — staging has a
 * real Stripe account and real org data we don't want to pollute.
 */

import { test as setup, expect } from '@playwright/test'
import path from 'path'

const AUTH_FILE = path.join(__dirname, '.auth/staging-user.json')

const EMAIL    = process.env.E2E_EMAIL    ?? (() => { throw new Error('E2E_EMAIL not set') })()
const PASSWORD = process.env.E2E_PASSWORD ?? (() => { throw new Error('E2E_PASSWORD not set') })()

setup('authenticate staging user', async ({ page }) => {
  await page.goto('/login')

  await page.getByLabel(/email/i).fill(EMAIL)
  await page.getByLabel(/password/i).fill(PASSWORD)
  await page.getByRole('button', { name: /sign in|log in/i }).click()

  // Must land on dashboard or root (tour may appear — dismiss it)
  await expect(page).toHaveURL(/\/(dashboard|\s*)?$/, { timeout: 15_000 })

  // Dismiss tour if it appears
  const tourClose = page.locator('.driver-popover-close-btn, [aria-label*="close"], button:has-text("Skip")').first()
  if (await tourClose.isVisible({ timeout: 2_000 }).catch(() => false)) {
    await tourClose.click()
  }

  await page.context().storageState({ path: AUTH_FILE })
})
