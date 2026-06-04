import axios, { AxiosInstance } from 'axios'
import { getConfig, resolveApiUrl } from './config.js'

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string
  ) {
    super(detail)
    this.name = 'ApiError'
  }
}

function createClient(): AxiosInstance {
  const client = axios.create({
    baseURL: resolveApiUrl(),
    headers: { 'Content-Type': 'application/json' },
  })

  client.interceptors.request.use((config) => {
    const cfg = getConfig()
    if (cfg?.access_token) {
      config.headers['Authorization'] = `Bearer ${cfg.access_token}`
    }
    return config
  })

  client.interceptors.response.use(
    (res) => res,
    (err) => {
      const status: number = err.response?.status ?? 0
      const detail: string = err.response?.data?.detail || err.message || 'Unknown error'
      if (status === 401) {
        console.error('Session expired. Run `arbiter login`.')
        process.exit(1)
      }
      throw new ApiError(status, detail)
    }
  )

  return client
}

// Lazily created so resolveApiUrl() picks up any runtime overrides
let _client: AxiosInstance | null = null

function client(): AxiosInstance {
  if (!_client) {
    _client = createClient()
  }
  return _client
}

export function resetClient(): void {
  _client = null
}

export async function get<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  const res = await client().get<T>(path, { params })
  return res.data
}

export async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await client().post<T>(path, body)
  return res.data
}

export async function patch<T>(path: string, body?: unknown): Promise<T> {
  const res = await client().patch<T>(path, body)
  return res.data
}

export async function del(path: string): Promise<void> {
  await client().delete(path)
}
