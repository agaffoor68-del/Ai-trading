"use client";

import useSWR, { mutate } from "swr";
import {
  api,
  fetchWithTimeout,
  parseApiError,
  isServerWakingUp,
  isFyersNotConnected,
  isFyersError,
  isFyersUnreachable,
  isAuthError,
  formatFyersSymbol,
} from "@/lib/api-client";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

// Helper to create fetcher with proper error handling
const createFetcher = <T,>(key: string) => async (): Promise<T> => {
  const response = await fetchWithTimeout(key, {
    credentials: "same-origin",
  });

  if (!response.ok) {
    const error = parseApiError(await response.json().catch(() => null), response.status);

    if (response.status === 401 && !isFyersNotConnected(error)) {
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`;
      }
    }

    throw error;
  }

  return response.json();
};

// Helper for POST requests
const createPostFetcher = <T,>(key: string, body: any) => async (): Promise<T> => {
  const response = await fetchWithTimeout(key, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "same-origin",
  });

  if (!response.ok) {
    const error = parseApiError(await response.json().catch(() => null), response.status);

    if (response.status === 401 && !isFyersNotConnected(error)) {
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`;
      }
    }

    throw error;
  }

  return response.json();
};

export function useMarketQuotes(symbols: string[]) {
  const symbolsKey = symbols.length > 0 ? symbols.sort().join(",") : "";
  
  const { data, error, isLoading, mutate } = useSWR<{ quotes: Record<string, any>; total: number }>(
    symbolsKey ? [`/api/v1/market/quotes`, symbols] : null,
    ([, syms]) => createPostFetcher<{ quotes: Record<string, any>; total: number }>("/api/v1/market/quotes", { symbols: syms })(),
    {
      refreshInterval: (data) => {
        if (data?.quotes) {
          const now = Date.now();
          const hasRecent = Object.values(data.quotes).some(q => 
            q.updated_at && (now - new Date(q.updated_at).getTime()) < 60000
          );
          return hasRecent ? 3000 : 30000;
        }
        return 30000;
      },
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 2000,
    }
  );

  // Backend returns { quotes: { "<fyers-symbol>": { ltp, change, ... } }, total, ... }
  console.log("API Response (quotes):", data);

  return {
    quotes: data?.quotes || {},
    total: data?.total || 0,
    isLoading,
    isError: !!error,
    error: error?.message,
    errorCode: (error as any)?.code,
    isFyersNotConnected: isFyersNotConnected(error),
    isFyersError: isFyersError(error),
    isFyersUnreachable: isFyersUnreachable(error),
    isServerWakingUp: isServerWakingUp(error),
    mutate,
  };
}

export function useOptionChain(symbol: string, expiry: string, strikes = 10) {
  const { data, error, isLoading, mutate } = useSWR<{
    symbol: string;
    expiry: string;
    spot_price: number;
    atm_strike: number;
    strike_interval: number;
    option_chain: any[];
    expiries: string[];
    timestamp: string;
  }>(
    symbol && expiry ? `/api/v1/market/option-chain?symbol=${encodeURIComponent(symbol)}&expiry=${encodeURIComponent(expiry)}&strikes=${strikes}` : null,
    createFetcher<{
      symbol: string;
      expiry: string;
      spot_price: number;
      atm_strike: number;
      strike_interval: number;
      option_chain: any[];
      expiries: string[];
      timestamp: string;
    }>(`/api/v1/market/option-chain?symbol=${encodeURIComponent(symbol)}&expiry=${encodeURIComponent(expiry)}&strikes=${strikes}`),
    {
      refreshInterval: (data) => data ? 3000 : 30000,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 2000,
    }
  );

  // Backend returns { option_chain: [...], spot_price, atm_strike, expiries, ... }
  console.log("API Response (option-chain):", data);

  return {
    chainData: data,
    isLoading,
    isError: !!error,
    error: error?.message,
    errorCode: (error as any)?.code,
    isFyersNotConnected: isFyersNotConnected(error),
    isFyersError: isFyersError(error),
    isFyersUnreachable: isFyersUnreachable(error),
    isServerWakingUp: isServerWakingUp(error),
    mutate,
  };
}

export function useAISignals(symbols: string[] = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]) {
  const { data, error, isLoading, mutate } = useSWR<{
    signals: Array<{
      symbol: string;
      signal: "BUY" | "SELL" | "HOLD";
      confidence: number;
      rsi: number;
      ema_trend: "BULLISH" | "BEARISH" | "NEUTRAL";
      price: number;
      timestamp: string;
    }>;
    timestamp: string;
  }>(
    symbols.length > 0 ? `/api/v1/market/ai/signals?symbols=${symbols.join(",")}` : null,
    createFetcher<{
      signals: Array<{
        symbol: string;
        signal: "BUY" | "SELL" | "HOLD";
        confidence: number;
        rsi: number;
        ema_trend: "BULLISH" | "BEARISH" | "NEUTRAL";
        price: number;
        timestamp: string;
      }>;
      timestamp: string;
    }>(`/api/v1/market/ai/signals?symbols=${symbols.join(",")}`),
    {
      refreshInterval: 30000,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 10000,
    }
  );

  // Backend returns { signals: [...], timestamp }
  console.log("API Response (ai-signals):", data);

  return {
    signals: data?.signals || [],
    timestamp: data?.timestamp,
    isLoading,
    isError: !!error,
    error: error?.message,
    errorCode: (error as any)?.code,
    isFyersNotConnected: isFyersNotConnected(error),
    isFyersError: isFyersError(error),
    isFyersUnreachable: isFyersUnreachable(error),
    isServerWakingUp: isServerWakingUp(error),
    mutate,
  };
}

