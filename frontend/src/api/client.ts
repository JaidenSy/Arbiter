/**
 * Arbiter Frontend — Axios HTTP clients.
 *
 * apiClient  — attaches the agent API key (Bearer nxai_<hex>). Used by all
 *              existing pages that interact with agent/MCP resource endpoints.
 *
 * authClient — attaches the user JWT (Bearer <jwt>). Used by the dashboard
 *              auth UI (Login, Register, AuthContext, UsageStrip).
 *              On 401: attempts one silent token refresh, then redirects to /login.
 *
 * Usage:
 *   import { apiClient, authClient } from './client'
 */

import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from "axios";

const BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

// ── Plan-limit event bus ──────────────────────────────────────────────────────
// When any request returns 402, dispatch this event so the upgrade modal can
// open regardless of which page triggered it.
export interface PlanLimitPayload {
  resource: string;
  current: number;
  limit: number;
  plan: string;
}
export const PLAN_LIMIT_EVENT = "arbiter:plan_limit";
function dispatchPlanLimit(payload: PlanLimitPayload): void {
  window.dispatchEvent(new CustomEvent(PLAN_LIMIT_EVENT, { detail: payload }));
}

// ── apiClient — agent API key ─────────────────────────────────────────────────

export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30_000,
});

apiClient.interceptors.request.use((config) => {
  const apiKey = localStorage.getItem("arbiter_api_key");
  if (apiKey) {
    config.headers.Authorization = `Bearer ${apiKey}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const hadKey = !!localStorage.getItem("arbiter_api_key");
      localStorage.removeItem("arbiter_api_key");
      if (hadKey) {
        window.location.href = "/agents";
      }
    }
    if (error.response?.status === 402) {
      dispatchPlanLimit(error.response.data);
    }
    return Promise.reject(error);
  },
);

// ── authClient — user JWT ─────────────────────────────────────────────────────

let isRefreshing = false;
let pendingQueue: Array<{
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
}> = [];

function drainQueue(token: string | null, err: unknown): void {
  pendingQueue.forEach((p) => (token ? p.resolve(token) : p.reject(err)));
  pendingQueue = [];
}

export const authClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

// Attach JWT from localStorage before every request
authClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("arbiter_access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401: attempt token refresh once, retry original request, else redirect /login
authClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retried?: boolean;
    };

    if (error.response?.status === 402) {
      dispatchPlanLimit(error.response.data);
      return Promise.reject(error);
    }

    if (error.response?.status !== 401 || originalRequest._retried) {
      return Promise.reject(error);
    }

    // Skip retry for auth endpoints themselves to avoid infinite loops
    const url: string = originalRequest.url ?? "";
    if (url.includes("/auth/login") || url.includes("/auth/register") || url.includes("/auth/refresh")) {
      return Promise.reject(error);
    }

    originalRequest._retried = true;

    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        pendingQueue.push({ resolve, reject });
      }).then((token) => {
        originalRequest.headers.Authorization = `Bearer ${token}`;
        return authClient(originalRequest);
      });
    }

    isRefreshing = true;
    const refreshToken = localStorage.getItem("arbiter_refresh_token");

    if (!refreshToken) {
      isRefreshing = false;
      localStorage.removeItem("arbiter_access_token");
      window.location.href = "/login";
      return Promise.reject(error);
    }

    try {
      const res = await authClient.post<{
        access_token: string;
        refresh_token: string;
      }>("/auth/refresh", { refresh_token: refreshToken });

      const newAccess = res.data.access_token;
      localStorage.setItem("arbiter_access_token", newAccess);
      localStorage.setItem("arbiter_refresh_token", res.data.refresh_token);

      drainQueue(newAccess, null);
      originalRequest.headers.Authorization = `Bearer ${newAccess}`;
      return authClient(originalRequest);
    } catch (refreshErr) {
      drainQueue(null, refreshErr);
      localStorage.removeItem("arbiter_access_token");
      localStorage.removeItem("arbiter_refresh_token");
      window.location.href = "/login";
      return Promise.reject(refreshErr);
    } finally {
      isRefreshing = false;
    }
  },
);
