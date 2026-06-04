import { Command } from 'commander'
import { get } from '../../lib/api.js'
import { requireAuth } from '../../lib/config.js'
import { printTable } from '../../lib/output.js'
import type { AgentPage } from '../../types/index.js'

export function registerAgentList(agentCmd: Command): void {
  agentCmd
    .command('list')
    .description('List all agents in your org')
    .option('--json', 'Output raw JSON')
    .action(async (opts: { json?: boolean }) => {
      requireAuth()

      const page = await get<AgentPage>('/api/v1/agents', { skip: 0, limit: 200 })

      if (opts.json) {
        console.log(JSON.stringify(page, null, 2))
        return
      }

      if (page.items.length === 0) {
        printTable(['ID', 'Name', 'Scope', 'Created'], [])
        console.log("No agents found. Create one with 'arbiter agent create --name <name>'.")
        return
      }

      const rows = page.items.map((a) => [
        a.id,
        a.name,
        a.scope,
        formatDate(a.created_at),
      ])

      printTable(['ID', 'Name', 'Scope', 'Created'], rows)
    })
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toISOString().replace('T', ' ').slice(0, 16)
}