export function useCandles(symbol: string, interval: string = "5m", days: number = 5) {
  const { data, error, isLoading, mutate } = useSWR<{ candles: any[]; market_open?: boolean; note?: string | null }>(
    symbol ? `/api/v1/market/candles?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&days=${days}` : null,
    createFetcher<{ candles: any[]; market_open?: boolean; note?: string | null }>(`/api/v1/market/candles?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&days=${days}`),
    {
      refreshInterval: 60000,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 30000,
    }
  );

  // The backend wraps the candle rows under `candles`:
  // { "candles": [{time, open, high, low, close, volume}], "market_open", "note" }
  console.log("API Response (candles):", data);

  return {
    candles: data?.candles || [],
    isLoading,
    isError: !!error,
    error: error?.message,
    errorCode: (error as any)?.code,
    isFyersNotConnected: isFyersNotConnected(error),
    isFyersError: isFyersError(error),
    isFyersUnreachable: isFyersUnreachable(error),
    isServerWakingUp: isServerWakingUp(error),
    mutate,
  };
}

export function useMarketStatus() {
  const { data, error, isLoading, mutate } = useSWR<{
    is_open: boolean;
    is_trading_day: boolean;
    next_open: string | null;
    next_close: string | null;
    time_to_close_minutes: number;
    timezone: string;
  }>(
    "/api/v1/market/status",
    createFetcher<{
      is_open: boolean;
      is_trading_day: boolean;
      next_open: string | null;
      next_close: string | null;
      time_to_close_minutes: number;
      timezone: string;
    }>("/api/v1/market/status"),
    {
      refreshInterval: 30000,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 10000,
    }
  );

  return {
    status: data,
    isLoading,
    isError: !!error,
    error: error?.message,
    mutate,
  };
}

export function useFyersStatus() {
  const { data, error, isLoading, mutate } = useSWR<any>(
    "/api/v1/fyers/status",
    createFetcher<any>("/api/v1/fyers/status"),
    {
      refreshInterval: 30000,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 10000,
    }
  );

  return {
    status: data,
    isLoading,
    isError: !!error,
    error: error?.message,
    mutate,
  };
}

export function useFullStatus() {
  const { data, error, isLoading, mutate } = useSWR<any>(
    "/api/v1/fyers/status",
    createFetcher<any>("/api/v1/fyers/status"),
    {
      refreshInterval: 30000,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 10000,
    }
  );

  // Backend returns FLAT: { connected: bool, valid: bool, message, token_expires_at, ... }
  console.log("API Response (fyers/status):", data);

  return {
    status: data,
    isLoading,
    isError: !!error,
    error: error?.message,
    mutate,
  };
}

export function useExpiries(symbol: string) {
  const { data, error, isLoading, mutate } = useSWR<{ expiries: string[] }>(
    symbol ? `/api/v1/market/expiries?symbol=${encodeURIComponent(symbol)}` : null,
    createFetcher<{ expiries: string[] }>(`/api/v1/market/expiries?symbol=${encodeURIComponent(symbol)}`),
    {
      refreshInterval: 3600000,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 300000,
    }
  );

  return {
    expiries: data?.expiries || [],
    isLoading,
    isError: !!error,
    error: error?.message,
    mutate,
  };
}

export function useMe() {
  const { data, error, isLoading, mutate } = useSWR<{
    id: number;
    email: string;
    role: string;
    is_active: boolean;
    subscription: {
      plan_type: string;
      start_date: string | null;
      end_date: string | null;
      is_active: boolean;
    } | null;
  }>(
    "/api/auth/me",
    createFetcher<{
      id: number;
      email: string;
      role: string;
      is_active: boolean;
      subscription: {
        plan_type: string;
        start_date: string | null;
        end_date: string | null;
        is_active: boolean;
      } | null;
    }>("/api/auth/me"),
    {
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 60000,
    }
  );

  return {
    user: data,
    isLoading,
    isError: !!error,
    error: error?.message,
    mutate,
  };
}

export {
  isFyersNotConnected,
  isFyersError,
  isFyersUnreachable,
  isServerWakingUp,
  isAuthError,
  formatFyersSymbol,
  SERVER_WAKING_MESSAGE,
} from "@/lib/api-client";