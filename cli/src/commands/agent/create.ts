import { Command } from 'commander'
import { post } from '../../lib/api.js'
import { requireAuth } from '../../lib/config.js'
import { printSuccess, printError } from '../../lib/output.js'
import { ApiError } from '../../lib/api.js'
import chalk from 'chalk'
import type { Agent } from '../../types/index.js'

export function registerAgentCreate(agentCmd: Command): void {
  agentCmd
    .command('create')
    .description('Create a new agent')
    .requiredOption('--name <name>', 'Display name for the agent')
    .option('--json', 'Output raw JSON')
    .action(async (opts: { name: string; json?: boolean }) => {
      requireAuth()

      let agent: Agent
      try {
        agent = await post<Agent>('/api/v1/agents', { name: opts.name })
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.status === 402) {
            printError('Plan limit reached. Upgrade at https://arbiterai.dev/pricing')
          }
          if (err.status === 409) {
            printError('An agent with that name already exists.')
          }
          printError(`API error: ${err.detail}`)
        }
        throw err
      }

      if (opts.json) {
        console.log(JSON.stringify(agent, null, 2))
        return
      }

      printSuccess('Agent created')
      console.log(`  ID:   ${agent.id}`)
      console.log(`  Name: ${agent.name}`)
      console.log('')
      console.log(
        chalk.yellow('⚠  Save this API key — it will not be shown again:')
      )
      console.log('')
      console.log(`  ${chalk.bold(agent.api_key ?? '(key not returned)')}`)
      console.log('')
    })
}
