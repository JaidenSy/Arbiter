import { Command } from 'commander'
import { registerPermissionsGrant } from './grant.js'
import { registerPermissionsList } from './list.js'

export function registerPermissionsCommands(program: Command): void {
  const permissionsCmd = program
    .command('permissions')
    .description('Manage agent tool permissions')

  registerPermissionsGrant(permissionsCmd)
  registerPermissionsList(permissionsCmd)
}
