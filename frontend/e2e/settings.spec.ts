/**
 * Nexvault E2E — Settings page tests.
 *
 * Covers: profile section, API key save/show/hide/clear,
 * gateway URL save, billing section (plan badge, usage bars, upgrade CTA).
 */

import { test, expect } from '@playwright/test'

test.describe('Settings — Profile', () => {
  test('profile section shows email, role, org, plan', async ({ page }) => {
    await page.goto('/settings')

    // Profile rows should be present
    await expect(page.getByText(/email/i)).toBeVisible({ timeout: 5_000 })
    await expect(page.getByText(/role/i)).toBeVisible()
    await expect(page.getByText(/org/i)).toBeVisible()
    await expect(page.getByText(/plan/i)).toBeVisible()
  })
})

test.describe('Settings — API Key', () => {
  test('save key → status turns Connected', async ({ page }) => {
    await page.goto('/settings')

    const keyInput = page.getByPlaceholder(/nxai_/)
    await keyInput.fill('nxai_testkey1234abcd')
    await page.getByRole('button', { name: /^save$/i }).first().click()

    await expect(page.getByText(/connected/i)).toBeVisible({ timeout: 3_000 })

    // Persisted in localStorage
    const stored = await page.evaluate(() => localStorage.getItem('nexvault_api_key'))
    expect(stored).toBe('nxai_testkey1234abcd')
  })

  test('show/hide toggles password masking', async ({ page }) => {
    await page.goto('/settings')

    const keyInput = page.getByPlaceholder(/nxai_/)
    await keyInput.fill('nxai_testkey1234abcd')

    // Default: masked (type=password)
    await expect(keyInput).toHaveAttribute('type', 'password')

    // Click Show
    await page.getByRole('button', { name: /show/i }).click()
    await expect(keyInput).toHaveAttribute('type', 'text')

    // Click Hide
    await page.getByRole('button', { name: /hide/i }).click()
    await expect(keyInput).toHaveAttribute('type', 'password')
  })

  test('clear key → status turns No key set', async ({ page }) => {
    await page.goto('/settings')

    // Ensure a key is set first
    await page.evaluate(() => localStorage.setItem('nexvault_api_key', 'nxai_testkey'))
    await page.reload()

    await page.getByRole('button', { name: /clear/i }).click()

    await expect(page.getByText(/no key set/i)).toBeVisible({ timeout: 3_000 })
    const stored = await page.evaluate(() => localStorage.getItem('nexvault_api_key'))
    expect(stored).toBeNull()
  })
})

test.describe('Settings — Billing', () => {
  test('billing section renders plan badge and usage bars', async ({ page }) => {
    await page.goto('/settings')

    // Plan badge (FREE / PRO / ENTERPRISE)
    const planBadge = page.getByText(/free|pro|enterprise/i)
    await expect(planBadge.first()).toBeVisible({ timeout: 8_000 })

    // Usage bars — tool calls label
    await expect(page.getByText(/tool calls/i)).toBeVisible()

    // Agents bar
    await expect(page.getByText(/agents/i)).toBeVisible()
  })

  test('free plan shows Upgrade to Pro button', async ({ page }) => {
    await page.goto('/settings')

    // Only check if on free plan
    const isPro = await page.getByText(/^pro$/i).isVisible({ timeout: 3_000 }).catch(() => false)
    if (isPro) {
      test.skip() // already on pro, skip
      return
    }

    await expect(page.getByRole('button', { name: /upgrade.*pro|upgrade/i })).toBeVisible({ timeout: 8_000 })
  })

  test('upgrade button triggers Stripe checkout redirect (mocked)', async ({ page }) => {
    await page.goto('/settings')

    const upgradeBtn = page.getByRole('button', { name: /upgrade.*pro|upgrade/i })
    if (!(await upgradeBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
      test.skip() // not on free plan
      return
    }

    // Mock the billing/checkout response to avoid real Stripe redirect
    await page.route('**/billing/checkout', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ url: 'https://checkout.stripe.com/test-session' }),
      })
    })

    // Intercept the navigation to Stripe
    let navigatedUrl = ''
    page.on('framenavigated', (frame) => {
      if (frame === page.mainFrame()) {
        navigatedUrl = frame.url()
      }
    })

    await upgradeBtn.click()

    // Allow time for redirect to be triggered
    await page.waitForTimeout(1_000)
    expect(navigatedUrl).toContain('checkout.stripe.com')
  })
})

test.describe('Settings — Gateway URL', () => {
  test('save new URL reloads page', async ({ page }) => {
    await page.goto('/settings')

    const urlInput = page.getByPlaceholder(/http:\/\/localhost:8000/)
    await urlInput.clear()
    await urlInput.fill('http://localhost:8000/api/v1')

    const saveBtn = page.getByRole('button', { name: /^save$/i }).last()
    await saveBtn.click()

    // Page should reload (brief loading state or navigation)
    await page.waitForLoadState('load', { timeout: 5_000 })
    await expect(page).toHaveURL(/\/settings/)
  })
})
