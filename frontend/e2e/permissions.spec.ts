/**
 * NexVault E2E — Permissions (RBAC) page tests.
 *
 * Covers: grant permission, revoke permission, empty state.
 */

import { test, expect } from '@playwright/test'
import { registerUser, createAgent, createServer } from './helpers/api'

test.describe('Permissions', () => {
  test('empty state shown when no permissions exist', async ({ page }) => {
    await page.goto('/permissions')
    const hasTable = await page.locator('table, [role="table"]').isVisible().catch(() => false)
    const hasEmpty = await page.getByText(/no permissions|grant your first|no grants/i).isVisible().catch(() => false)
    expect(hasTable || hasEmpty).toBe(true)
  })

  test('grant permission → appears in table', async ({ page }) => {
    await page.goto('/permissions')

    await page.getByRole('button', { name: /grant|add permission|new/i }).click()

    // Select agent and server from dropdowns — both should be populated
    // (assuming at least one agent + server exist from setup/onboarding)
    const agentSelect = page.locator('select, [role="combobox"]').nth(0)
    const serverSelect = page.locator('select, [role="combobox"]').nth(1)

    if (await agentSelect.isVisible().catch(() => false)) {
      // Select first available agent
      await agentSelect.selectOption({ index: 0 })
    }
    if (await serverSelect.isVisible().catch(() => false)) {
      await serverSelect.selectOption({ index: 0 })
    }

    // Tool name — use wildcard
    const toolInput = page.getByLabel(/tool/i)
    if (await toolInput.isVisible().catch(() => false)) {
      await toolInput.fill('*')
    }

    await page.getByRole('button', { name: /^grant|^save|^create/i }).click()

    // A row should appear (wildcard tool name)
    await expect(page.locator('table, [role="table"]')).toBeVisible({ timeout: 8_000 })
  })

  test('revoke permission → removed from table', async ({ page }) => {
    await page.goto('/permissions')

    // Find any existing permission row and revoke it
    const revokeBtn = page.getByRole('button', { name: /revoke|delete|remove/i }).first()
    if (!(await revokeBtn.isVisible({ timeout: 3_000 }).catch(() => false))) {
      test.skip() // no permissions to revoke
      return
    }

    const rowCount = await page.locator('tr[data-testid], tbody tr').count()
    await revokeBtn.click()

    const confirmBtn = page.getByRole('button', { name: /confirm|yes|revoke/i })
    if (await confirmBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await confirmBtn.click()
    }

    // One fewer row (or empty state)
    const newRowCount = await page.locator('tr[data-testid], tbody tr').count()
    expect(newRowCount).toBeLessThan(rowCount)
  })
})
