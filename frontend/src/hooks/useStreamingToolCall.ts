/**
 * NexusAI — useStreamingToolCall hook.
 *
 * Issues a POST to /proxy/tool-call using the Fetch API with a ReadableStream
 * decoder.  Unlike EventSource (GET-only), fetch supports POST with a body,
 * which is required for tool-call requests.
 *
 * The hook automatically detects whether the response is:
 *   - text/event-stream → accumulates raw SSE chunks into `chunks[]`
 *   - application/json  → parses the response and sets `result`
 *
 * Auth: uses the agent API key stored in localStorage under "nexusai_api_key".
 *
 * Usage:
 *   const { chunks, result, isStreaming, error, send, reset } = useStreamingToolCall();
 *   await send({ server_name: "fs", tool_name: "read_file", params: { path: "/tmp/x" } });
 */

import { useState, useCallback, useRef } from "react";
import type { ToolCallRequest, ToolCallResponse } from "../api/types";

const BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export interface UseStreamingToolCallState {
  /** Accumulated raw SSE chunk strings (streaming path only). */
  chunks: string[];
  /** Parsed JSON result (non-streaming path only). */
  result: ToolCallResponse | null;
  /** True while the stream / fetch is in progress. */
  isStreaming: boolean;
  /** Error message if the call failed. */
  error: string | null;
}

export interface UseStreamingToolCallActions {
  /** Send a tool-call request. Returns when the full response is received. */
  send: (request: ToolCallRequest) => Promise<void>;
  /** Reset state back to initial values. */
  reset: () => void;
}

const INITIAL_STATE: UseStreamingToolCallState = {
  chunks: [],
  result: null,
  isStreaming: false,
  error: null,
};

export function useStreamingToolCall(): UseStreamingToolCallState &
  UseStreamingToolCallActions {
  const [state, setState] = useState<UseStreamingToolCallState>(INITIAL_STATE);
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState(INITIAL_STATE);
  }, []);

  const send = useCallback(async (request: ToolCallRequest): Promise<void> => {
    // Abort any in-flight call.
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState({ chunks: [], result: null, isStreaming: true, error: null });

    const apiKey = localStorage.getItem("nexusai_api_key") ?? "";

    let resp: Response;
    try {
      resp = await fetch(`${BASE_URL}/proxy/tool-call`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify(request),
        signal: controller.signal,
      });
    } catch (err: unknown) {
      if ((err as { name?: string }).name === "AbortError") return;
      setState((s) => ({
        ...s,
        isStreaming: false,
        error: err instanceof Error ? err.message : "Network error",
      }));
      return;
    }

    if (!resp.ok) {
      let detail = `HTTP ${resp.status}`;
      try {
        const body = await resp.json();
        detail = body?.detail ?? detail;
      } catch {
        // ignore parse failure
      }
      setState((s) => ({ ...s, isStreaming: false, error: detail }));
      return;
    }

    const contentType = resp.headers.get("content-type") ?? "";

    // ── SSE path ───────────────────────────────────────────────────────────────
    if (contentType.includes("text/event-stream")) {
      const reader = resp.body?.getReader();
      if (!reader) {
        setState((s) => ({
          ...s,
          isStreaming: false,
          error: "Streaming not supported by this browser",
        }));
        return;
      }
      const decoder = new TextDecoder();
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const text = decoder.decode(value, { stream: true });
          if (text) {
            setState((s) => ({
              ...s,
              chunks: [...s.chunks, text],
            }));
          }
        }
      } catch (err: unknown) {
        if ((err as { name?: string }).name !== "AbortError") {
          setState((s) => ({
            ...s,
            error: err instanceof Error ? err.message : "Stream read error",
          }));
        }
      } finally {
        reader.releaseLock();
        setState((s) => ({ ...s, isStreaming: false }));
      }
      return;
    }

    // ── JSON path ──────────────────────────────────────────────────────────────
    try {
      const data = (await resp.json()) as ToolCallResponse;
      setState({ chunks: [], result: data, isStreaming: false, error: null });
    } catch (err: unknown) {
      setState((s) => ({
        ...s,
        isStreaming: false,
        error: err instanceof Error ? err.message : "JSON parse error",
      }));
    }
  }, []);

  return { ...state, send, reset };
}
