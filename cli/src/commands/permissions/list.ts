import { Command } from 'commander'
import { get } from '../../lib/api.js'
import { requireAuth } from '../../lib/config.js'
import { printTable } from '../../lib/output.js'
import { ApiError } from '../../lib/api.js'
import { printError } from '../../lib/output.js'
import type { PermissionPage } from '../../types/index.js'

export function registerPermissionsList(permissionsCmd: Command): void {
  permissionsCmd
    .command('list')
    .description('List permissions for an agent')
    .requiredOption('--agent <id>', 'Agent ID')
    .option('--json', 'Output raw JSON')
    .action(async (opts: { agent: string; json?: boolean }) => {
      requireAuth()

      let page: PermissionPage
      try {
        page = await get<PermissionPage>(`/api/v1/agents/${opts.agent}/permissions`)
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.status === 404) {
            printError('Agent not found.')
          }
          printError(`API error: ${err.detail}`)
        }
        throw err
      }

      if (opts.json) {
        console.log(JSON.stringify(page, null, 2))
        return
      }

      if (page.items.length === 0) {
        printTable(['Tool', 'Server ID', 'Granted At'], [])
        console.log('No permissions granted for this agent.')
        return
      }

      const rows = page.items.map((p) => [
        p.tool_name,
        p.mcp_server_id,
        formatDate(p.granted_at),
      ])

      printTable(['Tool', 'Server ID', 'Granted At'], rows)
    })
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toISOString().replace('T', ' ').slice(0, 16)
}
