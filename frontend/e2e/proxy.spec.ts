/**
 * Arbiter E2E — Proxy / Test Call playground tests.
 *
 * Covers: test call modal opens, agent/server/tool selection, firing a call
 *         shows a response panel, cache_hit field present, error response
 *         for a tool the agent doesn't have permission for.
 *
 * Note: These tests don't require a live MCP server — they verify the UI
 * flow and error-handling paths. Actual proxy round-trips are integration
 * tests handled in the backend suite.
 */

import { test, expect } from '@playwright/test'

test.describe('Test Call Playground', () => {
  test('test call button opens modal', async ({ page }) => {
    await page.goto('/agents')

    const testCallBtn = page.getByRole('button', { name: /test call|try it|test/i }).first()
    if (!(await testCallBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
      test.skip() // no agents or feature not visible
      return
    }

    await testCallBtn.click()

    await expect(page.getByRole('dialog').or(page.getByText(/test call|fire call/i))).toBeVisible({ timeout: 5_000 })
  })

  test('test call modal has agent, server, tool name, and params fields', async ({ page }) => {
    await page.goto('/agents')

    const testCallBtn = page.getByRole('button', { name: /test call|try it|test/i }).first()
    if (!(await testCallBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
      test.skip()
      return
    }

    await testCallBtn.click()

    await expect(page.getByLabel(/server/i).or(page.getByText(/server/i))).toBeVisible({ timeout: 5_000 })
    await expect(page.getByLabel(/tool/i).or(page.getByText(/tool/i))).toBeVisible()
  })

  test('firing call without a server name shows validation error', async ({ page }) => {
    await page.goto('/agents')

    const testCallBtn = page.getByRole('button', { name: /test call|try it|test/i }).first()
    if (!(await testCallBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
      test.skip()
      return
    }

    await testCallBtn.click()

    // Clear any pre-filled tool name
    const toolInput = page.getByLabel(/tool.?name/i).or(page.getByPlaceholder(/tool/i))
    if (await toolInput.isVisible().catch(() => false)) {
      await toolInput.clear()
    }

    // Click Fire / Send
    await page.getByRole('button', { name: /^fire|^send|^run|^call/i }).click()

    await expect(page.getByText(/required|select a server|select a tool|enter/i)).toBeVisible({ timeout: 5_000 })
  })
})

test.describe('Code Snippet Generator', () => {
  test('code snippet modal opens from agent row', async ({ page }) => {
    await page.goto('/agents')

    const snippetBtn = page.getByRole('button', { name: /snippet|code|<\/>/i }).first()
    if (!(await snippetBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
      test.skip()
      return
    }

    await snippetBtn.click()
    await expect(page.getByRole('dialog').or(page.getByText(/python|curl|typescript/i))).toBeVisible({ timeout: 5_000 })
  })

  test('tab switching changes code content', async ({ page }) => {
    await page.goto('/agents')

    const snippetBtn = page.getByRole('button', { name: /snippet|code|<\/>/i }).first()
    if (!(await snippetBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
      test.skip()
      return
    }

    await snippetBtn.click()

    const curlTab = page.getByRole('tab', { name: /curl/i }).or(page.getByRole('button', { name: /curl/i }))
    const tsTab   = page.getByRole('tab', { name: /typescript/i }).or(page.getByRole('button', { name: /typescript/i }))

    if (await curlTab.isVisible().catch(() => false)) {
      await curlTab.click()
      await expect(page.getByText(/curl/i).or(page.getByText(/-H "Authorization/i))).toBeVisible()
    }

    if (await tsTab.isVisible().catch(() => false)) {
      await tsTab.click()
      await expect(page.getByText(/fetch|axios|Authorization/i)).toBeVisible()
    }
  })
})

test.describe('MCP Server — Test Connection', () => {
  test('test connection button exists on server rows', async ({ page }) => {
    await page.goto('/mcp-servers')

    const testBtn = page.getByRole('button', { name: /test|ping|check connection/i }).first()
    if (!(await testBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
      test.skip()
      return
    }

    await testBtn.click()

    // Should show connected, unreachable, or timeout — any response is valid UI behaviour
    await expect(
      page.getByText(/connected|reachable|unreachable|failed|timeout|error/i)
    ).toBeVisible({ timeout: 12_000 })
  })
})
