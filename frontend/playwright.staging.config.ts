/**
 * Playwright config for running E2E tests against the staging environment.
 *
 * Usage:
 *   E2E_EMAIL=you@example.com E2E_PASSWORD=yourpass \
 *   npx playwright test --config=playwright.staging.config.ts
 *
 * Required env vars:
 *   E2E_EMAIL      — email of a pre-existing staging account
 *   E2E_PASSWORD   — password for that account
 *
 * Optional:
 *   STAGING_URL    — frontend base URL  (default: https://staging.arbiterai.dev)
 *   API_URL        — backend API URL    (default: https://api.arbiterai.dev/api/v1)
 */

import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: true,
  retries: 1,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report-staging' }]],

  use: {
    baseURL: process.env.STAGING_URL ?? 'https://staging.arbiterai.dev',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 20_000,
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'staging-setup',
      testMatch: '**/staging.setup.ts',
    },
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'e2e/.auth/staging-user.json',
      },
      dependencies: ['staging-setup'],
    },
  ],
})
