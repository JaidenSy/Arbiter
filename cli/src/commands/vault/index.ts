import { Command } from 'commander'
import { registerVaultSet } from './set.js'

export function registerVaultCommands(program: Command): void {
  const vaultCmd = program
    .command('vault')
    .description('Manage secrets in the vault')

  registerVaultSet(vaultCmd)
}
