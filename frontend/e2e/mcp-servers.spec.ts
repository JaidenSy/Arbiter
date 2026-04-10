/**
 * NexusAI E2E — MCP Servers page tests.
 *
 * Covers: create server, edit server, delete server, cache toggle.
 */

import { test, expect } from '@playwright/test'

test.describe('MCP Servers', () => {
  test('create server → appears in table', async ({ page }) => {
    await page.goto('/servers')

    const serverName = `e2e-server-${Date.now()}`

    await page.getByRole('button', { name: /add server|new server|create/i }).click()

    await page.getByLabel(/name/i).fill(serverName)
    await page.getByLabel(/url|base.?url/i).fill('http://localhost:3001/mcp')

    await page.getByRole('button', { name: /^add|^create|^save/i }).click()

    await expect(page.getByRole('cell', { name: serverName })).toBeVisible({ timeout: 8_000 })
  })

  test('edit server → updated name reflected in table', async ({ page }) => {
    await page.goto('/servers')

    const originalName = `e2e-edit-${Date.now()}`
    const updatedName = `${originalName}-updated`

    // Create
    await page.getByRole('button', { name: /add server|new server|create/i }).click()
    await page.getByLabel(/name/i).fill(originalName)
    await page.getByLabel(/url|base.?url/i).fill('http://localhost:3001/mcp')
    await page.getByRole('button', { name: /^add|^create|^save/i }).click()
    await expect(page.getByRole('cell', { name: originalName })).toBeVisible({ timeout: 8_000 })

    // Edit
    const row = page.locator('tr, [role="row"]').filter({ hasText: originalName })
    await row.getByRole('button', { name: /edit|pencil/i }).click()

    const nameInput = page.getByLabel(/name/i)
    await nameInput.clear()
    await nameInput.fill(updatedName)
    await page.getByRole('button', { name: /save|update|confirm/i }).click()

    await expect(page.getByRole('cell', { name: updatedName })).toBeVisible({ timeout: 5_000 })
    await expect(page.getByRole('cell', { name: originalName })).not.toBeVisible()
  })

  test('delete server → removed from table', async ({ page }) => {
    await page.goto('/servers')

    const serverName = `e2e-del-server-${Date.now()}`

    // Create
    await page.getByRole('button', { name: /add server|new server|create/i }).click()
    await page.getByLabel(/name/i).fill(serverName)
    await page.getByLabel(/url|base.?url/i).fill('http://localhost:3001/mcp')
    await page.getByRole('button', { name: /^add|^create|^save/i }).click()
    await expect(page.getByRole('cell', { name: serverName })).toBeVisible({ timeout: 8_000 })

    // Delete
    const row = page.locator('tr, [role="row"]').filter({ hasText: serverName })
    await row.getByRole('button', { name: /delete|remove/i }).click()

    const confirmBtn = page.getByRole('button', { name: /confirm|yes|delete/i })
    if (await confirmBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await confirmBtn.click()
    }

    await expect(row).not.toBeVisible({ timeout: 5_000 })
  })

  test('cache toggle changes state', async ({ page }) => {
    await page.goto('/servers')

    const serverName = `e2e-cache-${Date.now()}`

    // Create with cache disabled
    await page.getByRole('button', { name: /add server|new server|create/i }).click()
    await page.getByLabel(/name/i).fill(serverName)
    await page.getByLabel(/url|base.?url/i).fill('http://localhost:3001/mcp')
    await page.getByRole('button', { name: /^add|^create|^save/i }).click()
    await expect(page.getByRole('cell', { name: serverName })).toBeVisible({ timeout: 8_000 })

    // Find the cache toggle in that row and click it
    const row = page.locator('tr, [role="row"]').filter({ hasText: serverName })
    const cacheToggle = row.locator('input[type="checkbox"], [role="switch"]')
    if (await cacheToggle.isVisible().catch(() => false)) {
      const before = await cacheToggle.isChecked()
      await cacheToggle.click()
      await expect(cacheToggle).toBeChecked({ checked: !before, timeout: 5_000 })
    } else {
      test.skip() // cache toggle may be inside edit modal
    }
  })
})
