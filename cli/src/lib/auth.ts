import axios from 'axios'
import ora from 'ora'
import open from 'open'
import { resolveApiUrl, setConfig } from './config.js'
import type { DeviceCodeResponse, TokenResponse } from '../types/index.js'

const POLL_INTERVAL_MS = 3000
const MAX_POLL_MS = 15 * 60 * 1000 // 15 minutes

export async function deviceFlow(): Promise<TokenResponse> {
  const baseUrl = resolveApiUrl()

  // Step 1: initiate device flow
  const initRes = await axios.post<DeviceCodeResponse>(
    `${baseUrl}/api/v1/auth/cli/device`,
    {},
    { headers: { 'Content-Type': 'application/json' } }
  )
  const { device_code, user_code, verification_uri } = initRes.data

  // Step 2: build the browser URL from the backend-supplied verification_uri
  const verificationUri = `${verification_uri}?code=${user_code}`

  console.log('')
  console.log('  Open your browser to authorize:')
  console.log('')
  console.log(`  ${verificationUri}`)
  console.log('')
  console.log(`  Or visit the URL manually and enter code: ${user_code}`)
  console.log('')

  // Step 3: open browser
  try {
    await open(verificationUri)
  } catch {
    // Browser open is best-effort; user can open manually
  }

  // Step 4: poll for token
  const spinner = ora('Waiting for authorization... (press Ctrl+C to cancel)').start()
  const deadline = Date.now() + MAX_POLL_MS
  let networkErrorCount = 0

  while (Date.now() < deadline) {
    await sleep(POLL_INTERVAL_MS)

    try {
      const pollRes = await axios.post<TokenResponse>(
        `${baseUrl}/api/v1/auth/cli/token`,
        { device_code },
        {
          headers: { 'Content-Type': 'application/json' },
          validateStatus: (s) => [200, 428, 410, 403].includes(s),
        }
      )

      networkErrorCount = 0

      if (pollRes.status === 200) {
        spinner.succeed('Authorization granted.')
        const token = pollRes.data
        setConfig({
          access_token: token.access_token,
          org_id: token.org_id,
          logged_in_at: new Date().toISOString(),
        })
        return token
      }

      if (pollRes.status === 428) {
        // Still pending — continue
        continue
      }

      if (pollRes.status === 410) {
        spinner.fail('Authorization expired.')
        console.error('Authorization expired. Run `arbiter login` again.')
        process.exit(1)
      }

      if (pollRes.status === 403) {
        spinner.fail('Authorization denied.')
        console.error('Authorization denied.')
        process.exit(1)
      }
    } catch {
      networkErrorCount++
      if (networkErrorCount >= 3) {
        spinner.fail('Network error.')
        console.error('Could not reach Arbiter API. Check your connection.')
        process.exit(1)
      }
    }
  }

  spinner.fail('Authorization timed out.')
  console.error('Authorization timed out. Run `arbiter login` to try again.')
  process.exit(1)
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
