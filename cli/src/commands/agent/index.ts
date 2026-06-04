import { Command } from 'commander'
import { registerAgentCreate } from './create.js'
import { registerAgentList } from './list.js'
import { registerAgentDelete } from './delete.js'

export function registerAgentCommands(program: Command): void {
  const agentCmd = program
    .command('agent')
    .description('Manage agents in your org')

  registerAgentCreate(agentCmd)
  registerAgentList(agentCmd)
  registerAgentDelete(agentCmd)
}
