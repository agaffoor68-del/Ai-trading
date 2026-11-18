"use client";

import useSWR, { mutate as mutateSWR } from "swr";
import {
  fetchWithTimeout,
  parseApiError,
  isServerWakingUp,
  isFyersNotConnected,
  isFyersError,
  isFyersUnreachable,
  isAuthError,
} from "@/lib/api-client";

const FYERS_STATUS_KEY = "/api/v1/fyers/status";

interface OptionLegData {
  symbol?: string | null;
  ltp?: number | null;
  oi?: number | null;
  oi_change?: number | null;
  oi_change_pct?: number | null;
  volume?: number | null;
  bid?: number | null;
  ask?: number | null;
}

/** A strike row as returned by the option-chain API. */
export interface StrikeData {
  strike: number;
  is_atm: boolean;
  call_itm: boolean;
  put_itm: boolean;
  call: OptionLegData | null;
  put: OptionLegData | null;
}

interface OptionChainResponse {
  symbol: string;
  expiry: string;
  spot_price: number;
  atm_strike: number;
  strike_interval: number;
  option_chain: StrikeData[];
  /** Optional legacy/enveloped array shape supported by some deployments. */
  data?: StrikeData[];
  expiries: string[];
  timestamp: string;
}

function isFyersSessionExpired(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const candidate = error as { status?: number; code?: string | number; message?: string };
  return candidate.status === 401 && (
    isFyersNotConnected(error) ||
    /fyers.{0,30}(token|expired|auth|connect)/i.test(candidate.message ?? "")
  );
}

function markFyersDisconnected(): void {
  // SWR's shared cache is the global connection state consumed by the header
  // and every market-data panel.
  void mutateSWR(FYERS_STATUS_KEY, (current: any) => {
    if (current?.fyers && typeof current.fyers === "object") {
      return { ...current, fyers: { ...current.fyers, connected: false, valid: false, message: "Fyers session expired" } };
    }
    return { ...(current ?? {}), connected: false, valid: false, message: "Fyers session expired" };
  }, { revalidate: false });
}

function handleApiError(payload: unknown, status: number): Error & { code?: string | number; status?: number } {
  const error = parseApiError(payload, status) as Error & { code?: string | number; status?: number };
  if (isFyersSessionExpired(error)) {
    error.message = "Fyers Session Expired. Please Reconnect.";
    markFyersDisconnected();
  }
  return error;
}

const createFetcher = <T,>(key: string) => async (): Promise<T> => {
  const response = await fetchWithTimeout(key, { credentials: "same-origin" });
  if (!response.ok) {
    const error = handleApiError(await response.json().catch(() => null), response.status);
    if (response.status === 401 && !isFyersSessionExpired(error) && !isFyersNotConnected(error) && typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`;
    }
    throw error;
  }
  return response.json();
};

const createPostFetcher = <T,>(key: string, body: unknown) => async (): Promise<T> => {
  const response = await fetchWithTimeout(key, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "same-origin",
  });
  if (!response.ok) {
    const error = handleApiError(await response.json().catch(() => null), response.status);
    if (response.status === 401 && !isFyersSessionExpired(error) && !isFyersNotConnected(error) && typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`;
    }
    throw error;
  }
  return response.json();
};

type Quote = {
  symbol?: string;
  ltp?: number | null;
  change?: number | null;
  change_percent?: number | null;
  changePercent?: number | null;
  updated_at?: string;
  [key: string]: unknown;
};

function normalizeQuotes(payload: unknown): Record<string, Quote> {
  if (!payload || typeof payload !== "object") return {};
  const response = payload as { quotes?: unknown; data?: unknown };
  const rows = Array.isArray(response.data) ? response.data : Array.isArray(response.quotes) ? response.quotes : null;
  if (rows) {
    return rows.reduce<Record<string, Quote>>((result, row) => {
      if (!row || typeof row !== "object") return result;
      const quote = row as Quote;
      if (quote.symbol) result[quote.symbol] = quote;
      return result;
    }, {});
  }
  return response.quotes && typeof response.quotes === "object" ? response.quotes as Record<string, Quote> : {};
}

function isFyersConnected(status: any): boolean {
  const fyers = status?.fyers ?? status;
  return Boolean(fyers?.connected && fyers?.valid);
}

export function useMarketQuotes(symbols: string[]) {
  const stableSymbols = [...symbols].sort();
  const symbolsKey = stableSymbols.join(",");
  const { data, error, isLoading, mutate } = useSWR<unknown>(
    symbolsKey ? ["/api/v1/market/quotes", symbolsKey] : null,
    () => createPostFetcher<unknown>("/api/v1/market/quotes", { symbols: stableSymbols })(),
    {
      refreshInterval: (payload) => {
        const quotes = normalizeQuotes(payload);
        const hasRecent = Object.values(quotes).some((quote) => quote.updated_at && Date.now() - new Date(quote.updated_at).getTime() < 60000);
        return hasRecent ? 3000 : 30000;
      },
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 2000,
    },
  );
  const { status } = useFyersStatus();
  const quotes = normalizeQuotes(data);
  const sessionExpired = isFyersSessionExpired(error);
  console.log("API Response (quotes):", data);
  return {
    quotes: sessionExpired ? {} : quotes,
    response: data && typeof data === "object" ? { data } : undefined,
    total: (data as any)?.total ?? Object.keys(quotes).length,
    isLoading,
    isError: !!error,
    error: (error as any)?.message,
    errorCode: (error as any)?.code,
    isFyersNotConnected: sessionExpired || (!isFyersConnected(status) && isFyersNotConnected(error)),
    isFyersConnected: isFyersConnected(status) && !sessionExpired,
    isFyersError: isFyersError(error),
    isFyersUnreachable: isFyersUnreachable(error),
    isServerWakingUp: isServerWakingUp(error),
    mutate,
  };
}

