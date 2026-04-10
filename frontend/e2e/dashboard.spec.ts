/**
 * NexusAI E2E — Dashboard tests.
 *
 * Covers: stat cards render, chart renders, session row click navigates
 * to trace, UsageStrip visible.
 */

import { test, expect } from '@playwright/test'

test.describe('Dashboard', () => {
  test('renders 4 stat cards', async ({ page }) => {
    await page.goto('/dashboard')

    // 4 stat cards: Agents, MCP Servers, Tool Calls Today, Cache Hit Rate
    await expect(page.getByText(/agents/i).first()).toBeVisible({ timeout: 8_000 })
    await expect(page.getByText(/servers?/i).first()).toBeVisible()
    await expect(page.getByText(/tool calls/i).first()).toBeVisible()
    await expect(page.getByText(/cache/i).first()).toBeVisible()
  })

  test('history chart renders with period toggle', async ({ page }) => {
    await page.goto('/dashboard')

    // Chart area should be present
    const chart = page.locator('[class*="recharts"], svg, canvas').first()
    await expect(chart).toBeVisible({ timeout: 8_000 })

    // Period toggle buttons
    const toggle7d = page.getByRole('button', { name: /7d|7 day/i })
    const toggle24h = page.getByRole('button', { name: /24h|24 hour/i })

    if (await toggle7d.isVisible().catch(() => false)) {
      await toggle24h.click()
      await expect(chart).toBeVisible()
      await toggle7d.click()
      await expect(chart).toBeVisible()
    }
  })

  test('session row click → navigates to trace', async ({ page }) => {
    await page.goto('/dashboard')

    // Recent sessions table — skip if empty
    const sessionRow = page.locator('tbody tr, [role="row"]').nth(1)
    if (!(await sessionRow.isVisible({ timeout: 5_000 }).catch(() => false))) {
      test.skip() // no sessions yet
      return
    }

    await sessionRow.click()
    await expect(page).toHaveURL(/\/sessions\/[a-f0-9-]{36}/, { timeout: 5_000 })
  })

  test('session rows show agent names (not raw UUIDs)', async ({ page }) => {
    await page.goto('/dashboard')

    const sessionRow = page.locator('tbody tr, [role="row"]').nth(1)
    if (!(await sessionRow.isVisible({ timeout: 5_000 }).catch(() => false))) {
      test.skip()
      return
    }

    const rowText = await sessionRow.textContent() ?? ''
    // Agent name cell should not be a bare UUID
    const uuidPattern = /[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/
    const cells = await sessionRow.locator('td').allTextContents()
    // First text cell (agent name) should not be a UUID alone
    const agentCell = cells[0] ?? ''
    expect(agentCell.trim()).not.toMatch(/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/)
  })

  test('UsageStrip visible with plan name', async ({ page }) => {
    await page.goto('/dashboard')

    // UsageStrip shows plan + tool call count
    const strip = page.getByText(/free plan|pro plan|enterprise plan/i)
    await expect(strip).toBeVisible({ timeout: 8_000 })
  })
})
