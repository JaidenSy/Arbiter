import { Command } from 'commander'
import * as readline from 'readline'
import { del } from '../../lib/api.js'
import { requireAuth } from '../../lib/config.js'
import { printSuccess, printError } from '../../lib/output.js'
import { ApiError } from '../../lib/api.js'

export function registerAgentDelete(agentCmd: Command): void {
  agentCmd
    .command('delete <id>')
    .description('Delete an agent by ID')
    .action(async (id: string) => {
      requireAuth()

      const confirmed = await confirm(`Delete agent ${id}? (y/N) `)
      if (!confirmed) {
        console.log('Aborted.')
        return
      }

      try {
        await del(`/api/v1/agents/${id}`)
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.status === 404) {
            printError('Agent not found.')
          }
          printError(`API error: ${err.detail}`)
        }
        throw err
      }

      printSuccess(`Agent ${id} deleted.`)
    })
}

function confirm(prompt: string): Promise<boolean> {
  return new Promise((resolve) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    })
    rl.question(prompt, (answer: string) => {
      rl.close()
      resolve(answer.toLowerCase() === 'y')
    })
  })
}
