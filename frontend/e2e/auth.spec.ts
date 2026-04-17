/**
 * NexVault E2E — Auth tests.
 *
 * Covers: login, logout, auth guard (unauthenticated redirect).
 * Registration is covered in auth.setup.ts.
 */

import { test, expect } from '@playwright/test'

// These tests intentionally run WITHOUT the shared auth state
// (they manage auth themselves)
test.use({ storageState: { cookies: [], origins: [] } })

test.describe('Login', () => {
  test('valid credentials → redirect to dashboard', async ({ page }) => {
    // Use env vars or defaults; in CI these should be the setup user's creds
    const email = process.env.E2E_EMAIL ?? 'e2e-user@nexvault.test'
    const password = process.env.E2E_PASSWORD ?? 'TestPass123!'

    await page.goto('/login')
    await page.getByLabel(/email/i).fill(email)
    await page.getByLabel(/password/i).fill(password)
    await page.getByRole('button', { name: /sign in|log in/i }).click()

    await expect(page).toHaveURL(/\/(dashboard)?$/, { timeout: 10_000 })
  })

  test('wrong password → error message shown', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel(/email/i).fill('wrong@nexvault.test')
    await page.getByLabel(/password/i).fill('wrongpassword')
    await page.getByRole('button', { name: /sign in|log in/i }).click()

    await expect(page.getByText(/invalid|incorrect|unauthorized/i)).toBeVisible({ timeout: 5_000 })
  })
})

test.describe('Auth guard', () => {
  test('unauthenticated visit to dashboard → redirect to login', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/login/, { timeout: 5_000 })
  })

  test('unauthenticated visit to agents → redirect to login', async ({ page }) => {
    await page.goto('/agents')
    await expect(page).toHaveURL(/\/login/, { timeout: 5_000 })
  })
})

test.describe('Logout', () => {
  // Re-use shared auth for logout test
  test.use({ storageState: 'e2e/.auth/user.json' })

  test('logout clears tokens and redirects to login', async ({ page }) => {
    await page.goto('/dashboard')

    // Find and click logout — button text varies by implementation
    const logoutBtn = page.getByRole('button', { name: /logout|sign out|log out/i })
    await expect(logoutBtn).toBeVisible({ timeout: 5_000 })
    await logoutBtn.click()

    await expect(page).toHaveURL(/\/login/, { timeout: 5_000 })

    // Tokens should be cleared
    const token = await page.evaluate(() => localStorage.getItem('nexvault_access_token'))
    expect(token).toBeNull()
  })
})
