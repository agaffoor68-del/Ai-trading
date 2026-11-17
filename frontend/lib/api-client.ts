"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";

const RAW_API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

// Normalize the configured backend base so it never carries a trailing slash.
const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, "");

// Backend on Render sleeps when idle, so cold requests can take a while.
export const API_TIMEOUT_MS = 15000;
export const SERVER_WAKING_MESSAGE = "Server is waking up. Please wait...";

export interface ApiError {
  code: string;
  message: string;
  status?: number;
}

export interface FyersConnectResponse {
  authorization_url: string;
  state?: string;
}

interface FetchOptions extends RequestInit {
  requireAuth?: boolean;
}

function isAbortError(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const candidate = error as { name?: string; code?: string; message?: string };
  return (
    candidate.name === "AbortError" ||
    candidate.name === "TimeoutError" ||
    candidate.code === "ABORT_ERR" ||
    candidate.code === "TIMEOUT" ||
    candidate.code === "NETWORK_ERROR" ||
    /timed?\s*out|aborted/i.test(candidate.message ?? "")
  );
}

export function isServerWakingUp(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const candidate = error as { code?: string; status?: number };
  if (candidate.code === "TIMEOUT" || candidate.code === "NETWORK_ERROR") return true;
  if (typeof candidate.status === "number" && candidate.status >= 500) return true;
  return false;
}

// Backend errors come back as {detail: {code, message}}, {detail: "text"},
// {code, message} or {error: "text"} depending on the route, so normalize all
// of them into a single shape.
export function parseApiError(payload: unknown, status: number): ApiError {
  let code = status >= 500 ? "SERVER_ERROR" : "ERROR";
  let message = `HTTP ${status}`;

  const assign = (source: unknown) => {
    if (!source || typeof source !== "object") return;
    const record = source as Record<string, unknown>;
    if (typeof record.code === "string" && record.code) code = record.code;
    if (typeof record.message === "string" && record.message) message = record.message;
    else if (typeof record.error === "string" && record.error) message = record.error;
    else if (typeof record.detail === "string" && record.detail) message = record.detail;
  };

  assign(payload);
  if (payload && typeof payload === "object" && "detail" in payload) {
    assign((payload as { detail: unknown }).detail);
  }

  return { code, message, status };
}

export async function fetchWithTimeout(url: string, init: RequestInit = {}): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    if (isAbortError(error) || controller.signal.aborted) {
      throw { code: "TIMEOUT", message: SERVER_WAKING_MESSAGE, status: 408 } as ApiError;
    }
    throw { code: "NETWORK_ERROR", message: SERVER_WAKING_MESSAGE, status: 0 } as ApiError;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function apiFetch<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { requireAuth = true, headers = {}, ...fetchOptions } = options;

  const headersObj: HeadersInit = {
    "Content-Type": "application/json",
    ...headers,
  };

  // Same-origin /api/v1 requests go through the Next.js proxy (which adds
  // the Authorization header). Anything else is an absolute backend URL or a
  // path relative to the backend base.
  const url =
    endpoint.startsWith("http://") || endpoint.startsWith("https://") || endpoint.startsWith("/api/v1")
      ? endpoint
      : `${API_BASE_URL}${endpoint}`;

  const response = await fetchWithTimeout(url, {
    ...fetchOptions,
    headers: headersObj,
    credentials: "same-origin",
  });

  // Handle 401 - redirect to login
  if (response.status === 401) {
    const error = parseApiError(
      await response.json().catch(() => null),
      401
    );

    // Check if it's a Fyers-specific 401
    if (isFyersNotConnected(error)) {
      throw error;
    }
    
    // User auth failure - redirect to login
    window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`;
    throw error;
  }

  // Handle 403 - forbidden
  if (response.status === 403) {
    const error = parseApiError(await response.json().catch(() => null), 403);
    throw error;
  }

  // Handle other errors
  if (!response.ok) {
    throw parseApiError(await response.json().catch(() => null), response.status);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

// Helper functions for common API calls
export const api = {
  // Auth
  login: (email: string, password: string) => 
    apiFetch("/api/auth/login", {
      method: "POST",
      body: new URLSearchParams({ username: email, password }),
      requireAuth: false,
    }),

  logout: () => 
    apiFetch("/api/auth/logout", {
      method: "POST",
      requireAuth: true,
    }),

  getMe: () => 
    apiFetch("/api/auth/me", { requireAuth: true }),

  // Market data
  getMarketStatus: () => 
    apiFetch("/api/v1/market/status", { requireAuth: true }),

  getMarketQuotes: (symbols: string[]) => 
    apiFetch("/api/v1/market/quotes", {
      method: "POST",
      body: JSON.stringify({ symbols }),
      requireAuth: true,
    }),

  getCandles: (symbol: string, interval: string, days: number) => 
    apiFetch(`/api/v1/market/candles?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&days=${days}`, { requireAuth: true }),

  getOptionChain: (symbol: string, expiry: string, strikes?: number) => 
    apiFetch(`/api/v1/market/option-chain?symbol=${encodeURIComponent(symbol)}&expiry=${encodeURIComponent(expiry)}${strikes ? `&strikes=${strikes}` : ""}`, { requireAuth: true }),

  // Fyers
  getFyersStatus: () => 
    apiFetch("/api/v1/fyers/status", { requireAuth: true }),

  connectFyers: (clientId: string, secretKey: string) =>
    apiFetch<FyersConnectResponse>("/api/v1/fyers/connect", {
      method: "POST",
      body: JSON.stringify({ client_id: clientId, secret_key: secretKey }),
      requireAuth: true,
    }),

  // Admin
  getAdminUsers: () => 
    apiFetch("/api/v1/admin/users", { requireAuth: true }),

  grantAccess: (data: { email: string; plan: string; days: number }) => 
    apiFetch("/api/v1/admin/subscribe", {
      method: "POST",
      body: JSON.stringify(data),
      requireAuth: true,
    }),

  revokeAccess: (userId: number) => 
    apiFetch(`/api/v1/admin/revoke/${userId}`, {
      method: "DELETE",
      requireAuth: true,
    }),
};

// Error code helpers
export function isFyersNotConnected(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const candidate = error as { code?: string; status?: number; message?: string };
  if (candidate.code === "FYERS_NOT_CONNECTED" || candidate.code === "FYERS_TOKEN_EXPIRED") {
    return true;
  }
  const message = candidate.message ?? "";
  if (/fyers/i.test(message) && /not authenticated|not connected|expired|offline/i.test(message)) {
    return true;
  }
  return candidate.status === 401 && /fyers/i.test(message);
}

export function isAuthError(error: unknown): boolean {
  if (error && typeof error === "object" && "code" in error) {
    const code = (error as any).code;
    return code === "AUTH_REQUIRED" || code === "TOKEN_EXPIRED" || code === "TOKEN_INVALID";
  }
  return false;
}

export function formatFyersSymbol(symbol: string): string {
  if (symbol.includes(":")) {
    return symbol;
  }
  return symbol;
}

export function isFyersError(error: unknown): boolean {
  if (error && typeof error === "object" && "code" in error) {
    return (error as any).code === "FYERS_ERROR";
  }
  if (error && typeof error === "object" && "status" in error) {
    return (error as any).status === 502;
  }
  return false;
}

export function isFyersUnreachable(error: unknown): boolean {
  if (error && typeof error === "object" && "code" in error) {
    return (error as any).code === "FYERS_UNREACHABLE";
  }
  if (error && typeof error === "object" && "status" in error) {
    return (error as any).status === 504;
  }
  return false;
}
