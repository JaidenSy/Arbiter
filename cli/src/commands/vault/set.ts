import { Command } from 'commander'
import { post } from '../../lib/api.js'
import { requireAuth } from '../../lib/config.js'
import { printSuccess, printError, printWarning } from '../../lib/output.js'
import { ApiError } from '../../lib/api.js'
import type { VaultSecretResponse } from '../../types/index.js'

const SECRET_NAME_RE = /^[A-Za-z0-9_]+$/

export function registerVaultSet(vaultCmd: Command): void {
  vaultCmd
    .command('set')
    .description('Store a secret in the vault')
    .requiredOption('--agent <id>', 'Agent ID to scope the secret to')
    .requiredOption('--key <key>', 'Secret key name (e.g. OPENAI_API_KEY)')
    .requiredOption('--value <value>', 'Secret value')
    .option('--json', 'Output raw JSON')
    .action(async (opts: { agent: string; key: string; value: string; json?: boolean }) => {
      requireAuth()

      // Validate key format
      if (!SECRET_NAME_RE.test(opts.key)) {
        printError(
          'Secret key must contain only letters, numbers, and underscores (A-Za-z0-9_).'
        )
      }

      // Warn about shell history when running interactively
      if (process.stdout.isTTY) {
        printWarning(
          'Secret value provided via --value flag will appear in shell history.'
        )
        console.warn(
          `   Consider using: read -s VAL && arbiter vault set --agent ${opts.agent} --key ${opts.key} --value "$VAL"`
        )
        console.warn('')
      }

      let secret: VaultSecretResponse
      try {
        secret = await post<VaultSecretResponse>('/api/v1/vault/secrets', {
          name: opts.key,
          value: opts.value,
          agent_id: opts.agent,
        })
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.status === 404) {
            printError('Agent not found.')
          }
          if (err.status === 402) {
            printError('Plan limit reached. Upgrade at https://arbiterai.dev/pricing')
          }
          printError(`API error: ${err.detail}`)
        }
        throw err
      }

      if (opts.json) {
        console.log(JSON.stringify(secret, null, 2))
        return
      }

      printSuccess(`Secret '${opts.key}' set for agent ${opts.agent}.`)
    })
}
