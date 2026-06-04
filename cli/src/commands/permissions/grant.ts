import { Command } from 'commander'
import { get, post } from '../../lib/api.js'
import { requireAuth } from '../../lib/config.js'
import { printSuccess, printError } from '../../lib/output.js'
import { ApiError } from '../../lib/api.js'
import type { MCPServerPage, Permission } from '../../types/index.js'

export function registerPermissionsGrant(permissionsCmd: Command): void {
  permissionsCmd
    .command('grant')
    .description('Grant a tool permission to an agent')
    .requiredOption('--agent <id>', 'Agent ID')
    .requiredOption('--tool <tool>', 'Tool name (e.g. read_file, or * for all tools)')
    .requiredOption('--server <name>', 'MCP server name')
    .option('--json', 'Output raw JSON')
    .action(async (opts: { agent: string; tool: string; server: string; json?: boolean }) => {
      requireAuth()

      // Resolve server name → UUID
      const serverPage = await get<MCPServerPage>('/api/v1/mcp-servers', { skip: 0, limit: 200 })
      const server = serverPage.items.find(
        (s) => s.name.toLowerCase() === opts.server.toLowerCase()
      )

      if (!server) {
        printError(`MCP server '${opts.server}' not found. Check 'arbiter status' or verify the server name.`)
      }

      let permission: Permission
      try {
        permission = await post<Permission>(`/api/v1/agents/${opts.agent}/permissions`, {
          mcp_server_id: server.id,
          tool_name: opts.tool,
        })
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.status === 404) {
            printError('Agent or MCP server not found.')
          }
          if (err.status === 409) {
            console.log('Permission already exists.')
            process.exit(0)
          }
          printError(`API error: ${err.detail}`)
        }
        throw err
      }

      if (opts.json) {
        console.log(JSON.stringify(permission, null, 2))
        return
      }

      printSuccess(`Permission granted: ${opts.agent} → ${opts.server}/${opts.tool}`)
    })
}
