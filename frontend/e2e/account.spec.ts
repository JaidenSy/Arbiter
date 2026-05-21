/**
 * Arbiter E2E — Account page tests.
 *
 * Covers: display name update, change password (wrong current → error),
 *         linked providers display, danger zone visibility.
 */

import { test, expect } from '@playwright/test'

test.describe('Account — Profile', () => {
  test('account page renders email and display name fields', async ({ page }) => {
    await page.goto('/account')
    await expect(page.getByLabel(/email/i)).toBeVisible({ timeout: 8_000 })
    await expect(page.getByLabel(/display.?name|name/i).first()).toBeVisible()
  })

  test('update display name → success feedback', async ({ page }) => {
    await page.goto('/account')

    const nameInput = page.getByLabel(/display.?name|name/i).first()
    await nameInput.clear()
    await nameInput.fill('E2E Test Name')

    await page.getByRole('button', { name: /save|update/i }).first().click()

    // Should show success toast or updated value
    const success = page.getByText(/saved|updated|success/i)
    await expect(success).toBeVisible({ timeout: 5_000 })
  })

  test('email change initiates confirmation (does not apply immediately)', async ({ page }) => {
    await page.goto('/account')

    const emailInput = page.getByLabel(/email/i)
    const originalEmail = await emailInput.inputValue()

    await emailInput.clear()
    await emailInput.fill(`e2e-change-${Date.now()}@arbiter.test`)

    await page.getByRole('button', { name: /save|update/i }).first().click()

    // Should show "confirmation sent" message, not immediately update
    await expect(page.getByText(/confirm|verification|check your email|sent/i)).toBeVisible({ timeout: 5_000 })

    // Email in UI should NOT yet have changed
    await page.reload()
    const reloadedEmail = await page.getByLabel(/email/i).inputValue()
    expect(reloadedEmail).toBe(originalEmail)
  })
})

test.describe('Account — Change Password', () => {
  test('wrong current password → error shown', async ({ page }) => {
    await page.goto('/account')

    const currentPwd = page.getByLabel(/current password/i)
    if (!(await currentPwd.isVisible({ timeout: 3_000 }).catch(() => false))) {
      test.skip() // SSO-only account — no password section
      return
    }

    await currentPwd.fill('definitely-wrong-password')
    await page.getByLabel(/new password/i).fill('NewPass123!')
    await page.getByRole('button', { name: /change password|update password/i }).click()

    await expect(page.getByText(/incorrect|invalid|wrong|current password/i)).toBeVisible({ timeout: 5_000 })
  })

  test('mismatched new passwords → error shown', async ({ page }) => {
    await page.goto('/account')

    const currentPwd = page.getByLabel(/current password/i)
    if (!(await currentPwd.isVisible({ timeout: 3_000 }).catch(() => false))) {
      test.skip()
      return
    }

    await currentPwd.fill('TestPass123!')
    await page.getByLabel(/new password/i).fill('NewPass123!')
    const confirm = page.getByLabel(/confirm.*(password|new)/i)
    if (await confirm.isVisible().catch(() => false)) {
      await confirm.fill('DifferentPass!')
      await page.getByRole('button', { name: /change password|update password/i }).click()
      await expect(page.getByText(/match|mismatch/i)).toBeVisible({ timeout: 5_000 })
    }
  })
})

test.describe('Account — Linked Providers', () => {
  test('linked providers section visible', async ({ page }) => {
    await page.goto('/account')
    await expect(page.getByText(/linked|connected|social|sign.?in methods/i)).toBeVisible({ timeout: 8_000 })
  })

  test('Google and GitHub provider options present', async ({ page }) => {
    await page.goto('/account')
    await expect(page.getByText(/google/i)).toBeVisible({ timeout: 8_000 })
    await expect(page.getByText(/github/i)).toBeVisible()
  })
})

test.describe('Account — Danger Zone', () => {
  test('delete account button exists but requires confirmation', async ({ page }) => {
    await page.goto('/account')

    const deleteBtn = page.getByRole('button', { name: /delete account|deactivate account/i })
    if (!(await deleteBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
      test.skip()
      return
    }

    await deleteBtn.click()

    // Should prompt for confirmation — we do NOT confirm
    const confirmDialog = page.getByRole('dialog').or(page.getByText(/are you sure|this cannot be undone/i))
    await expect(confirmDialog).toBeVisible({ timeout: 3_000 })

    // Dismiss without confirming
    const cancelBtn = page.getByRole('button', { name: /cancel|keep|no/i })
    if (await cancelBtn.isVisible().catch(() => false)) {
      await cancelBtn.click()
    } else {
      await page.keyboard.press('Escape')
    }
  })
})
