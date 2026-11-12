"use client";

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  FlaskConical,
  RotateCcw,
  TrendingUp,
  TrendingDown,
  DollarSign,
  ArrowRight,
  AlertCircle,
  CheckCircle,
  Activity,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";

interface PaperTrade {
  id: string;
  symbol: string;
  type: "CE" | "PE";
  side: "BUY" | "SELL";
  entry: number;
  exit: number | null;
  qty: number;
  pnl: number | null;
  status: "OPEN" | "CLOSED";
  timestamp: string;
}

const MOCK_TRADES: PaperTrade[] = [
  {
    id: "1",
    symbol: "NIFTY 24350 CE",
    type: "CE",
    side: "BUY",
    entry: 145.50,
    exit: 167.80,
    qty: 50,
    pnl: 1115,
    status: "CLOSED",
    timestamp: "2024-11-10 10:30:00",
  },
  {
    id: "2",
    symbol: "BANKNIFTY 51900 PE",
    type: "PE",
    side: "BUY",
    entry: 210.25,
    exit: 185.40,
    qty: 25,
    pnl: -621,
    status: "CLOSED",
    timestamp: "2024-11-10 11:45:00",
  },
  {
    id: "3",
    symbol: "NIFTY 24400 CE",
    type: "CE",
    side: "BUY",
    entry: 120.00,
    exit: null,
    qty: 50,
    pnl: null,
    status: "OPEN",
    timestamp: "2024-11-11 09:15:00",
  },
  {
    id: "4",
    symbol: "SENSEX 79800 CE",
    type: "CE",
    side: "SELL",
    entry: 180.50,
    exit: 155.20,
    qty: 10,
    pnl: 253,
    status: "CLOSED",
    timestamp: "2024-11-11 10:30:00",
  },
  {
    id: "5",
    symbol: "NIFTY 24300 PE",
    type: "PE",
    side: "BUY",
    entry: 85.75,
    exit: null,
    qty: 50,
    pnl: null,
    status: "OPEN",
    timestamp: "2024-11-11 11:00:00",
  },
];

