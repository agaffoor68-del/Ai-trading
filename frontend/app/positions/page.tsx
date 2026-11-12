"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Briefcase,
  TrendingUp,
  TrendingDown,
  X,
  RotateCcw,
  Loader2,
  RefreshCw,
  AlertCircle,
  CheckCircle,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import useSWR from "swr";
import { api, type Position, type PositionsResponse } from "@/lib/api";

const fetcher = (url: string) => fetch(url).then((res) => {
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
});

export default function PositionsPage() {
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const { data, error, isLoading, mutate } = useSWR<PositionsResponse>(
    "/api/v1/execution/positions",
    (url) => fetcher(`${process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com"}${url}`),
    {
      refreshInterval: 5000,
      revalidateOnFocus: true,
      revalidateOnReconnect: true,
      dedupingInterval: 2000,
    }
  );

  const positions = data?.positions || [];

  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const handleSquareOffAll = async () => {
    if (!confirm("Square off ALL open positions? This cannot be undone.")) return;
    try {
      // TODO: Call bulk square-off endpoint when available
      showToast("Square-off all not yet implemented", "error");
    } catch {
      showToast("Failed to square off positions", "error");
    }
  };

  const handleClosePosition = async (position: Position) => {
    if (!confirm(`Close position for ${position.symbol}?`)) return;
    try {
      // TODO: Call individual close endpoint when available
      showToast(`Close position for ${position.symbol} not yet implemented`, "error");
    } catch {
      showToast("Failed to close position", "error");
    }
  };

  const formatPnL = (pnl: number) => {
    const sign = pnl >= 0 ? "+" : "";
    return `${sign}₹${pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
  };

  const formatPnLPercent = (pnlPercent: number) => {
    const sign = pnlPercent >= 0 ? "+" : "";
    return `${sign}${pnlPercent.toFixed(2)}%`;
  };

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="ml-64 min-h-screen flex flex-col">
        <Header />

        <main className="flex-1 p-6 md:p-8 lg:p-10 pt-20 lg:pt-24 space-y-6">
          {/* Page Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Briefcase className="w-8 h-8 text-neon-cyan drop-shadow-[0_0_10px_rgba(0,240,255,0.6)]" strokeWidth={2.5} />
              <div>
                <h1 className="text-3xl font-bold text-white tracking-tight">Positions</h1>
                <p className="text-text-secondary">Real-time position tracking with PnL</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <motion.button
                onClick={handleSquareOffAll}
                disabled={positions.length === 0 || isLoading}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-neon-red/10 border border-neon-red/30 text-neon-red font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:bg-neon-red/20 glass"
              >
                <RotateCcw className="w-4 h-4" strokeWidth={2.5} />
                <span>Square Off All</span>
              </motion.button>
              <motion.button
                onClick={() => mutate()}
                disabled={isLoading}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-card-bg border border-glow-border hover:border-neon-cyan/50 text-white font-medium transition-all disabled:opacity-50 glass"
              >
                <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} strokeWidth={2.5} />
                <span>Refresh</span>
              </motion.button>
            </div>
          </div>

          {/* Toast Notification */}
          {toast && (
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
              className={`fixed top-6 right-6 px-6 py-4 rounded-xl border text-white font-medium z-50 shadow-lg ${
                toast.type === "success"
                  ? "bg-neon-green/20 border-neon-green/50 text-neon-green shadow-[0_0_20px_rgba(0,255,102,0.3)]"
                  : "bg-neon-red/20 border-neon-red/50 text-neon-red shadow-[0_0_20px_rgba(255,0,60,0.3)]"
              }`}
            >
              <div className="flex items-center gap-2">
                {toast.type === "success" ? (
                  <CheckCircle className="w-5 h-5" strokeWidth={2.5} />
                ) : (
                  <AlertCircle className="w-5 h-5" strokeWidth={2.5} />
                )}
                <span>{toast.message}</span>
              </div>
            </motion.div>
          )}

          {/* Positions Table */}
          <div className="glass rounded-2xl border border-glow-border overflow-hidden">
            {isLoading ? (
              <div className="flex items-center justify-center h-64">
                <div className="flex flex-col items-center gap-3 text-text-secondary">
                  <Loader2 className="w-8 h-8 animate-spin text-neon-cyan" strokeWidth={2.5} />
                  <span>Loading positions...</span>
                </div>
              </div>
            ) : positions.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-80 text-center px-6">
                <Briefcase className="w-16 h-16 text-text-muted mb-4" strokeWidth={1.5} />
                <h2 className="text-xl font-semibold text-white mb-2">No Open Positions</h2>
                <p className="text-text-secondary mb-6 max-w-md">
                  You don't have any active positions. Start trading by placing an order.
                </p>
                <a
                  href="/order-ticket"
                  className="flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black font-bold hover:opacity-90 transition-opacity"
                >
                  <TrendingUp className="w-5 h-5" strokeWidth={2.5} />
                  Place a Trade
                </a>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full border-collapse" role="grid">
                  <thead>
                    <tr className="border-b border-glow-border bg-card-bg/50 text-text-muted text-xs font-medium uppercase tracking-wider">
                      <th className="px-5 py-4 text-left">Symbol</th>
                      <th className="px-5 py-4 text-center">Type</th>
                      <th className="px-5 py-4 text-right">Qty</th>
                      <th className="px-5 py-4 text-right">Entry Price</th>
                      <th className="px-5 py-4 text-right">Current Price</th>
                      <th className="px-5 py-4 text-right">PnL</th>
                      <th className="px-5 py-4 text-right">PnL %</th>
                      <th className="px-5 py-4 text-center">Status</th>
                      <th className="px-5 py-4 text-center">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((position, index) => {
                      const isPositive = position.pnl >= 0;
                      return (
                        <motion.tr
                          key={position.symbol}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: index * 0.03 }}
                          className="border-b border-glow-border/50 hover:bg-card-bg/30 transition-colors"
                        >
                          <td className="px-5 py-4">
                            <div className="flex items-center gap-3">
                              <span className="font-mono font-semibold text-white text-base">{position.symbol}</span>
                              <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${position.side === "LONG" ? "bg-neon-green/20 text-neon-green" : "bg-neon-red/20 text-neon-red"}`}>
                                {position.side}
                              </span>
                            </div>
                          </td>
                          <td className="px-5 py-4 text-center">
                            <span className={`text-sm font-mono ${position.symbol.includes("CE") || position.symbol.includes("CALL") ? "text-neon-green" : "text-neon-red"}`}>
                              {position.symbol.includes("PE") || position.symbol.includes("PUT") ? "PE" : "CE"}
                            </span>
                          </td>
                          <td className="px-5 py-4 text-right font-mono text-white">{position.quantity.toLocaleString()}</td>
                          <td className="px-5 py-4 text-right font-mono text-text-secondary">₹{position.avgPrice.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                          <td className="px-5 py-4 text-right font-mono text-neon-cyan">₹{position.ltp.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                          <td className={`px-5 py-4 text-right font-mono font-medium ${isPositive ? "text-neon-green" : "text-neon-red"}`}>
                            {formatPnL(position.pnl)}
                          </td>
                          <td className={`px-5 py-4 text-right font-mono font-medium ${isPositive ? "text-neon-green" : "text-neon-red"}`}>
                            {formatPnLPercent(position.pnlPercent)}
                          </td>
                          <td className="px-5 py-4 text-center">
                            <span className="px-3 py-1 rounded-full text-xs font-medium bg-neon-green/20 text-neon-green border border-neon-green/30">
                              Open
                            </span>
                          </td>
                          <td className="px-5 py-4 text-center">
                            <motion.button
                              onClick={() => handleClosePosition(position)}
                              disabled={isLoading}
                              whileHover={{ scale: 1.1 }}
                              whileTap={{ scale: 0.9 }}
                              className="p-2 rounded-lg bg-neon-red/10 border border-neon-red/30 text-neon-red hover:bg-neon-red/20 transition-colors disabled:opacity-50"
                              title="Close Position"
                            >
                              <X className="w-4 h-4" strokeWidth={2.5} />
                            </motion.button>
                          </td>
                        </motion.tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Summary Footer */}
          {positions.length > 0 && (
            <div className="glass rounded-2xl border border-glow-border p-6">
              <h3 className="font-semibold text-white mb-4">Portfolio Summary</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                <div className="text-center">
                  <p className="text-xs text-text-muted uppercase tracking-wider">Total Positions</p>
                  <p className="text-2xl font-bold text-white mt-1">{positions.length}</p>
                </div>
                <div className="text-center">
                  <p className="text-xs text-text-muted uppercase tracking-wider">Total Quantity</p>
                  <p className="text-2xl font-bold text-white mt-1">{positions.reduce((sum, p) => sum + p.quantity, 0).toLocaleString()}</p>
                </div>
                <div className="text-center">
                  <p className="text-xs text-text-muted uppercase tracking-wider">Total PnL</p>
                  <p className={`text-2xl font-bold mt-1 ${positions.reduce((sum, p) => sum + p.pnl, 0) >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                    {formatPnL(positions.reduce((sum, p) => sum + p.pnl, 0))}
                  </p>
                </div>
                <div className="text-center">
                  <p className="text-xs text-text-muted uppercase tracking-wider">Win Rate</p>
                  <p className="text-2xl font-bold text-white mt-1">
                    {positions.length > 0
                      ? `${Math.round((positions.filter((p) => p.pnl >= 0).length / positions.length) * 100)}%`
                      : "0%"}
                  </p>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}