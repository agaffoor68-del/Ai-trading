"use client";

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  RotateCcw,
  Play,
  Loader2,
  TrendingUp,
  TrendingDown,
  BarChart2,
  Calendar,
  ChevronDown,
  AlertCircle,
  CheckCircle,
  FileText,
  Download,
  Settings,
  Zap,
  TrendingUp as TrendingUpIcon,
  ArrowRight,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";

interface BacktestResult {
  totalTrades: number;
  winRate: number;
  totalPnL: number;
  maxDrawdown: number;
  profitFactor: number;
  sharpeRatio: number;
  avgWin: number;
  avgLoss: number;
  bestTrade: number;
  worstTrade: number;
  equityCurve: { date: string; equity: number }[];
  trades: { date: string; symbol: string; side: string; entry: number; exit: number; pnl: number; pnlPercent: number }[];
}

const STRATEGIES = [
  { id: "1", name: "NIFTY Momentum Breakout", timeframe: "15m" },
  { id: "2", name: "BANKNIFTY Mean Reversion", timeframe: "5m" },
  { id: "3", name: "SENSEX Trend Following", timeframe: "1h" },
  { id: "4", name: "NIFTY Intraday Scalper", timeframe: "3m" },
];

const SYMBOLS = ["NIFTY 50", "BANKNIFTY", "SENSEX", "FINNIFTY", "MIDCPNIFTY"];

const MOCK_RESULT: BacktestResult = {
  totalTrades: 147,
  winRate: 64.6,
  totalPnL: 284750,
  maxDrawdown: 12.4,
  profitFactor: 1.87,
  sharpeRatio: 1.42,
  avgWin: 3240,
  avgLoss: -1890,
  bestTrade: 15670,
  worstTrade: -8920,
  equityCurve: Array.from({ length: 30 }, (_, i) => ({
    date: new Date(Date.now() - (29 - i) * 86400000).toISOString().split("T")[0],
    equity: 1000000 + i * 8000 + Math.sin(i * 0.5) * 15000,
  })),
  trades: [
    { date: "2024-11-10", symbol: "NIFTY", side: "BUY CE", entry: 145.50, exit: 167.80, pnl: 1115, pnlPercent: 15.3 },
    { date: "2024-11-10", symbol: "NIFTY", side: "SELL PE", entry: 210.25, exit: 185.40, pnl: -621, pnlPercent: -11.8 },
    { date: "2024-11-09", symbol: "BANKNIFTY", side: "BUY CE", entry: 180.00, exit: 210.50, pnl: 762, pnlPercent: 16.9 },
    { date: "2024-11-09", symbol: "NIFTY", side: "BUY PE", entry: 120.00, exit: 145.20, pnl: 1260, pnlPercent: 21.0 },
    { date: "2024-11-08", symbol: "SENSEX", side: "SELL CE", entry: 195.50, exit: 165.20, pnl: 603, pnlPercent: 15.4 },
  ],
};

