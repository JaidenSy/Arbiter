import { Command } from 'commander'
import { clearConfig, isLoggedIn } from '../lib/config.js'
import { printSuccess } from '../lib/output.js'

export function registerLogout(program: Command): void {
  program
    .command('logout')
    .description('Clear your local Arbiter session')
    .action(() => {
      if (!isLoggedIn()) {
        console.log('Not logged in.')
        return
      }
      clearConfig()
      printSuccess('Logged out.')
    })
}
