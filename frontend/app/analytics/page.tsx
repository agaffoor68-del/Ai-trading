"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import {
  BarChart2,
  TrendingUp,
  TrendingDown,
  PieChart,
  Target,
  Award,
  Calendar,
  ChevronDown,
  Download,
  RefreshCw,
  DollarSign,
  Activity,
  Zap,
  Shield,
  ArrowUpRight,
  ArrowDownRight,
  LucideIcon,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";

interface DailyPnL {
  date: string;
  pnl: number;
  cumulative: number;
}

interface StrategyPerformance {
  id: string;
  name: string;
  totalPnL: number;
  winRate: number;
  totalTrades: number;
  sharpeRatio: number;
  maxDrawdown: number;
}

const TIME_RANGES = [
  { label: "7D", days: 7 },
  { label: "30D", days: 30 },
  { label: "90D", days: 90 },
  { label: "1Y", days: 365 },
  { label: "ALL", days: 0 },
];

const MOCK_DAILY_PNL: DailyPnL[] = Array.from({ length: 30 }, (_, i) => {
  const date = new Date(Date.now() - (29 - i) * 86400000);
  const daily = (Math.random() - 0.4) * 50000;
  return {
    date: date.toISOString().split("T")[0],
    pnl: Math.round(daily),
    cumulative: 0, // Will calculate below
  };
}).map((d, i, arr) => ({
  ...d,
  cumulative: arr.slice(0, i + 1).reduce((sum, x) => sum + x.pnl, 1000000),
}));

const MOCK_STRATEGIES: StrategyPerformance[] = [
  { id: "1", name: "NIFTY Momentum Breakout", totalPnL: 284750, winRate: 64.6, totalTrades: 147, sharpeRatio: 1.42, maxDrawdown: 12.4 },
  { id: "2", name: "BANKNIFTY Mean Reversion", totalPnL: 156200, winRate: 71.2, totalTrades: 89, sharpeRatio: 1.68, maxDrawdown: 8.9 },
  { id: "3", name: "SENSEX Trend Following", totalPnL: -23400, winRate: 48.5, totalTrades: 67, sharpeRatio: 0.89, maxDrawdown: 18.2 },
  { id: "4", name: "NIFTY Intraday Scalper", totalPnL: 98500, winRate: 58.3, totalTrades: 234, sharpeRatio: 1.15, maxDrawdown: 15.6 },
  { id: "5", name: "FINNIFTY Volatility", totalPnL: 45800, winRate: 52.1, totalTrades: 45, sharpeRatio: 0.95, maxDrawdown: 22.1 },
];

const formatCurrency = (val: number) => `₹${val.toLocaleString(undefined, { minimumFractionDigits: 0 })}`;
const formatPnL = (val: number) => `${val >= 0 ? "+" : ""}${formatCurrency(val)}`;

