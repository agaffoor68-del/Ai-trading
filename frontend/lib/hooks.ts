"use client";

import useSWR, { mutate } from "swr";
import { 
  api, 
  type AISignal, 
  type AISignalsResponse, 
  type OptionChainResponse, 
  type QuotesResponse,
  type MarketStatusResponse,
  isFyersNotConnected,
  isFyersError,
  isFyersUnreachable,
  formatFyersSymbol
} from "@/lib/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

// Helper to create fetcher with proper error handling
const createFetcher = <T,>(key: string) => async (): Promise<T> => {
  const response = await fetch(`${API_BASE_URL}${key}`, {
    signal: AbortSignal.timeout(10000),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ code: "UNKNOWN", message: `HTTP ${response.status}` })) as { code: string; message: string };
    const err = new Error(error.message || `HTTP ${response.status}`) as Error & { code?: string; status?: number };
    err.code = error.code;
    err.status = response.status;
    throw err;
  }
  
  return response.json();
};

// Helper for POST requests
const createPostFetcher = <T,>(key: string, body: any) => async (): Promise<T> => {
  const response = await fetch(`${API_BASE_URL}${key}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(10000),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ code: "UNKNOWN", message: `HTTP ${response.status}` })) as { code: string; message: string };
    const err = new Error(error.message || `HTTP ${response.status}`) as Error & { code?: string; status?: number };
    err.code = error.code;
    err.status = response.status;
    throw err;
  }
  
  return response.json();
};

export { isFyersNotConnected, isFyersError, isFyersUnreachable, formatFyersSymbol } from "@/lib/api";

export function useMarketQuotes(symbols: string[]) {
  const symbolsKey = symbols.length > 0 ? symbols.sort().join(",") : "";
  
  const { data, error, isLoading, mutate } = useSWR<QuotesResponse>(
    symbolsKey ? [`/api/v1/market/quotes`, symbols] : null,
    ([, syms]) => createPostFetcher<QuotesResponse>("/api/v1/market/quotes", { symbols: syms })(),
    {
      refreshInterval: (data) => {
        // Refresh every 2-3s during market hours, 30s when closed
        if (data?.quotes) {
          // Check if any quote has recent data
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
    mutate,
  };
}

export function useOptionChain(symbol: string, expiry: string, strikes = 10) {
  const { data, error, isLoading, mutate } = useSWR<OptionChainResponse>(
    symbol && expiry ? `/api/v1/market/option-chain?symbol=${encodeURIComponent(symbol)}&expiry=${encodeURIComponent(expiry)}&strikes=${strikes}` : null,
    createFetcher<OptionChainResponse>(`/api/v1/market/option-chain?symbol=${encodeURIComponent(symbol)}&expiry=${encodeURIComponent(expiry)}&strikes=${strikes}`),
    {
      refreshInterval: (data) => {
        // Refresh every 3s during market hours if we have data
        return data ? 3000 : 30000;
      },
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 2000,
    }
  );

  return {
    chainData: data,
    isLoading,
    isError: !!error,
    error: error?.message,
    errorCode: (error as any)?.code,
    isFyersNotConnected: isFyersNotConnected(error),
    isFyersError: isFyersError(error),
    isFyersUnreachable: isFyersUnreachable(error),
    mutate,
  };
}

export function useAISignals(symbols: string[] = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]) {
  const { data, error, isLoading, mutate } = useSWR<AISignalsResponse>(
    symbols.length > 0 ? `/api/v1/market/ai/signals?symbols=${symbols.join(",")}` : null,
    createFetcher<AISignalsResponse>(`/api/v1/market/ai/signals?symbols=${symbols.join(",")}`),
    {
      refreshInterval: 30000,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 10000,
    }
  );

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
    mutate,
  };
}

export function useCandles(symbol: string, interval: string = "5m", days: number = 5) {
  const { data, error, isLoading, mutate } = useSWR<any[]>(
    symbol ? `/api/v1/market/candles?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&days=${days}` : null,
    createFetcher<any[]>(`/api/v1/market/candles?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&days=${days}`),
    {
      refreshInterval: 60000, // Candles don't need frequent refresh
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 30000,
    }
  );

  return {
    candles: data || [],
    isLoading,
    isError: !!error,
    error: error?.message,
    errorCode: (error as any)?.code,
    isFyersNotConnected: isFyersNotConnected(error),
    isFyersError: isFyersError(error),
    isFyersUnreachable: isFyersUnreachable(error),
    mutate,
  };
}

export function useMarketStatus() {
  const { data, error, isLoading, mutate } = useSWR<MarketStatusResponse>(
    "/api/market/status",
    createFetcher<MarketStatusResponse>("/api/market/status"),
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
    "/api/fyers/status",
    createFetcher<any>("/api/fyers/status"),
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

export function useExpiries(symbol: string) {
  const { data, error, isLoading, mutate } = useSWR<any>(
    symbol ? `/api/v1/market/expiries?symbol=${encodeURIComponent(symbol)}` : null,
    createFetcher<any>(`/api/v1/market/expiries?symbol=${encodeURIComponent(symbol)}`),
    {
      refreshInterval: 3600000, // 1 hour - expiries don't change often
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

export async function placeOrder(orderData: any) {
  const response = await fetch(`${API_BASE_URL}/api/v1/execution/order`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(orderData),
    signal: AbortSignal.timeout(15000),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ code: "UNKNOWN", message: "Order failed" })) as { code: string; message: string };
    const err = new Error(error.message || `HTTP ${response.status}`) as Error & { code?: string; status?: number };
    err.code = error.code;
    err.status = response.status;
    throw err;
  }

  return response.json();
}

export async function connectFyers(clientId: string, clientSecret: string) {
  const response = await fetch(`${API_BASE_URL}/api/v1/fyers/connect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: clientId, client_secret: clientSecret }),
    signal: AbortSignal.timeout(10000),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ code: "UNKNOWN", message: "Failed to connect" })) as { code: string; message: string };
    const err = new Error(error.message || `HTTP ${response.status}`) as Error & { code?: string; status?: number };
    err.code = error.code;
    err.status = response.status;
    throw err;
  }

  return response.json();
}

export function invalidateAllCache() {
  mutate("/api/v1/market/quotes");
  mutate("/api/v1/market/option-chain");
  mutate("/api/v1/market/ai/signals");
  mutate("/api/v1/execution/positions");
  mutate("/api/market/status");
  mutate("/api/v1/fyers/status");
  mutate("/api/fyers/status");
}