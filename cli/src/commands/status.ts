import { Command } from 'commander'
import { get } from '../lib/api.js'
import { getConfig, resolveApiUrl } from '../lib/config.js'
import chalk from 'chalk'
import type { MeResponse, HealthResponse } from '../types/index.js'

export function registerStatus(program: Command): void {
  program
    .command('status')
    .description('Show current auth state and gateway health')
    .option('--json', 'Output raw JSON')
    .action(async (opts: { json?: boolean }) => {
      const cfg = getConfig()
      const apiUrl = resolveApiUrl()

      if (!cfg?.access_token) {
        if (opts.json) {
          console.log(JSON.stringify({ logged_in: false, api_url: apiUrl }))
        } else {
          console.log('Not logged in. Run `arbiter login`.')
        }
        return
      }

      // Check gateway health (no auth needed)
      let gatewayStatus = 'unknown'
      try {
        const health = await get<HealthResponse>('/health')
        gatewayStatus = health.status
      } catch {
        gatewayStatus = 'unreachable'
      }

      // Check current user
      let me: MeResponse | null = null
      try {
        me = await get<MeResponse>('/api/v1/auth/me')
      } catch {
        console.error('Session expired. Run `arbiter login`.')
        process.exit(1)
      }

      if (opts.json) {
        console.log(
          JSON.stringify({
            logged_in: true,
            email: me?.email ?? null,
            org_id: me?.org_id ?? cfg.org_id,
            api_url: apiUrl,
            gateway_status: gatewayStatus,
          })
        )
        return
      }

      console.log(chalk.green('Logged in'))
      console.log(`  Email:          ${me?.email ?? '(unknown)'}`)
      console.log(`  Org ID:         ${me?.org_id ?? cfg.org_id}`)
      console.log(`  Plan:           ${me?.org_plan ?? '(unknown)'}`)
      console.log(`  API:            ${apiUrl}`)
      console.log(`  Gateway status: ${gatewayStatus === 'ok' ? chalk.green(gatewayStatus) : chalk.yellow(gatewayStatus)}`)
    })
}
