/**
 * Arbiter E2E — UI polish and defensive rendering tests.
 *
 * Covers: error boundary recovery, copy feedback, wildcard permission badge,
 *         tour fires only once, empty states on fresh pages, confirmation
 *         dialogs on destructive actions, API key "not shown again" warning.
 */

import { test, expect } from '@playwright/test'

test.describe('Copy Button', () => {
  test('copying agent API key shows "Copied!" feedback', async ({ page }) => {
    await page.goto('/agents')

    // Create a fresh agent to get the API key modal
    const agentName = `e2e-copy-${Date.now()}`
    await page.getByRole('button', { name: /new agent|add agent|create/i }).click()
    await page.getByLabel(/name/i).fill(agentName)
    await page.getByRole('button', { name: /^create|^add|^save/i }).click()

    // Key modal opens
    await expect(page.getByText(/nxai_/)).toBeVisible({ timeout: 8_000 })

    // Click copy button — should switch to "Copied!"
    const copyBtn = page.getByRole('button', { name: /^copy$/i })
    await copyBtn.click()
    await expect(page.getByRole('button', { name: /copied/i })).toBeVisible({ timeout: 3_000 })

    // Reverts to "Copy" after 2s
    await expect(page.getByRole('button', { name: /^copy$/i })).toBeVisible({ timeout: 4_000 })

    // Dismiss
    await page.getByRole('button', { name: /dismiss|done|close/i }).click()
  })

  test('"key not shown again" warning visible in API key modal', async ({ page }) => {
    await page.goto('/agents')

    const agentName = `e2e-warning-${Date.now()}`
    await page.getByRole('button', { name: /new agent|add agent|create/i }).click()
    await page.getByLabel(/name/i).fill(agentName)
    await page.getByRole('button', { name: /^create|^add|^save/i }).click()

    await expect(page.getByText(/nxai_/)).toBeVisible({ timeout: 8_000 })
    await expect(page.getByText(/not be shown again|copy it now|won't be shown/i)).toBeVisible()

    await page.getByRole('button', { name: /dismiss|done|close/i }).click()
  })
})

test.describe('Wildcard Permission Badge', () => {
  test('tool_name="*" renders amber warning badge, not plain text', async ({ page }) => {
    await page.goto('/permissions')

    // Grant a wildcard permission if none exist — or just check existing ones
    const wildcardBadge = page.getByText('all tools')
    if (!(await wildcardBadge.isVisible({ timeout: 3_000 }).catch(() => false))) {
      test.skip() // no wildcard perms in this env — skip visual check
      return
    }

    // Badge should be warning-colored (amber) not muted
    const badge = page.locator('span', { hasText: 'all tools' }).first()
    await expect(badge).toBeVisible()

    // Check it has a warning-related class (not the muted/italic style)
    const classList = await badge.getAttribute('class') ?? ''
    expect(classList).toMatch(/warning/)
  })
})

test.describe('Confirmation Dialogs', () => {
  test('agent deactivate prompts confirmation dialog', async ({ page }) => {
    await page.goto('/agents')

    const agentName = `e2e-confirm-${Date.now()}`
    await page.getByRole('button', { name: /new agent|add agent|create/i }).click()
    await page.getByLabel(/name/i).fill(agentName)
    await page.getByRole('button', { name: /^create|^add|^save/i }).click()
    await expect(page.getByText(/nxai_/)).toBeVisible({ timeout: 8_000 })
    await page.getByRole('button', { name: /dismiss|done|close/i }).click()

    // Click delete on the newly created agent
    const row = page.locator('tr, [role="row"]').filter({ hasText: agentName })
    await row.getByRole('button', { name: /delete|deactivate|remove/i }).click()

    // Confirmation dialog must appear
    await expect(page.getByRole('dialog').or(page.getByText(/cannot be undone|are you sure/i))).toBeVisible({ timeout: 5_000 })

    // Cancel it
    await page.getByRole('button', { name: /cancel|keep/i }).click()

    // Agent still in table
    await expect(row).toBeVisible()
  })

  test('vault secret delete prompts confirmation', async ({ page }) => {
    await page.goto('/vault')

    const secretName = `E2E_CONFIRM_${Date.now()}`
    await page.getByRole('button', { name: /add secret|new secret|create/i }).click()
    await page.getByLabel(/name|key/i).fill(secretName)
    await page.getByLabel(/value/i).fill('confirm-test-value')
    await page.getByRole('button', { name: /^add|^create|^save/i }).click()
    await expect(page.getByText(secretName)).toBeVisible({ timeout: 8_000 })

    const row = page.locator('tr, li, [role="row"]').filter({ hasText: secretName })
    await row.getByRole('button', { name: /delete|remove/i }).click()

    // Confirmation dialog appears
    await expect(page.getByRole('dialog').or(page.getByText(/cannot be undone|are you sure/i))).toBeVisible({ timeout: 5_000 })

    // Confirm deletion this time
    await page.getByRole('button', { name: /confirm|yes|delete/i }).click()
    await expect(page.getByText(secretName)).not.toBeVisible({ timeout: 5_000 })
  })
})

test.describe('Tour', () => {
  test('tour does not re-appear after it has been seen', async ({ page }) => {
    await page.goto('/')

    // Set the seen flag directly (simulate having already seen it)
    await page.evaluate(() => localStorage.setItem('arbiter_tour_seen_v1', '1'))
    await page.reload()

    // Tour overlay/popover should NOT appear
    await page.waitForTimeout(1_500)
    const tourOverlay = page.locator('.driver-overlay, .driver-popover')
    await expect(tourOverlay).not.toBeVisible()
  })
})

test.describe('Error Boundary', () => {
  test('app renders normally — error boundary is not triggered', async ({ page }) => {
    await page.goto('/')

    // Error screen should NOT be visible on normal load
    await expect(page.getByText(/something went wrong/i)).not.toBeVisible({ timeout: 5_000 })
    await expect(page.getByText(/back to dashboard/i)).not.toBeVisible()
  })
})

test.describe('Vault — Secret Name Validation', () => {
  test('secret name with dashes shows validation error', async ({ page }) => {
    await page.goto('/vault')

    await page.getByRole('button', { name: /add secret|new secret|create/i }).click()
    await page.getByLabel(/name|key/i).fill('invalid-name-with-dashes')
    await page.getByLabel(/value/i).fill('some-value')
    await page.getByRole('button', { name: /^add|^create|^save/i }).click()

    // Should show a validation error about the name format
    await expect(page.getByText(/letters.*numbers.*underscore|invalid.*name|alphanumeric/i)).toBeVisible({ timeout: 5_000 })
  })

  test('secret name with dots shows validation error', async ({ page }) => {
    await page.goto('/vault')

    await page.getByRole('button', { name: /add secret|new secret|create/i }).click()
    await page.getByLabel(/name|key/i).fill('my.secret')
    await page.getByLabel(/value/i).fill('some-value')
    await page.getByRole('button', { name: /^add|^create|^save/i }).click()

    await expect(page.getByText(/letters.*numbers.*underscore|invalid.*name|alphanumeric/i)).toBeVisible({ timeout: 5_000 })
  })

  test('valid secret name with underscores passes', async ({ page }) => {
    await page.goto('/vault')

    const secretName = `VALID_SECRET_${Date.now()}`
    await page.getByRole('button', { name: /add secret|new secret|create/i }).click()
    await page.getByLabel(/name|key/i).fill(secretName)
    await page.getByLabel(/value/i).fill('valid-value')
    await page.getByRole('button', { name: /^add|^create|^save/i }).click()

    await expect(page.getByText(secretName)).toBeVisible({ timeout: 8_000 })

    // Cleanup
    const row = page.locator('tr, li, [role="row"]').filter({ hasText: secretName })
    await row.getByRole('button', { name: /delete|remove/i }).click()
    const confirm = page.getByRole('button', { name: /confirm|yes|delete/i })
    if (await confirm.isVisible({ timeout: 2_000 }).catch(() => false)) await confirm.click()
  })
})

test.describe('Auth Guard', () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  const protectedRoutes = ['/agents', '/mcp-servers', '/permissions', '/vault', '/sessions', '/settings', '/account', '/organization']

  for (const route of protectedRoutes) {
    test(`unauthenticated visit to ${route} → redirect to /login`, async ({ page }) => {
      await page.goto(route)
      await expect(page).toHaveURL(/\/login/, { timeout: 8_000 })
    })
  }
})
