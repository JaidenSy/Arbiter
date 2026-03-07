/**
 * NexusAI Frontend — Axios HTTP client.
 *
 * Creates a pre-configured Axios instance that:
 *   - Points to the NexusAI backend API (configurable via VITE_API_BASE_URL)
 *   - Attaches the Bearer API key from localStorage on every request
 *   - Transforms 401 responses into a redirect to a login/settings page
 *
 * Usage:
 *   import { apiClient } from './client'
 *   const agents = await apiClient.get<Agent[]>('/agents')
 *
 * TODO (Coder):
 *   - Add request interceptor to read API key from localStorage / auth context
 *   - Add response interceptor to handle 401 (clear key, show toast)
 *   - Add response interceptor to normalise error messages (extract detail field)
 */

import axios, { type AxiosInstance } from 'axios'

const BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30_000, // 30 s — matches backend proxy timeout
})

// ── Request interceptor — attach Bearer token ─────────────────────────────────
apiClient.interceptors.request.use((config) => {
  // TODO: const apiKey = localStorage.getItem('nexusai_api_key')
  // TODO: if (apiKey) config.headers.Authorization = `Bearer ${apiKey}`
  return config
})

// ── Response interceptor — handle auth errors ─────────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // TODO: if (error.response?.status === 401) {
    //   localStorage.removeItem('nexusai_api_key')
    //   window.location.href = '/settings'
    // }
    return Promise.reject(error)
  },
)