export default function PaperTradingPage() {
  const [virtualBalance, setVirtualBalance] = useState(1000000);
  const [trades] = useState<PaperTrade[]>(MOCK_TRADES);

  const handleReset = () => {
    if (confirm("Reset virtual account to ₹10,00,000? This will clear all paper trade history.")) {
      setVirtualBalance(1000000);
    }
  };

  const formatCurrency = (val: number) => `₹${val.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
  const formatPnL = (pnl: number | null) => {
    if (pnl === null) return "—";
    const sign = pnl >= 0 ? "+" : "";
    return `${sign}${formatCurrency(pnl)}`;
  };

  const totalPnL = trades.reduce((sum, t) => sum + (t.pnl || 0), 0);
  const openPositions = trades.filter((t) => t.status === "OPEN").length;
  const closedTrades = trades.filter((t) => t.status === "CLOSED");
  const winRate = closedTrades.length > 0 ? Math.round((closedTrades.filter((t) => (t.pnl || 0) > 0).length / closedTrades.length) * 100) : 0;

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="w-full lg:ml-64 min-h-screen flex flex-col">
        <Header />

        <main className="flex-1 p-4 md:p-8 lg:p-10 pt-20 lg:pt-24 space-y-8 max-w-6xl mx-auto w-full">
          {/* Page Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight flex items-center gap-3">
              <FlaskConical className="w-8 h-8 text-neon-purple drop-shadow-[0_0_10px_rgba(168,85,247,0.6)]" strokeWidth={2.5} />
              Paper Trading
            </h1>
            <p className="text-text-secondary mt-1">Simulated trading environment with virtual capital</p>
          </motion.div>

          {/* Account Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="glass rounded-2xl border border-glow-border p-4 md:p-6"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-text-muted uppercase tracking-wider">Virtual Balance</p>
                  <p className="text-2xl md:text-3xl font-bold text-white mt-1 font-mono">{formatCurrency(virtualBalance)}</p>
                </div>
                <div className="w-12 h-12 md:w-14 md:h-14 rounded-xl bg-neon-purple/20 flex items-center justify-center">
                  <DollarSign className="w-6 h-6 md:w-7 md:h-7 text-neon-purple" strokeWidth={2.5} />
                </div>
              </div>
              <motion.button
                onClick={handleReset}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="mt-4 w-full py-2.5 rounded-xl bg-neon-red/10 border border-neon-red/30 text-neon-red font-medium text-sm hover:bg-neon-red/20 transition-colors"
              >
                <RotateCcw className="w-4 h-4 mr-2" strokeWidth={2.5} />
                Reset Virtual Account
              </motion.button>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 }}
              className="glass rounded-2xl border border-glow-border p-4 md:p-6"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-text-muted uppercase tracking-wider">Total PnL</p>
                  <p className={`text-2xl md:text-3xl font-bold mt-1 font-mono ${totalPnL >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                    {formatPnL(totalPnL)}
                  </p>
                </div>
                <div className="w-12 h-12 md:w-14 md:h-14 rounded-xl bg-neon-green/20 flex items-center justify-center">
                  <TrendingUp className="w-6 h-6 md:w-7 md:h-7 text-neon-green" strokeWidth={2.5} />
                </div>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="glass rounded-2xl border border-glow-border p-4 md:p-6"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-text-muted uppercase tracking-wider">Open Positions</p>
                  <p className="text-2xl md:text-3xl font-bold text-white mt-1">{openPositions}</p>
                </div>
                <div className="w-12 h-12 md:w-14 md:h-14 rounded-xl bg-neon-cyan/20 flex items-center justify-center">
                  <Activity className="w-6 h-6 md:w-7 md:h-7 text-neon-cyan" strokeWidth={2.5} />
                </div>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.25 }}
              className="glass rounded-2xl border border-glow-border p-4 md:p-6"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-text-muted uppercase tracking-wider">Win Rate</p>
                  <p className="text-2xl md:text-3xl font-bold text-white mt-1">{winRate}%</p>
                </div>
                <div className="w-12 h-12 md:w-14 md:h-14 rounded-xl bg-neon-orange/20 flex items-center justify-center">
                  <CheckCircle className="w-6 h-6 md:w-7 md:h-7 text-neon-orange" strokeWidth={2.5} />
                </div>
              </div>
            </motion.div>
          </div>

          {/* Recent Paper Trades Table */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="glass rounded-2xl border border-glow-border overflow-hidden"
          >
            <div className="px-4 md:px-6 py-4 border-b border-glow-border bg-card-bg/50 flex items-center justify-between flex-wrap gap-4">
              <h2 className="text-lg font-semibold text-white">Recent Paper Trades</h2>
              <span className="text-xs text-text-muted">{trades.length} trades</span>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-[900px] w-full border-collapse" role="grid">
                <thead>
                  <tr className="border-b border-glow-border bg-card-bg/50 text-text-muted text-xs font-medium uppercase tracking-wider">
                    <th className="px-3 md:px-5 py-3 md:py-4 text-left">Symbol</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-center">Type</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-center">Side</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-right">Entry</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-right">Exit</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-right">Qty</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-right">PnL</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-center">Status</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-left">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((trade, index) => {
                    const isPositive = trade.pnl !== null && trade.pnl >= 0;
                    return (
                      <motion.tr
                        key={trade.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 + index * 0.03 }}
                        className="border-b border-glow-border/50 hover:bg-card-bg/30 transition-colors"
                      >
                        <td className="px-3 md:px-5 py-3 md:py-4">
                          <span className="font-mono font-medium text-white">{trade.symbol}</span>
                        </td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-center">
                          <span className={`text-sm font-bold ${trade.type === "CE" ? "text-neon-green" : "text-neon-red"}`}>
                            {trade.type}
                          </span>
                        </td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-center">
                          <span className={`text-sm font-bold ${trade.side === "BUY" ? "text-neon-green" : "text-neon-red"}`}>
                            {trade.side}
                          </span>
                        </td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-right font-mono text-text-secondary">{formatCurrency(trade.entry)}</td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-right font-mono text-text-secondary">{trade.exit ? formatCurrency(trade.exit) : "—"}</td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-right font-mono text-white">{trade.qty.toLocaleString()}</td>
                        <td className={`px-3 md:px-5 py-3 md:py-4 text-right font-mono font-medium ${trade.pnl === null ? "text-text-muted" : isPositive ? "text-neon-green" : "text-neon-red"}`}>
                          {formatPnL(trade.pnl)}
                        </td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-center">
                          <span className={`px-3 py-1 rounded-full text-xs font-medium ${trade.status === "OPEN" ? "bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/30" : "bg-neon-green/20 text-neon-green border border-neon-green/30"}`}>
                            {trade.status}
                          </span>
                        </td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-left text-text-secondary text-sm">{trade.timestamp}</td>
                      </motion.tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </motion.div>
        </main>
      </div>
    </div>
  );
}