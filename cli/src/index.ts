import { Command } from 'commander'
import { resetClient } from './lib/api.js'
import { registerLogin } from './commands/login.js'
import { registerLogout } from './commands/logout.js'
import { registerStatus } from './commands/status.js'
import { registerAgentCommands } from './commands/agent/index.js'
import { registerPermissionsCommands } from './commands/permissions/index.js'
import { registerVaultCommands } from './commands/vault/index.js'

// eslint-disable-next-line @typescript-eslint/no-require-imports
const pkg = require('../package.json') as { version: string }

const program = new Command()

program
  .name('arbiter')
  .description('Arbiter CLI — manage your MCP gateway from the terminal')
  .version(pkg.version, '-v, --version')
  .option('--api-url <url>', 'Override API base URL', (url) => {
    process.env['ARBITER_API_URL'] = url
    resetClient()
  })

registerLogin(program)
registerLogout(program)
registerStatus(program)
registerAgentCommands(program)
registerPermissionsCommands(program)
registerVaultCommands(program)

program.parseAsync(process.argv).catch((err: unknown) => {
  if (err instanceof Error) {
    console.error(err.message)
  } else {
    console.error('An unexpected error occurred.')
  }
  process.exit(1)
})
