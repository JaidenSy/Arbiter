export interface ArbiterConfig {
  access_token: string
  org_id: string
  api_url: string
  user_email?: string
  logged_in_at?: string
}

export interface Agent {
  id: string
  name: string
  description: string | null
  is_active: boolean
  scope: string
  rate_limit_per_minute: number | null
  created_at: string
  updated_at: string
  api_key?: string
}

export interface AgentPage {
  items: Agent[]
  total: number
  skip: number
  limit: number
}

export interface Permission {
  id: string
  agent_id: string
  mcp_server_id: string
  tool_name: string
  granted_at: string
  granted_by: string
  rate_limit_per_minute: number | null
  cache_ttl_seconds: number | null
}

export interface PermissionPage {
  items: Permission[]
  total: number
  skip: number
  limit: number
}

export interface VaultSecretResponse {
  id: string
  name: string
  agent_id: string | null
  created_at: string
}

export interface MCPServer {
  id: string
  name: string
  base_url: string
  description: string | null
  headers: Record<string, string>
  is_active: boolean
  cache_enabled: boolean
}

export interface MCPServerPage {
  items: MCPServer[]
  total: number
  skip: number
  limit: number
}

export interface DeviceCodeResponse {
  device_code: string
  user_code: string
  expires_in: number
  verification_uri: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  org_id: string
}

export interface MeResponse {
  id: string
  email: string
  display_name: string
  role: string
  org_id: string
  org_name: string
  org_plan: string
  has_password: boolean
  linked_providers: string[]
  avatar_url: string | null
  is_verified: boolean
}

export interface HealthResponse {
  status: string
}
