"use client";

import { useState, useEffect, useCallback } from "react";
import { type MarketStatusResponse } from "@/lib/api";
import { fetchWithTimeout, isServerWakingUp, SERVER_WAKING_MESSAGE } from "@/lib/api-client";

export function useMarketStatus() {
  const [status, setStatus] = useState<MarketStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetchWithTimeout("/api/v1/market/status", {
        credentials: "same-origin",
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      setStatus(data);
      setError(null);
    } catch (err) {
      setError(isServerWakingUp(err) ? SERVER_WAKING_MESSAGE : err instanceof Error ? err.message : "Failed to fetch market status");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    // Refresh every 30 seconds
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  return { ...status, isLoading, error };
}