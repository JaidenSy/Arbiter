/**
 * Arbiter E2E — Landing page tests (unauthenticated).
 *
 * Covers: hero copy, comparison table, pricing tiers, nav links,
 *         FAQ accordion, footer links.
 */

import { test, expect } from '@playwright/test'

test.use({ storageState: { cookies: [], origins: [] } })

test.describe('Landing — Hero', () => {
  test('problem-first headline visible', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText(/without guardrails/i)).toBeVisible({ timeout: 10_000 })
  })

  test('subheadline leads with shared credentials pain point', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText(/shared credentials/i)).toBeVisible()
  })

  test('"Get Started Free" CTA links to /register', async ({ page }) => {
    await page.goto('/')
    const cta = page.getByRole('link', { name: /get started free|start for free/i }).first()
    await expect(cta).toBeVisible()
    await expect(cta).toHaveAttribute('href', /\/register/)
  })

  test('"Sign In" nav link links to /login', async ({ page }) => {
    await page.goto('/')
    const link = page.getByRole('link', { name: /sign in/i }).first()
    await expect(link).toBeVisible()
    await expect(link).toHaveAttribute('href', /\/login/)
  })

  test('beta badge visible', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText(/now in beta/i)).toBeVisible()
  })
})

test.describe('Landing — Features section', () => {
  test('all 6 feature cards render', async ({ page }) => {
    await page.goto('/')
    const features = ['Agent Identity', 'Tool-Level Permissions', 'Encrypted Vault', 'Semantic Cache', 'Full Observability', 'MCP Native']
    for (const f of features) {
      await expect(page.getByText(f)).toBeVisible()
    }
  })
})

test.describe('Landing — Comparison table', () => {
  test('comparison section visible', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText(/how arbiter compares/i)).toBeVisible()
  })

  test('table has Arbiter, LiteLLM, Portkey, DIY columns', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('Arbiter')).toBeVisible()
    await expect(page.getByText('LiteLLM')).toBeVisible()
    await expect(page.getByText('Portkey')).toBeVisible()
    await expect(page.getByText('DIY')).toBeVisible()
  })

  test('cost row shows $0–$29/mo for Arbiter', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText(/\$0–\$29\/mo/)).toBeVisible()
  })

  test('per-agent identity row renders', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText(/per-agent identity/i)).toBeVisible()
  })
})

test.describe('Landing — Pricing', () => {
  test('three pricing tiers visible', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('Free')).toBeVisible()
    await expect(page.getByText('Pro')).toBeVisible()
    await expect(page.getByText('Enterprise')).toBeVisible()
  })

  test('Pro tier shows $29/mo', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('$29')).toBeVisible()
  })

  test('Pro tier is highlighted (most popular badge)', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText(/most popular/i)).toBeVisible()
  })

  test('free plan CTA links to /register', async ({ page }) => {
    await page.goto('/')
    const cta = page.getByRole('link', { name: /get started free/i }).last()
    await expect(cta).toHaveAttribute('href', /\/register/)
  })
})

test.describe('Landing — FAQ', () => {
  test('FAQ section present', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText(/common questions/i)).toBeVisible()
  })

  test('accordion expands on click', async ({ page }) => {
    await page.goto('/')
    const firstQuestion = page.getByText(/what is mcp/i)
    await expect(firstQuestion).toBeVisible()
    await firstQuestion.click()
    await expect(page.getByText(/model context protocol/i)).toBeVisible({ timeout: 3_000 })
  })

  test('accordion collapses on second click', async ({ page }) => {
    await page.goto('/')
    const firstQuestion = page.getByText(/what is mcp/i)
    await firstQuestion.click()
    await firstQuestion.click()
    await expect(page.getByText(/model context protocol/i)).not.toBeVisible({ timeout: 3_000 })
  })
})

test.describe('Landing — How It Works', () => {
  test('three numbered steps visible', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('01')).toBeVisible()
    await expect(page.getByText('02')).toBeVisible()
    await expect(page.getByText('03')).toBeVisible()
  })
})

test.describe('Landing — Footer', () => {
  test('footer renders API Docs link', async ({ page }) => {
    await page.goto('/')
    const apiDocs = page.getByRole('link', { name: /api docs/i })
    await expect(apiDocs).toBeVisible()
    await expect(apiDocs).toHaveAttribute('href', /\/docs/)
  })
})
