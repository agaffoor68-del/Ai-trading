"use client";

import useSWR, { mutate } from "swr";
import { api, type AISignal, type AISignalsResponse, type OptionChainData, type QuotesResponse } from "@/lib/api";

export function useMarketQuotes(symbols: string[]) {
  const symbolsKey = symbols.sort().join(",");
  
  const { data, error, isLoading, mutate } = useSWR<QuotesResponse>(
    symbols.length > 0 ? `/api/v1/market/quotes?symbols=${symbolsKey}` : null,
    async (url) => {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com"}${url}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbols }),
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    },
    {
      refreshInterval: 5000,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 2000,
    }
  );

  return {
    quotes: data?.quotes || {},
    isLoading,
    isError: !!error,
    error: error?.message,
    mutate,
  };
}

export function useOptionChain(symbol: string, expiry: string) {
  const { data, error, isLoading, mutate } = useSWR<OptionChainData>(
    symbol && expiry ? `/api/v1/market/option-chain?symbol=${encodeURIComponent(symbol)}&expiry=${encodeURIComponent(expiry)}` : null,
    async (url) => {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com"}${url}`, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    },
    {
      refreshInterval: 5000,
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
    mutate,
  };
}

export function useAISignals() {
  const { data, error, isLoading, mutate } = useSWR<AISignalsResponse>(
    "/api/v1/ai/live-analysis",
    async (url) => {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com"}${url}`, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    },
    {
      refreshInterval: 30000,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 5000,
    }
  );

  return {
    signals: data?.signals || [],
    isLoading,
    isError: !!error,
    error: error?.message,
    mutate,
  };
}

export function usePositions() {
  const { data, error, isLoading, mutate } = useSWR<{ positions: any[] }>(
    "/api/v1/execution/positions",
    async (url) => {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com"}${url}`, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    },
    {
      refreshInterval: 5000,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 2000,
    }
  );

  return {
    positions: data?.positions || [],
    isLoading,
    isError: !!error,
    error: error?.message,
    mutate,
  };
}

export async function placeOrder(orderData: any) {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com"}/api/v1/execution/order`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(orderData),
      signal: AbortSignal.timeout(15000),
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: "Order failed" }));
    throw new Error(error.message || `HTTP ${response.status}`);
  }

  return response.json();
}

export function invalidateAllCache() {
  mutate("/api/v1/market/quotes");
  mutate("/api/v1/market/option-chain");
  mutate("/api/v1/ai/live-analysis");
  mutate("/api/v1/execution/positions");
}