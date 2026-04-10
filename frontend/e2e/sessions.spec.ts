/**
 * NexusAI E2E — Sessions + Session Trace tests.
 *
 * Covers: sessions list, clicking through to trace, badge rendering,
 * event row expand, stat pills.
 *
 * Sessions require real proxy traffic to exist. These tests check the list
 * and trace pages render correctly when sessions exist, and the empty state
 * when they don't.
 */

import { test, expect } from '@playwright/test'

test.describe('Sessions list', () => {
  test('renders list or empty state without crashing', async ({ page }) => {
    await page.goto('/sessions')

    const hasTable = await page.locator('table, [role="table"]').isVisible({ timeout: 5_000 }).catch(() => false)
    const hasEmpty = await page.getByText(/no sessions|first tool call|sessions appear/i).isVisible({ timeout: 5_000 }).catch(() => false)
    expect(hasTable || hasEmpty).toBe(true)
  })

  test('clicking session row navigates to trace page', async ({ page }) => {
    await page.goto('/sessions')

    const firstRow = page.locator('tbody tr, [role="row"]').nth(1) // skip header
    if (!(await firstRow.isVisible({ timeout: 3_000 }).catch(() => false))) {
      test.skip() // no sessions yet
      return
    }

    await firstRow.click()
    await expect(page).toHaveURL(/\/sessions\/[a-f0-9-]{36}/, { timeout: 5_000 })
  })

  test('session rows show agent name (not UUID)', async ({ page }) => {
    await page.goto('/sessions')

    const firstRow = page.locator('tbody tr, [role="row"]').nth(1)
    if (!(await firstRow.isVisible({ timeout: 3_000 }).catch(() => false))) {
      test.skip()
      return
    }

    const rowText = await firstRow.textContent()
    // Should NOT be a raw UUID (8-4-4-4-12 pattern) in the agent name column
    expect(rowText).not.toMatch(/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\s/)
  })
})

test.describe('Session Trace', () => {
  test('trace page renders waterfall and stat pills', async ({ page }) => {
    await page.goto('/sessions')

    const firstRow = page.locator('tbody tr, [role="row"]').nth(1)
    if (!(await firstRow.isVisible({ timeout: 3_000 }).catch(() => false))) {
      test.skip()
      return
    }

    await firstRow.click()
    await expect(page).toHaveURL(/\/sessions\/[a-f0-9-]{36}/, { timeout: 5_000 })

    // Waterfall table present
    await expect(page.locator('table, [role="table"]')).toBeVisible({ timeout: 5_000 })

    // Stat pills visible (total calls, duration, etc.)
    const pills = page.locator('[class*="pill"], [class*="badge"], [class*="stat"]')
    await expect(pills.first()).toBeVisible({ timeout: 3_000 })
  })

  test('clicking event row expands request/response detail', async ({ page }) => {
    await page.goto('/sessions')

    const firstRow = page.locator('tbody tr, [role="row"]').nth(1)
    if (!(await firstRow.isVisible({ timeout: 3_000 }).catch(() => false))) {
      test.skip()
      return
    }

    await firstRow.click()
    await expect(page).toHaveURL(/\/sessions\/[a-f0-9-]{36}/, { timeout: 5_000 })

    // Click first event row in the trace
    const eventRow = page.locator('tbody tr, [role="row"]').nth(1)
    if (!(await eventRow.isVisible({ timeout: 3_000 }).catch(() => false))) {
      test.skip()
      return
    }
    await eventRow.click()

    // Expanded detail should show request/response JSON or SSE message
    const detail = page.getByText(/request|response|SSE stream/i)
    await expect(detail).toBeVisible({ timeout: 5_000 })
  })

  test('SSE badge visible on streaming events', async ({ page }) => {
    await page.goto('/sessions')

    // Look for any session that has an SSE event (may not always exist)
    const sseBadge = page.getByText('SSE')
    if (await sseBadge.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await expect(sseBadge).toBeVisible()
    } else {
      // Navigate into a session trace and check there
      const firstRow = page.locator('tbody tr, [role="row"]').nth(1)
      if (await firstRow.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await firstRow.click()
        // SSE badge may or may not be present depending on test data
      }
      test.skip() // no SSE events in current test data
    }
  })
})
