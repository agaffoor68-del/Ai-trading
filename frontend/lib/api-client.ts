"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";

const RAW_API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";
const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, "");

export interface ApiError {
  code: string;
  message: string;
  status?: number;
}

export interface FyersConnectResponse {
  auth_url?: string;
  authorization_url?: string;
  state?: string;
}

interface FetchOptions extends RequestInit {
  requireAuth?: boolean;
  redirectOnUnauthorized?: boolean;
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
  const timeoutId = setTimeout(() => controller.abort(), 15000);

  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    if (isAbortError(error) || controller.signal.aborted) {
      throw { code: "TIMEOUT", message: "Server is waking up. Please wait...", status: 408 } as ApiError;
    }
    throw { code: "NETWORK_ERROR", message: "Server is waking up. Please wait...", status: 0 } as ApiError;
  } finally {
    clearTimeout(timeoutId);
  }
}

function getStoredAuthToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  const localToken = window.localStorage.getItem("admin_token");
  if (localToken) {
    return localToken;
  }

  const cookieToken = document.cookie
    .split("; ")
    .find((row) => row.startsWith("access_token="));

  if (!cookieToken) {
    return null;
  }

  const value = cookieToken.split("=").slice(1).join("=");
  return value ? decodeURIComponent(value) : null;
}

export async function apiFetch<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { requireAuth = true, redirectOnUnauthorized = true, headers = {}, ...fetchOptions } = options;

  const authToken = getStoredAuthToken();
  const headersObj: HeadersInit = {
    "Content-Type": "application/json",
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    ...headers,
  };

  const url =
    endpoint.startsWith("http://") || endpoint.startsWith("https://") || endpoint.startsWith("/api/v1")
      ? endpoint
      : `${API_BASE_URL}${endpoint}`;

  const response = await fetchWithTimeout(url, {
    ...fetchOptions,
    headers: headersObj,
    credentials: "same-origin",
  });

  if (response.status === 401) {
    const error = parseApiError(await response.json().catch(() => null), 401);

    if (isFyersNotConnected(error)) {
      throw error;
    }

    if (redirectOnUnauthorized) {
      window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`;
    }
    throw error;
  }

  if (response.status === 403) {
    const error = parseApiError(await response.json().catch(() => null), 403);
    throw error;
  }

  if (!response.ok) {
    throw parseApiError(await response.json().catch(() => null), response.status);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const api = {
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

  getMe: () => apiFetch("/api/auth/me", { requireAuth: true }),

  getMarketStatus: () => apiFetch("/api/v1/market/status", { requireAuth: true }),

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

  getFyersStatus: () => apiFetch("/api/v1/fyers/status", { requireAuth: true }),

  connectFyers: (clientId: string, secretKey: string) =>
    apiFetch<FyersConnectResponse>("/api/v1/fyers/connect", {
      method: "POST",
      body: JSON.stringify({ client_id: clientId, client_secret: secretKey }),
      requireAuth: true,
    }),

  getAdminUsers: () =>
    apiFetch<{ users?: unknown; total?: number }>("/api/v1/admin/users", {
      requireAuth: true,
      redirectOnUnauthorized: false,
    }),

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

export { toast };

