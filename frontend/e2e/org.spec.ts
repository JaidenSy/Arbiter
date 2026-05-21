/**
 * Arbiter E2E — Organization / Members page tests.
 *
 * Covers: members list renders, current user present, invite flow UI,
 *         pending invites list, cancel invite.
 */

import { test, expect } from '@playwright/test'

test.describe('Org — Members list', () => {
  test('members page loads and shows at least one member', async ({ page }) => {
    await page.goto('/organization')
    await expect(page.locator('table, [role="table"]')).toBeVisible({ timeout: 10_000 })

    // At least the current user should appear
    const rows = page.locator('tbody tr, [role="row"]')
    await expect(rows.first()).toBeVisible()
  })

  test('current user email appears in the list', async ({ page }) => {
    await page.goto('/organization')

    const email = process.env.E2E_EMAIL ?? ''
    if (email) {
      await expect(page.getByText(email)).toBeVisible({ timeout: 8_000 })
    }
  })

  test('each member row shows role badge', async ({ page }) => {
    await page.goto('/organization')

    await expect(page.locator('table, [role="table"]')).toBeVisible({ timeout: 10_000 })

    const roleBadge = page.getByText(/owner|admin|member/i).first()
    await expect(roleBadge).toBeVisible()
  })
})

test.describe('Org — Invite flow', () => {
  test('invite button visible for owner/admin', async ({ page }) => {
    await page.goto('/organization')
    const inviteBtn = page.getByRole('button', { name: /invite|send invite/i })
    await expect(inviteBtn).toBeVisible({ timeout: 8_000 })
  })

  test('invite modal opens and has email + role fields', async ({ page }) => {
    await page.goto('/organization')

    await page.getByRole('button', { name: /invite|send invite/i }).click()

    await expect(page.getByLabel(/email/i)).toBeVisible({ timeout: 5_000 })
    await expect(page.getByLabel(/role/i).or(page.getByRole('combobox'))).toBeVisible()
  })

  test('invite with invalid email → validation error', async ({ page }) => {
    await page.goto('/organization')

    await page.getByRole('button', { name: /invite|send invite/i }).click()
    await page.getByLabel(/email/i).fill('not-an-email')
    await page.getByRole('button', { name: /^send|^invite|^submit/i }).click()

    await expect(page.getByText(/invalid email|valid email/i)).toBeVisible({ timeout: 5_000 })
  })

  test('invite to non-existent domain → sends invite (or shows pending)', async ({ page }) => {
    await page.goto('/organization')

    const uniqueEmail = `e2e-invite-${Date.now()}@arbiter-nonexistent.test`

    await page.getByRole('button', { name: /invite|send invite/i }).click()
    await page.getByLabel(/email/i).fill(uniqueEmail)

    // Select member role
    const roleSelect = page.getByLabel(/role/i).or(page.getByRole('combobox')).first()
    if (await roleSelect.isVisible().catch(() => false)) {
      await roleSelect.selectOption('member')
    }

    await page.getByRole('button', { name: /^send|^invite|^submit/i }).click()

    // Should appear in pending invites or show success
    await expect(
      page.getByText(uniqueEmail).or(page.getByText(/sent|pending|invited/i))
    ).toBeVisible({ timeout: 8_000 })

    // Clean up — cancel the invite
    const cancelBtn = page.locator('tr, [role="row"]')
      .filter({ hasText: uniqueEmail })
      .getByRole('button', { name: /cancel|delete|remove/i })
    if (await cancelBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await cancelBtn.click()
      const confirm = page.getByRole('button', { name: /confirm|yes/i })
      if (await confirm.isVisible({ timeout: 2_000 }).catch(() => false)) await confirm.click()
    }
  })
})

test.describe('Org — Pending invites', () => {
  test('pending invites section renders (may be empty)', async ({ page }) => {
    await page.goto('/organization')

    const inviteSection = page.getByText(/pending invites|invitations/i)
    await expect(inviteSection).toBeVisible({ timeout: 8_000 })
  })
})
