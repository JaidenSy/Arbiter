/**
 * NexusAI Frontend — shared TypeScript types for API responses.
 *
 * These types mirror the Pydantic schemas exposed by the NexusAI backend.
 * Keep in sync with CODER-A's backend contracts.
 */

export interface Agent {
  id: string
  name: string
  description: string | null
  is_active: boolean
  created_at: string
}

/** Only returned from POST /agents — the api_key is never shown again. */
export interface AgentCreateResponse extends Agent {
  api_key: string
}

export interface MCPServer {
  id: string
  name: string
  base_url: string
  description: string | null
  cache_enabled: boolean
  is_active: boolean
  created_at: string
}

export interface SessionEvent {
  id: string
  tool_name: string
  cache_hit: boolean
  duration_ms: number | null
  error: string | null
  occurred_at: string
  metadata: Record<string, unknown>
}

export interface Session {
  id: string
  agent_id: string
  started_at: string
  events?: SessionEvent[]
}

export interface ToolPermission {
  id: string
  agent_id: string
  mcp_server_id: string
  tool_name: string
}

export interface VaultSecret {
  id: string
  name: string
  agent_id: string | null
}

export interface VaultSecretWithValue extends VaultSecret {
  value: string
}

export interface DashboardStats {
  agents_count: number
  servers_count: number
  tool_calls_today: number
  cache_hit_rate_today: number // 0.0–1.0
}
