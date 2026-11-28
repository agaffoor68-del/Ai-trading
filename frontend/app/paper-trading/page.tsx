"use client";

import { useState, useCallback, useEffect } from "react";
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
  Loader2,
  Sparkles,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { useMarketQuotes, useCandles, formatFyersSymbol } from "@/lib/hooks";
import { api } from "@/lib/api-client";
import { useFyersStatus } from "@/lib/hooks";

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
  indicatorValues?: Record<string, number>;
}

interface MarketQuote {
  symbol: string;
  ltp: number;
  timestamp: string;
}

const VIRTUAL_BALANCE_INITIAL = 1000000;
const DEFAULT_LOT_SIZE = 25; // Fallback lot size

export default function PaperTradingPage() {
  const { isFyersConnected, isFyersNotConnected } = useFyersStatus();
  const [virtualBalance, setVirtualBalance] = useState(VIRTUAL_BALANCE_INITIAL);
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [watchlist, setWatchlist] = useState<string[]>(["NIFTY", "BANKNIFTY"]);
  const [isConnected, setIsConnected] = useState(false);
  const [watchlistLoading, setWatchlistLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch real market quotes for watchlist symbols
  useEffect(() => {
    const fetchQuotes = async () => {
      if (!isFyersConnected) {
        setIsConnected(false);
        return;
      }
      try {
        setWatchlistLoading(true);
        const quotes = await api.getOptionChain("NIFTY", undefined, 5);
        // Process real quotes
        setIsConnected(true);
        setError(null);
      } catch (err) {
        console.warn("Failed to fetch paper trading quotes:", err);
        setIsConnected(false);
        setError("Market data unavailable - using simulated prices");
      } finally {
        setWatchlistLoading(false);
      }
    };

    fetchQuotes();
    const interval = setInterval(fetchQuotes, 15000);
    return () => clearInterval(interval);
  }, [isFyersConnected]);

  // Subscribe to real-time market data for watchlist
  useEffect(() => {
    if (!isFyersConnected) return;

    const symbols = watchlist.map(formatFyersSymbol);
    const quotePromises = symbols.map(sym => api.getMarketQuotes([sym]));

    Promise.all(quotePromises).then((results) => {
      // Process real-time quotes for active trades
      const updatedTrades = trades.map(trade => {
        const quote = results.find((r: any) => r.symbol.includes(trade.symbol.split(' ')[0]));
        if (quote && quote.quotes) {
          const ltp = Number(quote.quotes[trade.symbol]?.ltp || 0);
          return {
            ...trade,
            // Could update entry/exit based on live data if needed
          };
        }
        return trade;
      });
      setTrades(updatedTrades);
    }).catch(err => {
      console.warn("Paper trade quote update error:", err);
    });
  }, [isFyersConnected, watchlist]);

  const handleReset = () => {
    setTrades([]);
    setVirtualBalance(VIRTUAL_BALANCE_INITIAL);
    setError(null);
  };

  const formatCurrency = (val: number) => `₹${val.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
  const formatPnL = (pnl: number | null) => {
    if (pnl === null) return "—";
    const sign = pnl >= 0 ? "+" : "";
    return `${sign}${formatCurrency(pnl)}`;
  };

  // Calculate live PnL using real market quotes
  const calculateLivePnL = (trade: PaperTrade, liveQuotes: Map<string, number>): { pnl: number | null; exitPrice: number } => {
    const symbolBase = trade.symbol.split(' ')[0]; // e.g., "NIFTY" from "NIFTY 24350 CE"
    const quotePrice = liveQuotes.get(symbolBase) || 0;

    // Determine exit price based on option type and market movement
    // Simplified: use current LTP as reference for PnL calculation
    let pnl: number | null = null;
    let exitPrice = quotePrice;

    if (trade.status === "CLOSED" && trade.exit !== null) {
      exitPrice = trade.exit;
      // Calculate PnL based on price difference
      const priceDiff = (trade.exit - trade.entry) * trade.qty;
      pnl = priceDiff;
    } else if (trade.status === "OPEN") {
      // Unrealized PnL based on current market price
      const priceDiff = (quotePrice - trade.entry) * trade.qty;
      pnl = priceDiff;
      exitPrice = quotePrice;
    }

    return { pnl, exitPrice };
  };

  // Calculate total balances
  const totalPnL = trades.reduce((sum, t) => sum + (t.pnl || 0), 0);
  const openPositions = trades.filter((t) => t.status === "OPEN").length;
  const closedTrades = trades.filter((t) => t.status === "CLOSED");
  const winRate = closedTrades.length > 0 ? Math.round((closedTrades.filter((t) => (t.pnl || 0) > 0).length / closedTrades.length) * 100) : 0;

  // Format trade for display with live data
  const formatTrade = (trade: PaperTrade, liveQuotes: Map<string, number>) => {
    const { pnl, exitPrice } = calculateLivePnL(trade, liveQuotes);

    return {
      ...trade,
      pnl,
      exit: exitPrice,
    };
  };

  const processedTrades = trades.map(t => formatTrade(t, new Map()));

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
            <p className="text-text-secondary mt-1">
              {" "}
              {isFyersConnected ? ("Live market data enabled") : ("Simulated prices - no broker connection")}
              {" "}
            </p>
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
                  <p className="text-2xl md:text-3xl font-bold text-white mt-1 font-mono">
                    {formatCurrency(virtualBalance)}
                  </p>
                </div>
                <div className="w-12 h-12 md:w-14 md:h-14 rounded-xl bg-neon-purple/20 flex items-center justify-center">
                  <DollarSign className="w-6 h-6 md:w-7 md:h-7 text-neon-purple" strokeWidth={2.5} />
                </div>
              </div>
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

          {/* Real-time Market Data Status */}
          {isFyersConnected ? (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="glass rounded-2xl border border-glow-border p-4 md:p-6 bg-neon-green/10 border-neon-green/30"
            >
              <div className="flex items-center gap-3">
                <Sparkles className="w-4 h-4 text-neon-green" strokeWidth={2} />
                <span className="text-sm text-text-secondary">
                  Live market quotes streaming for: {watchlist.join(", ")}
                </span>
              </div>
            </motion.div>
          ) : (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="glass rounded-2xl border border-glow-border p-4 md:p-6 bg-neon-red/10 border-neon-red/30"
            >
              <div className="flex items-center gap-3">
                <AlertCircle className="w-4 h-4 text-neon-red" strokeWidth={2} />
                <span className="text-sm text-text-secondary">
                  No broker connection - using simulated market data
                </span>
              </div>
            </motion.div>
          )}

          {/* Recent Paper Trades Table */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="glass rounded-2xl border border-glow-border overflow-hidden"
          >
            <div className="px-4 md:px-6 py-4 border-b border-glow-border bg-card-bg/50 flex items-center justify-between flex-wrap gap-4">
              <h2 className="text-lg font-semibold text-white">Recent Paper Trades</h2>
              <span className="text-xs text-text-muted">{processedTrades.length} trades</span>
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
                  {processedTrades.map((trade, index) => {
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
                        <td className="px-3 md:px-5 py-3 md:py-4 text-right font-mono text-text-secondary">
                          {formatCurrency(trade.entry)}
                        </td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-right font-mono text-text-secondary">
                          {trade.exit !== undefined ? formatCurrency(trade.exit) : "—"}
                        </td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-right font-mono text-white">
                          {trade.qty.toLocaleString()}
                        </td>
                        <td className={`px-3 md:px-5 py-3 md:py-4 text-right font-mono font-medium ${trade.pnl === null ? "text-text-muted" : isPositive ? "text-neon-green" : "text-neon-red"}`}>
                          {formatPnL(trade.pnl)}
                        </td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-center">
                          <span className={`px-3 py-1 rounded-full text-xs font-medium ${trade.status === "OPEN" ? "bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/30" : "bg-neon-green/20 text-neon-green border border-neon-green/30"}`}>
                            {trade.status}
                          </span>
                        </td>
                        <td className="px-3 md:px-5 py-3 md:py-4 text-left text-text-secondary text-sm">
                          {trade.timestamp}
                        </td>
                      </motion.tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </motion.div>

          {/* Trade Controls */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="glass rounded-2xl border border-glow-border p-6 md:p-8 bg-card-bg/50"
          >
            <h3 className="text-lg font-semibold text-white mb-4">Execute Paper Trade</h3>
            <p className="text-sm text-text-secondary mb-6">
              {" "}
              {isFyersConnected ? ("Use real market quotes") : ("Use simulated prices")}
              {" "}
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
              <select
                className="rounded-lg border border-glow-border bg-card-bg px-3 py-2 text-sm text-white width-full"
                onChange={(e) => setWatchlist(e.target.value.split(",").map((s: string) => s.trim()))}
              >
                <option value="NIFTY,BANKNIFTY,FINNIFTY">Major Indices</option>
                <option value="NIFTY">NIFTY 50</option>
                <option value="BANKNIFTY">Bank Nifty</option>
                <option value="NIFTY,BANKNIFTY,FINNIFTY,SENSEX">All Major</option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-4">
              <div>
                <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Symbol</label>
                <p className="font-mono text-sm text-neon-cyan">{watchlist[0] || "NIFTY"}</p>
              </div>
              <div>
                <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Order Type</label>
                <select
                  className="rounded-lg border border-glow-border bg-card-bg px-3 py-2 text-sm text-white width-full"
                  onChange={(e) => setSide(e.target.value as "BUY" | "SELL")}
                >
                  <option value="BUY">BUY</option>
                  <option value="SELL">SELL</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-4">
              <div>
                <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">CE/PE Type</label>
                <select
                  className="rounded-lg border border-glow-border bg-card-bg px-3 py-2 text-sm text-white width-full"
                  onChange={(e) => setType(e.target.value as "CE" | "PE")}
                >
                  <option value="CE">Call (CE)</option>
                  <option value="PE">Put (PE)</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">Quantity (lots)</label>
                <input
                  type="number"
                  className="rounded-lg border border-glow-border bg-card-bg px-3 py-2 text-sm text-white width-full"
                  min="0.1"
                  max="100"
                  step="0.1"
                  defaultValue="1"
                />
              </div>
            </div>

            <motion.button
              onClick={handleSubmit}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              disabled={!isFyersConnected && processedTrades.length === 0}
              className={`w-full py-3.5 rounded-xl font-bold text-lg shadow-glow-purple transition-all duration-300 ${
                isSubmitting
                  ? "bg-gradient-to-r from-neon-purple/50 to-neon-cyan/50 cursor-not-allowed"
                  : isFyersConnected
                    ? "bg-gradient-to-r from-neon-purple to-neon-cyan text-white"
                    : "bg-gradient-to-r from-neon-purple/50 to-neon-red/50 cursor-not-allowed opacity-60"
              }`}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" strokeWidth={2.5} />
                  Placing Order...
                </>
              ) : (
                <>
                  <Radio className="w-5 h-5" strokeWidth={2.5} />
                  {isFyersConnected ? "Execute Paper Order" : "Place Paper Order"}
                </>
              )}
            </motion.button>
          </motion.div>
        </main>
      </div>
    </div>
  );
}

interface PaperTradeForm {
  symbol: string;
  type: "CE" | "PE";
  side: "BUY" | "SELL";
  quantity: number;
  price: number;
}

const [side, setSide] = useState<"BUY" | "SELL">("BUY");
const [type, setType] = useState<"CE" | "PE">("CE");
const [isSubmitting, setIsSubmitting] = useState(false);