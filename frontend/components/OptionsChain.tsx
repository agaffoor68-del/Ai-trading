"use client";

import { motion } from "framer-motion";
import { Maximize2, Search, Filter } from "lucide-react";
import useSWR from "swr";
import { api, formatFyersSymbol } from "@/lib/api";

interface OptionChainStrike {
  strike: number;
  call_ltp: number | null;
  call_change_percent: number | null;
  call_oi: number | null;
  put_ltp: number | null;
  put_change_percent: number | null;
  put_oi: number | null;
}

interface OptionChainData {
  symbol: string;
  expiry: string;
  spot_price: number;
  atm_strike: number;
  option_chain: OptionChainStrike[];
}

// Default index for dashboard
const DEFAULT_INDEX = "NIFTY";

export function OptionsChain() {
  // Fetch option chain for default index
  const { data: chainData, isLoading, error, mutate } = useSWR<OptionChainData>(
    `dashboard-option-chain-${DEFAULT_INDEX}`,
    async () => {
      // We need to fetch expiry first, then option chain
      // For dashboard, use a simple approach - fetch from the option-chain endpoint
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com"}/api/v1/market/option-chain?symbol=${DEFAULT_INDEX}`, {
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) {
        // If no expiry provided, backend will auto-find nearest expiry
        throw new Error(`HTTP ${response.status}`);
      }
      return response.json();
    },
    {
      refreshInterval: 5000,
      revalidateOnFocus: false,
      dedupingInterval: 3000,
    }
  );

  // Transform backend data to UI format
  const transformedStrikes = chainData?.option_chain?.map((strike: any) => ({
    strike: strike.strike,
    isATM: strike.strike === chainData.atm_strike,
    ceLtp: strike.call_ltp ?? 0,
    ceChange: strike.call_change_percent ?? 0,
    ceOI: strike.call_oi ?? 0,
    ceOIChange: strike.call_change_percent ?? 0,
    peLtp: strike.put_ltp ?? 0,
    peChange: strike.put_change_percent ?? 0,
    peOI: strike.put_oi ?? 0,
    peOIChange: strike.put_change_percent ?? 0,
  })) || [];

  const formatNumber = (n: number) => n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const formatOI = (n: number) => n.toLocaleString();

  if (isLoading) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[350px] flex flex-col"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-glow-border bg-card-bg/50">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-white">Options Chain</h3>
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-cyan/20 text-neon-cyan font-medium">NIFTY</span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-orange/20 text-neon-orange font-medium">{chainData?.expiry || "LOADING..."}</span>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3 text-text-secondary">
            <span className="animate-spin">⏳</span>
            <span>Loading option chain...</span>
          </div>
        </div>
      </motion.div>
    );
  }

  if (error) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[350px] flex flex-col"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-glow-border bg-card-bg/50">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-white">Options Chain</h3>
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-cyan/20 text-neon-cyan font-medium">NIFTY</span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-red/20 text-neon-red font-medium">ERROR</span>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-center text-text-secondary">
            <p className="mb-2">Failed to load option chain</p>
            <p className="text-sm text-neon-red/80">{error.message}</p>
          </div>
        </div>
      </motion.div>
    );
  }

  if (!chainData || !transformedStrikes.length) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[350px] flex flex-col"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-glow-border bg-card-bg/50">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-white">Options Chain</h3>
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-cyan/20 text-neon-cyan font-medium">NIFTY</span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-orange/20 text-neon-orange font-medium">{chainData?.expiry || "NO DATA"}</span>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-text-muted">
            <p>No live data. Please connect Fyers.</p>
          </div>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.5 }}
      className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[350px] flex flex-col"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-glow-border bg-card-bg/50">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-white">Options Chain</h3>
          <span className="text-[10px] px-2 py-0.5 rounded bg-neon-cyan/20 text-neon-cyan font-medium">NIFTY</span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-neon-orange/20 text-neon-orange font-medium">{chainData.expiry}</span>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={() => mutate()}
            className="p-1.5 rounded-lg bg-card-bg border border-glow-border hover:border-neon-cyan/50 transition-colors" 
            title="Refresh"
          >
            <Maximize2 className="w-4 h-4 text-text-secondary" strokeWidth={2} />
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-x-auto overflow-y-auto p-2">
        <table className="w-full text-sm" role="grid">
          <thead>
            <tr className="border-b border-glow-border text-text-muted">
              <th className="px-2 py-2 text-left font-medium">Call LTP</th>
              <th className="px-2 py-2 text-right font-medium">Call OI</th>
              <th className="px-2 py-2 text-right font-medium">Δ OI</th>
              <th className="px-2 py-2 text-center font-medium w-20">STRIKE</th>
              <th className="px-2 py-2 text-right font-medium">Δ OI</th>
              <th className="px-2 py-2 text-right font-medium">Put OI</th>
              <th className="px-2 py-2 text-right font-medium">Put LTP</th>
            </tr>
          </thead>
          <tbody>
            {transformedStrikes.map((row, index) => (
              <motion.tr
                key={row.strike}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 + index * 0.04 }}
                className={`transition-colors ${row.isATM ? "bg-gradient-to-r from-neon-cyan/5 via-neon-yellow/5 to-transparent" : "hover:bg-card-bg"}`}
                style={row.isATM ? { boxShadow: "inset 0 0 0 1px rgba(0, 240, 255, 0.1)" } : undefined}
              >
                <td className="px-2 py-1.5 font-mono font-medium text-neon-green">{formatNumber(row.ceLtp)}</td>
                <td className="px-2 py-1.5 text-right font-mono text-text-secondary">{formatOI(row.ceOI)}</td>
                <td className={`px-2 py-1.5 text-right font-mono text-xs ${row.ceOIChange >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                  {row.ceOIChange >= 0 ? "+" : ""}{row.ceOIChange.toFixed(1)}%
                </td>
                <td className={`px-2 py-1.5 text-center font-mono font-bold ${row.isATM ? "text-neon-cyan text-glow-cyan" : "text-white"}`}>
                  {row.strike.toLocaleString()}
                  {row.isATM && <span className="ml-1 text-[10px] bg-neon-cyan/20 text-neon-cyan px-1 rounded">ATM</span>}
                </td>
                <td className={`px-2 py-1.5 text-right font-mono text-xs ${row.peOIChange >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                  {row.peOIChange >= 0 ? "+" : ""}{row.peOIChange.toFixed(1)}%
                </td>
                <td className="px-2 py-1.5 text-right font-mono text-text-secondary">{formatOI(row.peOI)}</td>
                <td className="px-2 py-1.5 font-mono font-medium text-neon-red">{formatNumber(row.peLtp)}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}
