import fs from 'fs'
import os from 'os'
import path from 'path'
import type { ArbiterConfig } from '../types/index.js'

const DEFAULT_API_URL = 'https://nexusai-api-production.up.railway.app'

function getConfigDir(): string {
  return path.join(os.homedir(), '.config', 'arbiter')
}

function getConfigPath(): string {
  return path.join(getConfigDir(), 'config.json')
}

export function getConfig(): ArbiterConfig | null {
  try {
    const raw = fs.readFileSync(getConfigPath(), 'utf-8')
    return JSON.parse(raw) as ArbiterConfig
  } catch {
    return null
  }
}

export function setConfig(data: Partial<ArbiterConfig>): void {
  const dir = getConfigDir()
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true })
  }
  const existing = getConfig() ?? { api_url: resolveApiUrl(), access_token: '', org_id: '' }
  const updated: ArbiterConfig = { ...existing, ...data }
  const filePath = getConfigPath()
  fs.writeFileSync(filePath, JSON.stringify(updated, null, 2), 'utf-8')
  fs.chmodSync(filePath, 0o600)
}

export function clearConfig(): void {
  const filePath = getConfigPath()
  if (fs.existsSync(filePath)) {
    fs.unlinkSync(filePath)
  }
}

export function isLoggedIn(): boolean {
  const cfg = getConfig()
  return !!(cfg?.access_token)
}

export function requireAuth(): ArbiterConfig {
  const cfg = getConfig()
  if (!cfg?.access_token) {
    console.error('Not logged in. Run `arbiter login`.')
    process.exit(1)
  }
  return cfg
}

export function resolveApiUrl(): string {
  const envUrl = process.env['ARBITER_API_URL']
  if (envUrl) return envUrl
  const cfg = getConfig()
  if (cfg?.api_url) return cfg.api_url
  return DEFAULT_API_URL
}
