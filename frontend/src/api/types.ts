/**
 * Arbiter Frontend — shared TypeScript types for API responses.
 *
 * These types mirror the Pydantic schemas exposed by the Arbiter backend.
 * Keep in sync with CODER-A's backend contracts.
 */

export interface Page<T> {
  items: T[]
  total: number
  skip: number
  limit: number
}

export type AgentScope = "full" | "read_only" | "vault_read_only";

export interface Agent {
  id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  scope: AgentScope;
  created_at: string;
}

/** Only returned from POST /agents — the api_key is never shown again. */
export interface AgentCreateResponse extends Agent {
  api_key: string;
}

export interface MCPServer {
  id: string;
  name: string;
  base_url: string;
  description: string | null;
  cache_enabled: boolean;
  is_active: boolean;
  created_at: string;
}

export interface MCPServerCreate {
  name: string;
  base_url: string;
  description?: string | null;
  cache_enabled?: boolean;
}

export interface MCPServerUpdate {
  name?: string;
  base_url?: string;
  description?: string | null;
  cache_enabled?: boolean;
  is_active?: boolean;
}

export interface SessionEvent {
  id: string;
  session_id: string;
  mcp_server_id: string | null;
  mcp_server_name: string | null;
  tool_name: string;
  request_payload: Record<string, unknown>;
  response_payload: Record<string, unknown> | null;
  cache_hit: boolean;
  duration_ms: number | null;
  error: string | null;
  occurred_at: string;
}

export interface Session {
  id: string;
  agent_id: string;
  started_at: string;
  ended_at: string | null;
  metadata: Record<string, unknown>;
  events?: SessionEvent[];
}

export interface ToolPermission {
  id: string;
  agent_id: string;
  mcp_server_id: string;
  tool_name: string;
  granted_at: string;
  granted_by: string | null;
  rate_limit_per_minute: number | null;
  cache_ttl_seconds: number | null;
}

export interface ToolPermissionCreate {
  mcp_server_id: string
  tool_name: string
  rate_limit_per_minute?: number | null
  cache_ttl_seconds?: number | null
}

export interface ToolPermissionUpdate {
  rate_limit_per_minute: number | null
  cache_ttl_seconds: number | null
}

export interface ToolPermissionEvent {
  id: string
  permission_id: string | null
  mcp_server_id: string | null
  tool_name: string
  action: 'granted' | 'revoked' | 'updated'
  performed_by: string | null
  changes: Record<string, [unknown, unknown]> | null
  occurred_at: string
}

export interface VaultSecret {
  id: string;
  name: string;
  agent_id: string | null;
  created_at: string;
}

export interface VaultSecretWithValue extends VaultSecret {
  value: string;
}

export interface VaultSecretCreate {
  name: string;
  value: string;
}

export interface DashboardStats {
  agents_count: number;
  servers_count: number;
  tool_calls_today: number;
  cache_hit_rate_today: number; // 0.0–1.0
  error_rate_today: number; // 0.0–1.0
}

export interface CacheToolStat {
  tool_name: string;
  entries: number;
}

export interface CacheStats {
  total_entries: number;
  expired_entries: number;
  active_entries: number;
  top_tools: CacheToolStat[];
}

export interface MCPServerTestResult {
  reachable: boolean;
  tool_count: number | null;
  error: string | null;
  latency_ms: number | null;
}

export interface HistoryBucket {
  timestamp: string;
  label: string;
  tool_calls: number;
  cache_hits: number;
  cache_hit_rate: number; // 0.0–1.0
  errors: number;
}

export interface StatsHistoryResponse {
  period: string;
  buckets: HistoryBucket[];
}

export interface BillingStatus {
  plan: string;
  tool_calls_month: number;
  tool_calls_limit: number | null;
  agents_count: number;
  agents_limit: number | null;
  servers_count: number;
  servers_limit: number | null;
  vault_secrets_count: number;
  vault_secrets_limit: number | null;
  has_active_subscription: boolean;
}
