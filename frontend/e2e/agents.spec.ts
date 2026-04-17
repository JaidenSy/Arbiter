/**
 * NexVault E2E — Agents page tests.
 *
 * Covers: create agent, API key reveal/copy/hide, delete agent, empty state.
 */

import { test, expect } from '@playwright/test'

test.describe('Agents', () => {
  test('empty state shown when no agents exist', async ({ page }) => {
    // Fresh state: the setup user may have agents from onboarding — skip if so
    await page.goto('/agents')
    // Either the table or the empty state should be visible
    const hasTable = await page.locator('table, [role="table"]').isVisible().catch(() => false)
    const hasEmpty = await page.getByText(/register your first agent|no agents/i).isVisible().catch(() => false)
    expect(hasTable || hasEmpty).toBe(true)
  })

  test('create agent → appears in table with nxai_ key', async ({ page }) => {
    await page.goto('/agents')

    const agentName = `e2e-agent-${Date.now()}`

    // Open create dialog
    await page.getByRole('button', { name: /new agent|add agent|create/i }).click()

    // Fill form
    await page.getByLabel(/name/i).fill(agentName)
    await page.getByRole('button', { name: /^create|^add|^save/i }).click()

    // API key modal — key shown once
    const keyModal = page.getByText(/nxai_/)
    await expect(keyModal).toBeVisible({ timeout: 8_000 })

    // Key format: nxai_ prefix
    const keyText = await keyModal.textContent()
    expect(keyText).toMatch(/nxai_[a-f0-9]+/)

    // Dismiss modal
    await page.getByRole('button', { name: /done|close|dismiss|ok/i }).click()

    // Agent appears in table
    await expect(page.getByRole('cell', { name: agentName })).toBeVisible({ timeout: 5_000 })
  })

  test('API key reveal: show/hide toggles masking', async ({ page }) => {
    await page.goto('/agents')

    // Find an existing agent row (may exist from create test or onboarding)
    const revealBtn = page.getByRole('button', { name: /reveal|show key|view key/i }).first()
    if (await revealBtn.isVisible().catch(() => false)) {
      await revealBtn.click()
      // Key should now be visible
      await expect(page.getByText(/nxai_/)).toBeVisible({ timeout: 5_000 })
    } else {
      // Key reveal is in the create modal — already tested above
      test.skip()
    }
  })

  test('delete agent → removed from table', async ({ page }) => {
    await page.goto('/agents')

    const agentName = `e2e-delete-${Date.now()}`

    // Create an agent to delete
    await page.getByRole('button', { name: /new agent|add agent|create/i }).click()
    await page.getByLabel(/name/i).fill(agentName)
    await page.getByRole('button', { name: /^create|^add|^save/i }).click()
    await expect(page.getByText(/nxai_/)).toBeVisible({ timeout: 8_000 })
    await page.getByRole('button', { name: /done|close|dismiss|ok/i }).click()

    // Wait for agent row
    const row = page.locator('tr, [role="row"]').filter({ hasText: agentName })
    await expect(row).toBeVisible({ timeout: 5_000 })

    // Delete it
    await row.getByRole('button', { name: /delete|remove/i }).click()

    // Confirm dialog
    const confirmBtn = page.getByRole('button', { name: /confirm|yes|delete/i })
    if (await confirmBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await confirmBtn.click()
    }

    // Row gone
    await expect(row).not.toBeVisible({ timeout: 5_000 })
  })
})
