"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

export interface ApiError {
  code: string;
  message: string;
}

interface FetchOptions extends RequestInit {
  requireAuth?: boolean;
}

export async function apiFetch<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { requireAuth = true, headers = {}, ...fetchOptions } = options;

  const headersObj: HeadersInit = {
    "Content-Type": "application/json",
    ...headers,
  };

  // Same-origin requests carry the httpOnly session cookie; the Next.js
  // proxy route adds the Authorization header for the backend.
  const url = endpoint.startsWith("/api/") ? endpoint : `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    ...fetchOptions,
    headers: headersObj,
    credentials: "same-origin",
  });

  // Handle 401 - redirect to login
  if (response.status === 401) {
    const error = await response.json().catch(() => ({ code: "AUTH_REQUIRED", message: "Authentication required" }));
    
    // Check if it's a Fyers-specific 401
    if (error.code === "FYERS_NOT_CONNECTED") {
      throw { ...error, status: 401 };
    }
    
    // User auth failure - redirect to login
    window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`;
    throw { ...error, status: 401 };
  }

  // Handle 403 - forbidden
  if (response.status === 403) {
    const error = await response.json().catch(() => ({ code: "FORBIDDEN", message: "Access denied" }));
    throw { ...error, status: 403 };
  }

  // Handle other errors
  if (!response.ok) {
    const error = await response.json().catch(() => ({ 
      code: "ERROR", 
      message: `HTTP ${response.status}` 
    }));
    throw { ...error, status: response.status };
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

  connectFyers: (clientId: string, clientSecret: string) => 
    apiFetch("/api/v1/fyers/connect", {
      method: "POST",
      body: JSON.stringify({ client_id: clientId, client_secret: clientSecret }),
      requireAuth: true,
    }),

  // Admin
  getAdminUsers: () => 
    apiFetch("/api/v1/admin/users", { requireAuth: true }),

  grantAccess: (email: string, plan: string, days: number) => 
    apiFetch("/api/v1/admin/subscribe", {
      method: "POST",
      body: JSON.stringify({ email, plan, days }),
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
  if (error && typeof error === "object" && "code" in error) {
    return (error as any).code === "FYERS_NOT_CONNECTED";
  }
  return false;
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