export default function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState("30D");
  const [selectedStrategy, setSelectedStrategy] = useState<string | null>(null);

  const totalPnL = useMemo(() => MOCK_STRATEGIES.reduce((sum, s) => sum + s.totalPnL, 0), []);
  const totalTrades = useMemo(() => MOCK_STRATEGIES.reduce((sum, s) => sum + s.totalTrades, 0), []);
  const avgWinRate = useMemo(() => MOCK_STRATEGIES.reduce((sum, s) => sum + s.winRate, 0) / MOCK_STRATEGIES.length, []);
  const bestStrategy = useMemo(() => MOCK_STRATEGIES.reduce((best, s) => s.totalPnL > best.totalPnL ? s : best), []);
  const worstStrategy = useMemo(() => MOCK_STRATEGIES.reduce((worst, s) => s.totalPnL < worst.totalPnL ? s : worst), []);

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
              <BarChart2 className="w-8 h-8 text-neon-purple drop-shadow-[0_0_10px_rgba(168,85,247,0.6)]" strokeWidth={2.5} />
              <div>
                <h1 className="text-3xl font-bold text-white tracking-tight">Performance Analytics</h1>
                <p className="text-text-secondary">Deep dive into strategy performance and risk metrics</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-card-bg border border-glow-border hover:border-neon-cyan/50 text-white font-medium transition-all glass"
              >
                <Download className="w-4 h-4" strokeWidth={2.5} />
                Export Report
              </motion.button>
              <div className="relative">
                <select
                  value={timeRange}
                  onChange={(e) => setTimeRange(e.target.value)}
                  className="pl-4 pr-10 py-2.5 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-sm cursor-pointer appearance-none"
                >
                  {TIME_RANGES.map((r) => (
                    <option key={r.label} value={r.label}>{r.label}</option>
                  ))}
                </select>
                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
              </div>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-card-bg border border-glow-border hover:border-neon-cyan/50 text-white font-medium transition-all glass"
              >
                <RefreshCw className="w-4 h-4" strokeWidth={2.5} />
                Refresh
              </motion.button>
            </div>
          </motion.div>

          {/* KPI Cards */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4"
          >
            <KPICard label="Total PnL" value={formatPnL(totalPnL)} icon={DollarSign} color={totalPnL >= 0 ? "text-neon-green" : "text-neon-red"} fontBold />
            <KPICard label="Total Trades" value={totalTrades} icon={Activity} color="text-neon-cyan" />
            <KPICard label="Avg Win Rate" value={`${avgWinRate.toFixed(1)}%`} icon={TrendingUp} color={avgWinRate >= 55 ? "text-neon-green" : "text-neon-red"} />
            <KPICard label="Best Strategy" value={bestStrategy.name} icon={Award} color="text-neon-purple" />
            <KPICard label="Worst Strategy" value={worstStrategy.name} icon={AlertCircle} color="text-neon-red" />
          </motion.div>

          {/* Charts Row */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="grid grid-cols-1 lg:grid-cols-2 gap-6"
          >
            {/* Daily PnL Chart */}
            <motion.div className="glass rounded-2xl border border-glow-border p-6 h-96">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                  <Activity className="w-5 h-5 text-neon-cyan" strokeWidth={2.5} />
                  Daily PnL
                </h3>
                <span className="text-xs text-text-muted">Cumulative Equity</span>
              </div>
              <div className="h-[380px] flex items-end justify-around px-2">
                {MOCK_DAILY_PNL.map((point, i) => {
                  const height = Math.max(4, ((point.pnl + 20000) / 40000) * 100);
                  const isPositive = point.pnl >= 0;
                  return (
                    <motion.div
                      key={i}
                      initial={{ height: 0 }}
                      animate={{ height: `${height}%` }}
                      transition={{ delay: i * 0.02, duration: 0.4 }}
                      className="flex-1 max-w-5 mx-0.5 rounded-t transition-all duration-300"
                      style={{ 
                        minHeight: "4px",
                        backgroundColor: isPositive ? "rgba(0, 255, 102, 0.8)" : "rgba(255, 0, 60, 0.8)",
                        boxShadow: isPositive ? "0 0 8px rgba(0, 255, 102, 0.5)" : "0 0 8px rgba(255, 0, 60, 0.5)"
                      }}
                    />
                  );
                })}
              </div>
              <div className="mt-4 flex justify-between text-xs text-text-muted">
                <span>Start: {MOCK_DAILY_PNL[0]?.date}</span>
                <span>End: {MOCK_DAILY_PNL[MOCK_DAILY_PNL.length - 1]?.date}</span>
              </div>
            </motion.div>

            {/* Win Rate Donut + Strategy Allocation */}
            <motion.div className="glass rounded-2xl border border-glow-border p-6 h-96 overflow-y-auto">
              <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
                <PieChart className="w-5 h-5 text-neon-purple" strokeWidth={2.5} />
                Win Rate Distribution
              </h3>
              
              {/* Donut Chart Placeholder */}
              <div className="flex items-center justify-center mb-8 relative">
                <div className="relative w-48 h-48">
                  <svg viewBox="0 0 100 100" className="w-full h-full transform -rotate-90">
                    <circle cx="50" cy="50" r="40" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="16" />
                    <motion.circle
                      initial={{ strokeDasharray: "0 251" }}
                      animate={{ strokeDasharray: `${(avgWinRate / 100) * 251} ${251 - (avgWinRate / 100) * 251}` }}
                      transition={{ duration: 1.5, delay: 0.3 }}
                      cx="50" cy="50" r="40" fill="none" stroke="url(#winRateGradient)" strokeWidth="16" strokeLinecap="round"
                    />
                    <defs>
                      <linearGradient id="winRateGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="#00FF66" />
                        <stop offset="100%" stopColor="#A855F7" />
                      </linearGradient>
                    </defs>
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center flex-col">
                    <span className="text-4xl font-bold text-white">{avgWinRate.toFixed(1)}%</span>
                    <span className="text-xs text-text-muted">Avg Win Rate</span>
                  </div>
                </div>
              </div>

              {/* Strategy Allocation */}
              <div className="space-y-4">
                <h4 className="text-xs text-text-muted uppercase tracking-wider">Strategy PnL Allocation</h4>
                {MOCK_STRATEGIES.map((strategy, index) => {
                  const pct = Math.abs(strategy.totalPnL) / MOCK_STRATEGIES.reduce((sum, s) => sum + Math.abs(s.totalPnL), 0) * 100;
                  return (
                    <motion.div
                      key={strategy.id}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.2 + index * 0.05 }}
                      className="flex items-center gap-4"
                    >
                      <div className="w-24 flex-shrink-0">
                        <span className="text-sm font-medium text-white truncate block">{strategy.name}</span>
                        <span className="text-xs text-text-muted">{strategy.totalTrades} trades</span>
                      </div>
                      <div className="flex-1 h-3 bg-card-bg/50 rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ delay: 0.3 + index * 0.05, duration: 0.8 }}
                          className="h-full rounded-full bg-gradient-to-r from-neon-cyan to-neon-purple"
                        />
                      </div>
                      <div className="w-20 text-right font-mono text-sm text-white">
                        {formatPnL(strategy.totalPnL)}
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            </motion.div>
          </motion.div>

          {/* Strategy Performance Table */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="glass rounded-2xl border border-glow-border overflow-hidden"
          >
            <div className="px-6 py-4 border-b border-glow-border bg-card-bg/50 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <Target className="w-5 h-5 text-neon-cyan" strokeWidth={2.5} />
                Strategy Performance Breakdown
              </h2>
              <span className="text-xs px-2 py-0.5 rounded bg-neon-purple/20 text-neon-purple font-medium">
                {MOCK_STRATEGIES.length} strategies
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full border-collapse" role="grid">
                <thead>
                  <tr className="border-b border-glow-border bg-card-bg/50 text-text-muted text-xs font-medium uppercase tracking-wider">
                    <th className="px-5 py-4 text-left">Strategy</th>
                    <th className="px-5 py-4 text-center">Total PnL</th>
                    <th className="px-5 py-4 text-center">Win Rate</th>
                    <th className="px-5 py-4 text-center">Total Trades</th>
                    <th className="px-5 py-4 text-center">Sharpe Ratio</th>
                    <th className="px-5 py-4 text-center">Max Drawdown</th>
                    <th className="px-5 py-4 text-center">Avg PnL/Trade</th>
                    <th className="px-5 py-4 text-center">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {MOCK_STRATEGIES.map((strategy, index) => {
                    const isPositive = strategy.totalPnL >= 0;
                    const avgPnL = strategy.totalTrades > 0 ? strategy.totalPnL / strategy.totalTrades : 0;
                    return (
                      <motion.tr
                        key={strategy.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.03 }}
                        className={`border-b border-glow-border/50 hover:bg-card-bg/30 transition-colors ${selectedStrategy === strategy.id ? "bg-neon-purple/5" : ""}`}
                        onClick={() => setSelectedStrategy(selectedStrategy === strategy.id ? null : strategy.id)}
                      >
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-3">
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${isPositive ? "bg-neon-green/20" : "bg-neon-red/20"}`}>
                              <Zap className={`w-4 h-4 ${isPositive ? "text-neon-green" : "text-neon-red"}`} strokeWidth={2.5} />
                            </div>
                            <div>
                              <p className="font-medium text-white">{strategy.name}</p>
                              <p className="text-xs text-text-muted">{strategy.totalTrades} trades • {strategy.winRate}% WR</p>
                            </div>
                          </div>
                        </td>
                        <td className={`px-5 py-4 text-center font-mono font-bold ${isPositive ? "text-neon-green" : "text-neon-red"}`}>
                          {formatPnL(strategy.totalPnL)}
                        </td>
                        <td className={`px-5 py-4 text-center font-mono ${strategy.winRate >= 55 ? "text-neon-green" : strategy.winRate >= 50 ? "text-neon-orange" : "text-neon-red"}`}>
                          {strategy.winRate}%
                        </td>
                        <td className="px-5 py-4 text-center font-mono text-text-secondary">{strategy.totalTrades}</td>
                        <td className={`px-5 py-4 text-center font-mono ${strategy.sharpeRatio >= 1.5 ? "text-neon-green" : strategy.sharpeRatio >= 1 ? "text-neon-orange" : "text-neon-red"}`}>
                          {strategy.sharpeRatio.toFixed(2)}
                        </td>
                        <td className={`px-5 py-4 text-center font-mono ${strategy.maxDrawdown <= 10 ? "text-neon-green" : strategy.maxDrawdown <= 15 ? "text-neon-orange" : "text-neon-red"}`}>
                          {strategy.maxDrawdown}%
                        </td>
                        <td className={`px-5 py-4 text-center font-mono ${avgPnL >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                          {formatCurrency(avgPnL)}
                        </td>
                        <td className="px-5 py-4 text-center">
                          <span className={`px-3 py-1 rounded-full text-xs font-medium ${strategy.totalPnL >= 0 && strategy.winRate >= 55 ? "bg-neon-green/20 text-neon-green border border-neon-green/30" : strategy.totalPnL < 0 ? "bg-neon-red/20 text-neon-red border border-neon-red/30" : "bg-neon-orange/20 text-neon-orange border border-neon-orange/30"}`}>
                            {strategy.totalPnL >= 0 && strategy.winRate >= 55 ? "Profitable" : strategy.totalPnL < 0 ? "Loss" : "Review"}
                          </span>
                        </td>
                      </motion.tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </motion.div>

          {/* Risk Metrics */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="grid grid-cols-1 md:grid-cols-3 gap-6"
          >
            <RiskCard
              title="Risk Metrics"
              items={[
                { label: "Portfolio VaR (95%)", value: "₹45,200", status: "ok" },
                { label: "Max Correlation", value: "0.72 (NIFTY/BANK)", status: "warn" },
                { label: "Concentration Risk", value: "32% in NIFTY", status: "warn" },
                { label: "Liquidity Score", value: "A+ (High)", status: "ok" },
              ]}
            />
            <RiskCard
              title="Execution Quality"
              items={[
                { label: "Avg Slippage", value: "0.8 bps", status: "ok" },
                { label: "Fill Rate", value: "98.7%", status: "ok" },
                { label: "Partial Fills", value: "12%", status: "warn" },
                { label: "Rejection Rate", value: "0.3%", status: "ok" },
              ]}
            />
            <RiskCard
              title="Cost Analysis"
              items={[
                { label: "Total Commissions", value: "₹12,450", status: "info" },
                { label: "STT Paid", value: "₹8,920", status: "info" },
                { label: "Exchange Fees", value: "₹3,180", status: "info" },
                { label: "Cost per Trade", value: "₹28.5", status: "info" },
              ]}
            />
          </motion.div>
        </main>
      </div>
    </div>
  );
}

function KPICard({ label, value, icon: Icon, color, fontBold }: { label: string; value: string | number; icon: LucideIcon; color: string; fontBold?: boolean }) {
  return (
    <div className="glass rounded-2xl border border-glow-border p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-text-muted uppercase tracking-wider">{label}</p>
          <p className={`text-2xl font-bold mt-1 ${color} ${fontBold ? "font-black" : ""}`}>{value}</p>
        </div>
        <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ backgroundColor: "rgba(255,255,255,0.03)" }}>
          <Icon className="w-6 h-6" strokeWidth={2.5} style={{ color: "currentColor" }} />
        </div>
      </div>
    </div>
  );
}

function RiskCard({ title, items }: { title: string; items: { label: string; value: string; status: "ok" | "warn" | "info" }[] }) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case "ok": return "text-neon-green";
      case "warn": return "text-neon-orange";
      case "info": return "text-neon-cyan";
      default: return "text-text-muted";
    }
  };

  return (
    <div className="glass rounded-2xl border border-glow-border p-6">
      <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
        <Shield className="w-4 h-4 text-neon-cyan" strokeWidth={2.5} />
        {title}
      </h3>
      <div className="space-y-3">
        {items.map((item, index) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.05 }}
            className="flex items-center justify-between px-3 py-2 rounded-lg bg-card-bg/30 border border-glow-border/50"
          >
            <span className="text-sm text-text-secondary">{item.label}</span>
            <div className="flex items-center gap-2">
              <span className={`font-mono text-sm ${getStatusColor(item.status)}`}>{item.value}</span>
              <span className={`w-2 h-2 rounded-full ${getStatusColor(item.status).replace("text-", "bg-")}`} />
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}