export function useOptionChain(symbol: string, expiry: string, strikes = 10) {
  const key = symbol && expiry ? `/api/v1/market/option-chain?symbol=${encodeURIComponent(symbol)}&expiry=${encodeURIComponent(expiry)}&strikes=${strikes}` : null;
  const { data, error, isLoading, mutate } = useSWR<OptionChainResponse>(key, key ? createFetcher<OptionChainResponse>(key) : null, {
    refreshInterval: (payload) => payload ? 3000 : 30000,
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    dedupingInterval: 2000,
  });
  const { status } = useFyersStatus();
  const sessionExpired = isFyersSessionExpired(error);
  console.log("API Response (option-chain):", data);
  return {
    chainData: sessionExpired ? undefined : data,
    isLoading,
    isError: !!error,
    error: (error as any)?.message,
    errorCode: (error as any)?.code,
    isFyersNotConnected: sessionExpired || (!isFyersConnected(status) && isFyersNotConnected(error)),
    isFyersConnected: isFyersConnected(status) && !sessionExpired,
    isFyersError: isFyersError(error),
    isFyersUnreachable: isFyersUnreachable(error),
    isServerWakingUp: isServerWakingUp(error),
    mutate,
  };
}

export function useAISignals(symbols: string[] = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]) {
  const query = symbols.map(encodeURIComponent).join(",");
  const key = symbols.length ? `/api/v1/market/ai/signals?symbols=${query}` : null;
  const { data, error, isLoading, mutate } = useSWR<any>(key, key ? createFetcher<any>(key) : null, {
    refreshInterval: 30000, revalidateOnFocus: true, revalidateOnReconnect: true, dedupingInterval: 10000,
  });
  const { status } = useFyersStatus();
  const sessionExpired = isFyersSessionExpired(error);
  const signals = sessionExpired ? [] : Array.isArray(data) ? data : Array.isArray(data?.signals) ? data.signals : [];
  console.log("API Response (ai-signals):", data);
  return {
    signals,
    timestamp: data?.timestamp,
    isLoading,
    isError: !!error,
    error: (error as any)?.message,
    errorCode: (error as any)?.code,
    isFyersNotConnected: sessionExpired || (!isFyersConnected(status) && isFyersNotConnected(error)),
    isFyersConnected: isFyersConnected(status) && !sessionExpired,
    isFyersError: isFyersError(error),
    isFyersUnreachable: isFyersUnreachable(error),
    isServerWakingUp: isServerWakingUp(error),
    mutate,
  };
}

export function useCandles(symbol: string, interval = "5m", days = 5) {
  const key = symbol ? `/api/v1/market/candles?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&days=${days}` : null;
  const { data, error, isLoading, mutate } = useSWR<any>(key, key ? createFetcher<any>(key) : null, {
    refreshInterval: 60000, revalidateOnFocus: true, revalidateOnReconnect: true, dedupingInterval: 30000,
  });
  const sessionExpired = isFyersSessionExpired(error);
  return {
    candles: sessionExpired ? [] : data?.candles || [],
    isLoading,
    isError: !!error,
    error: sessionExpired ? "Data unavailable. Please reconnect Fyers." : (error as any)?.message,
    errorCode: (error as any)?.code,
    isFyersNotConnected: sessionExpired || isFyersNotConnected(error),
    isFyersConnected: !sessionExpired,
    isFyersError: isFyersError(error),
    isFyersUnreachable: isFyersUnreachable(error),
    isServerWakingUp: isServerWakingUp(error),
    mutate,
  };
}

export function useMarketStatus() {
  const { data, error, isLoading, mutate } = useSWR<any>("/api/v1/market/status", createFetcher<any>("/api/v1/market/status"), {
    refreshInterval: 30000, revalidateOnFocus: true, revalidateOnReconnect: true, dedupingInterval: 10000,
  });
  return { status: data, isLoading, isError: !!error, error: (error as any)?.message, mutate };
}

export function useFyersStatus() {
  const { data, error, isLoading, mutate } = useSWR<any>(FYERS_STATUS_KEY, createFetcher<any>(FYERS_STATUS_KEY), {
    refreshInterval: 30000, revalidateOnFocus: true, revalidateOnReconnect: true, dedupingInterval: 10000,
  });
  return { status: data, isLoading, isError: !!error, error: (error as any)?.message, mutate };
}

export function useFullStatus() {
  const result = useFyersStatus();
  console.log("API Response (fyers/status):", result.status);
  return result;
}

export function useExpiries(symbol: string) {
  const key = symbol ? `/api/v1/market/expiries?symbol=${encodeURIComponent(symbol)}` : null;
  const { data, error, isLoading, mutate } = useSWR<{ expiries?: string[] }>(key, key ? createFetcher<{ expiries?: string[] }>(key) : null, {
    refreshInterval: 3600000, revalidateOnFocus: true, revalidateOnReconnect: true, dedupingInterval: 300000,
  });
  return { expiries: data?.expiries || [], isLoading, isError: !!error, error: (error as any)?.message, mutate };
}

export function useMe() {
  const { data, error, isLoading, mutate } = useSWR<any>("/api/auth/me", createFetcher<any>("/api/auth/me"), {
    revalidateOnFocus: true, revalidateOnReconnect: true, dedupingInterval: 60000,
  });
  return { user: data, isLoading, isError: !!error, error: (error as any)?.message, mutate };
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
