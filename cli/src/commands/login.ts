import { Command } from 'commander'
import { deviceFlow } from '../lib/auth.js'
import { get } from '../lib/api.js'
import { setConfig } from '../lib/config.js'
import { printSuccess } from '../lib/output.js'
import type { MeResponse } from '../types/index.js'

export function registerLogin(program: Command): void {
  program
    .command('login')
    .description('Authenticate with Arbiter via browser')
    .action(async () => {
      await deviceFlow()

      // Fetch user info and persist email
      try {
        const me = await get<MeResponse>('/api/v1/auth/me')
        setConfig({ user_email: me.email })
        printSuccess(`Logged in as ${me.email} (org: ${me.org_id})`)
      } catch {
        // Login succeeded even if /me fails for some reason
        printSuccess('Logged in successfully.')
      }
    })
}