export default function BacktestPage() {
  const [selectedStrategy, setSelectedStrategy] = useState(STRATEGIES[0].id);
  const [selectedSymbol, setSelectedSymbol] = useState("NIFTY 50");
  const [startDate, setStartDate] = useState("2024-10-01");
  const [endDate, setEndDate] = useState("2024-11-11");
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const runBacktest = async () => {
    if (!selectedStrategy) {
      setError("Please select a strategy");
      return;
    }

    setIsRunning(true);
    setError(null);
    setResult(null);
    setProgress(0);

    // Simulate backtest progress
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 90) {
          clearInterval(interval);
          return 90;
        }
        return prev + Math.random() * 10;
      });
    }, 200);

    try {
      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 3000));
      clearInterval(interval);
      setProgress(100);
      
      // Mock result
      setResult(MOCK_RESULT);
      
      setTimeout(() => setProgress(0), 500);
    } catch {
      setError("Backtest failed. Please try again.");
    } finally {
      setIsRunning(false);
    }
  };

  const formatCurrency = (val: number) => `₹${val.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
  const formatPnL = (val: number) => `${val >= 0 ? "+" : ""}${formatCurrency(val)}`;

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="ml-64 min-h-screen flex flex-col">
        <Header />

        <main className="flex-1 p-6 md:p-8 lg:p-10 pt-20 lg:pt-24 space-y-8 max-w-7xl mx-auto w-full">
          {/* Page Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <RotateCcw className="w-8 h-8 text-neon-orange drop-shadow-[0_0_10px_rgba(249,115,22,0.6)]" strokeWidth={2.5} />
              <div>
                <h1 className="text-3xl font-bold text-white tracking-tight">Backtest Engine</h1>
                <p className="text-text-secondary">Validate strategies with historical tick-level data</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <motion.button
                disabled={isRunning}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-card-bg border border-glow-border hover:border-neon-cyan/50 text-white font-medium transition-all disabled:opacity-50 glass"
              >
                <Download className="w-4 h-4" strokeWidth={2.5} />
                Export Report
              </motion.button>
              <motion.button
                disabled={isRunning}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-card-bg border border-glow-border hover:border-neon-cyan/50 text-white font-medium transition-all disabled:opacity-50 glass"
              >
                <Settings className="w-4 h-4" strokeWidth={2.5} />
                Advanced
              </motion.button>
            </div>
          </motion.div>

          {/* Backtest Configuration */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass rounded-2xl border border-glow-border p-6"
          >
            <h2 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
              <Settings className="w-5 h-5 text-neon-cyan" strokeWidth={2.5} />
              Backtest Configuration
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
              <div className="md:col-span-2">
                <label className="text-xs text-text-muted uppercase tracking-wider block mb-2">Strategy</label>
                <select
                  value={selectedStrategy}
                  onChange={(e) => setSelectedStrategy(e.target.value)}
                  disabled={isRunning}
                  className="w-full pl-4 pr-10 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base cursor-pointer appearance-none disabled:opacity-50"
                >
                  {STRATEGIES.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.timeframe})
                    </option>
                  ))}
                </select>
                <ChevronDown className="absolute right-4 top-9 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
              </div>

              <div>
                <label className="text-xs text-text-muted uppercase tracking-wider block mb-2">Symbol</label>
                <select
                  value={selectedSymbol}
                  onChange={(e) => setSelectedSymbol(e.target.value)}
                  disabled={isRunning}
                  className="w-full pl-4 pr-10 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base cursor-pointer appearance-none disabled:opacity-50"
                >
                  {SYMBOLS.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <ChevronDown className="absolute right-4 top-9 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
              </div>

              <div>
                <label className="text-xs text-text-muted uppercase tracking-wider block mb-2">Start Date</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  disabled={isRunning}
                  className="w-full pl-4 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base disabled:opacity-50"
                />
              </div>

              <div>
                <label className="text-xs text-text-muted uppercase tracking-wider block mb-2">End Date</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  disabled={isRunning}
                  className="w-full pl-4 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base disabled:opacity-50"
                />
              </div>
            </div>

            {/* Run Button */}
            <div className="mt-6 flex items-center justify-between">
              <motion.button
                onClick={runBacktest}
                disabled={isRunning}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex items-center gap-3 px-8 py-4 rounded-xl font-bold text-lg transition-all duration-300 ${
                  isRunning
                    ? "bg-card-bg/50 border border-glow-border text-text-muted cursor-not-allowed opacity-60"
                    : "bg-gradient-to-r from-neon-orange to-neon-red text-white shadow-glow-orange hover:shadow-glow-orange/50"
                }"
              >
                {isRunning ? (
                  <>
                    <Loader2 className="w-6 h-6 animate-spin" strokeWidth={2.5} />
                    Running... {Math.round(progress)}%
                  </>
                ) : (
                  <>
                    <Play className="w-6 h-6" strokeWidth={2.5} />
                    Run Backtest
                  </>
                )}
              </motion.button>

              {error && (
                <motion.div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-neon-red/10 border border-neon-red/30 text-neon-red text-sm">
                  <AlertCircle className="w-4 h-4" strokeWidth={2.5} />
                  {error}
                </motion.div>
              )}
            </div>

            {/* Progress Bar */}
            {isRunning && (
              <div className="mt-4 w-full bg-card-bg/50 rounded-full h-2 border border-glow-border overflow-hidden">
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-neon-orange to-neon-red"
                  style={{ width: `${progress}%` }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.3 }}
                />
              </div>
            )}
          </motion.div>

          {/* Results Panel */}
          {result && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="space-y-6"
            >
              {/* Key Metrics */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
                <MetricCard label="Total Trades" value={result.totalTrades} icon={FileText} color="text-neon-cyan" />
                <MetricCard label="Win Rate" value={`${result.winRate}%`} icon={TrendingUpIcon} color={result.winRate >= 55 ? "text-neon-green" : "text-neon-red"} />
                <MetricCard label="Total PnL" value={formatPnL(result.totalPnL)} icon={Zap} color={result.totalPnL >= 0 ? "text-neon-green" : "text-neon-red"} fontBold />
                <MetricCard label="Max Drawdown" value={`${result.maxDrawdown}%`} icon={TrendingDown} color="text-neon-red" />
                <MetricCard label="Profit Factor" value={result.profitFactor.toFixed(2)} icon={BarChart2} color={result.profitFactor > 1 ? "text-neon-green" : "text-neon-red"} />
              </div>

              {/* Additional Metrics */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <MetricCard label="Sharpe Ratio" value={result.sharpeRatio.toFixed(2)} icon={BarChart2} color="text-neon-purple" />
                <MetricCard label="Avg Win" value={formatCurrency(result.avgWin)} icon={TrendingUpIcon} color="text-neon-green" />
                <MetricCard label="Avg Loss" value={formatCurrency(result.avgLoss)} icon={TrendingDown} color="text-neon-red" />
                <MetricCard label="Best / Worst" value={`${formatCurrency(result.bestTrade)} / ${formatCurrency(result.worstTrade)}`} icon={Zap} color="text-text-secondary" />
              </div>

              {/* Equity Curve & Trade List */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Equity Curve Placeholder */}
                <motion.div className="glass rounded-2xl border border-glow-border p-6 h-96">
                  <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
                    <BarChart2 className="w-5 h-5 text-neon-cyan" strokeWidth={2.5} />
                    Equity Curve
                  </h3>
                  <div className="h-full flex items-end justify-around px-2">
                    {result.equityCurve.map((point, i) => (
                      <motion.div
                        key={i}
                        initial={{ height: 0 }}
                        animate={{ height: `${Math.max(10, ((point.equity - 950000) / 150000) * 100)}%` }}
                        transition={{ delay: i * 0.02, duration: 0.5 }}
                        className="flex-1 max-w-6 mx-1 bg-gradient-to-t from-neon-cyan to-neon-purple rounded-t transition-all duration-300"
                        style={{ minHeight: "10px" }}
                      />
                    ))}
                  </div>
                  <div className="mt-4 flex justify-between text-xs text-text-muted">
                    <span>Start: {result.equityCurve[0]?.date}</span>
                    <span>End: {result.equityCurve[result.equityCurve.length - 1]?.date}</span>
                  </div>
                </motion.div>

                {/* Recent Trades */}
                <motion.div className="glass rounded-2xl border border-glow-border p-6 h-96 overflow-y-auto">
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <FileText className="w-5 h-5 text-neon-cyan" strokeWidth={2.5} />
                    Recent Trades
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-sm" role="grid">
                      <thead>
                        <tr className="border-b border-glow-border text-text-muted text-xs font-medium uppercase tracking-wider">
                          <th className="px-3 py-3 text-left">Date</th>
                          <th className="px-3 py-3 text-center">Symbol</th>
                          <th className="px-3 py-3 text-center">Side</th>
                          <th className="px-3 py-3 text-right">Entry</th>
                          <th className="px-3 py-3 text-right">Exit</th>
                          <th className="px-3 py-3 text-right">PnL</th>
                          <th className="px-3 py-3 text-right">PnL %</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.trades.map((trade, index) => {
                          const isPositive = trade.pnl >= 0;
                          return (
                            <motion.tr
                              key={index}
                              initial={{ opacity: 0, y: 10 }}
                              animate={{ opacity: 1, y: 0 }}
                              transition={{ delay: index * 0.03 }}
                              className="border-b border-glow-border/50 hover:bg-card-bg/30"
                            >
                              <td className="px-3 py-3 text-left font-mono text-text-secondary">{trade.date}</td>
                              <td className="px-3 py-3 text-center font-medium text-white">{trade.symbol}</td>
                              <td className="px-3 py-3 text-center">
                                <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${trade.side.includes("BUY") ? "bg-neon-green/20 text-neon-green" : "bg-neon-red/20 text-neon-red"}`}>
                                  {trade.side}
                                </span>
                              </td>
                              <td className="px-3 py-3 text-right font-mono text-text-secondary">₹{trade.entry.toFixed(2)}</td>
                              <td className="px-3 py-3 text-right font-mono text-text-secondary">₹{trade.exit.toFixed(2)}</td>
                              <td className={`px-3 py-3 text-right font-mono font-medium ${isPositive ? "text-neon-green" : "text-neon-red"}`}>
                                {formatPnL(trade.pnl)}
                              </td>
                              <td className={`px-3 py-3 text-right font-mono font-medium ${isPositive ? "text-neon-green" : "text-neon-red"}`}>
                                {trade.pnlPercent >= 0 ? "+" : ""}{trade.pnlPercent.toFixed(1)}%
                              </td>
                            </motion.tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </motion.div>
              </div>
            </motion.div>
          )}

          {/* Empty State */}
          {!result && !isRunning && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="glass rounded-2xl border border-glow-border p-12 text-center"
            >
              <RotateCcw className="w-20 h-20 text-text-muted mx-auto mb-6" strokeWidth={1.5} />
              <h2 className="text-xl font-semibold text-white mb-2">No Backtest Results Yet</h2>
              <p className="text-text-secondary mb-8 max-w-md mx-auto">
                Configure your backtest parameters and click "Run Backtest" to see historical performance metrics.
              </p>
              <div className="flex items-center justify-center gap-4 text-sm text-text-muted">
                <div className="flex items-center gap-1"><Zap className="w-4 h-4" strokeWidth={2} /> Tick-level data</div>
                <div className="flex items-center gap-1"><BarChart2 className="w-4 h-4" strokeWidth={2} /> Walk-forward analysis</div>
                <div className="flex items-center gap-1"><FileText className="w-4 h-4" strokeWidth={2} /> Detailed reports</div>
              </div>
            </motion.div>
          )}
        </main>
      </div>
    </div>
  );
}

function MetricCard({ label, value, icon: Icon, color, fontBold }: { label: string; value: string | number; icon: React.ComponentType<{ className?: string; strokeWidth?: number }>; color: string; fontBold?: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass rounded-2xl border border-glow-border p-5"
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-text-muted uppercase tracking-wider">{label}</p>
          <p className={`text-2xl font-bold mt-1 ${color} ${fontBold ? "font-black" : ""}`}>{value}</p>
        </div>
        <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ backgroundColor: "rgba(255,255,255,0.03)" }}>
          <Icon className="w-6 h-6" strokeWidth={2.5} style={{ color: "currentColor" }} />
        </div>
      </div>
    </motion.div>
  );
}