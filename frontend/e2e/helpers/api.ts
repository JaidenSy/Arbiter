/**
 * NexusAI E2E — Direct API helpers for test setup.
 *
 * These helpers call the backend API directly (bypassing the UI) to set up
 * test data quickly. Use them in beforeEach/beforeAll hooks.
 */

import axios from 'axios'

const API = process.env.API_URL ?? 'http://localhost:8000/api/v1'

export interface TestUser {
  email: string
  password: string
  orgName: string
  accessToken: string
}

export interface TestAgent {
  id: string
  name: string
  apiKey: string
}

export interface TestServer {
  id: string
  name: string
}

/** Register a new user and return their access token. */
export async function registerUser(overrides: Partial<{ email: string; password: string; orgName: string }> = {}): Promise<TestUser> {
  const email = overrides.email ?? `test-${Date.now()}@nexusai.test`
  const password = overrides.password ?? 'TestPass123!'
  const orgName = overrides.orgName ?? `TestOrg-${Date.now()}`

  await axios.post(`${API}/auth/register`, { email, password, org_name: orgName })
  const { data } = await axios.post(`${API}/auth/login`, { email, password })

  return { email, password, orgName, accessToken: data.access_token }
}

/** Create an agent and return its id + raw API key. */
export async function createAgent(accessToken: string, name = `agent-${Date.now()}`): Promise<TestAgent> {
  const { data } = await axios.post(
    `${API}/agents`,
    { name, description: 'E2E test agent' },
    { headers: { Authorization: `Bearer ${accessToken}` } },
  )
  return { id: data.id, name: data.name, apiKey: data.api_key }
}

/** Create an MCP server and return its id. */
export async function createServer(accessToken: string, name = `server-${Date.now()}`): Promise<TestServer> {
  const { data } = await axios.post(
    `${API}/mcp-servers`,
    { name, base_url: 'http://localhost:3001/mcp', description: 'E2E test server', cache_enabled: false },
    { headers: { Authorization: `Bearer ${accessToken}` } },
  )
  return { id: data.id, name: data.name }
}

/** Grant a tool permission for an agent on a server. */
export async function grantPermission(
  accessToken: string,
  agentId: string,
  serverId: string,
  toolName = '*',
): Promise<void> {
  await axios.post(
    `${API}/agents/${agentId}/permissions`,
    { server_id: serverId, tool_name: toolName },
    { headers: { Authorization: `Bearer ${accessToken}` } },
  )
}

/** Store a vault secret for an org. */
export async function createSecret(
  accessToken: string,
  name: string,
  value = 'test-secret-value',
): Promise<{ id: string }> {
  const { data } = await axios.post(
    `${API}/vault/secrets`,
    { name, value },
    { headers: { Authorization: `Bearer ${accessToken}` } },
  )
  return { id: data.id }
}
