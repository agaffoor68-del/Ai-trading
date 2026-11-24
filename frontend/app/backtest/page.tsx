"use client";

import { useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { Play, Activity, Target, TrendingUp, TrendingDown, BarChart3, Loader2 } from "lucide-react";

interface Trade {
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  side: string;
  pnl: number;
  pnl_pct: number;
  exit_reason: string;
}

interface BacktestResult {
  symbol: string;
  yahoo_symbol: string;
  strategy: string;
  interval: string;
  range: string;
  initial_capital: number;
  final_capital: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  max_drawdown: number;
  data_source: string;
  candles_used: number;
  trades: Trade[];
}

export default function BacktestPage() {
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [symbol, setSymbol] = useState("RELIANCE");
  const [strategy, setStrategy] = useState("Supertrend + RSI");
  const [interval, setIntervalValue] = useState("15m");
  const [range, setRange] = useState("60d");
  const [initialCapital, setInitialCapital] = useState(100000);
  const [quantity, setQuantity] = useState(1);
  const [slPct, setSlPct] = useState(0.5);
  const [targetPct, setTargetPct] = useState(1.0);

  const runBacktest = async () => {
    setIsRunning(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/backtest/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol,
          strategy,
          interval,
          range,
          initial_capital: initialCapital,
          quantity,
          sl_pct: slPct,
          target_pct: targetPct,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Backtest failed");
      }

      setResults(data);
    } catch (err: any) {
      setError(err.message || "Unknown error");
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="w-full lg:ml-64 min-h-screen flex flex-col">
        <Header />
        <main className="flex-1 p-4 md:p-8 lg:p-10 pt-20 lg:pt-24 max-w-5xl mx-auto w-full space-y-6">

          <div className="flex items-center gap-3 mb-8">
            <Activity className="w-8 h-8 text-neon-cyan" />
            <h1 className="text-2xl md:text-3xl font-bold">Backtest Lab</h1>
            <span className="badge-info text-xs">Real Yahoo Data</span>
          </div>

          {/* Form */}
          <div className="glass rounded-2xl border border-glow-border p-4 md:p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
              <div>
                <label className="block text-sm text-text-secondary mb-1">Symbol</label>
                <input
                  type="text"
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  placeholder="e.g. RELIANCE, NIFTY 50"
                  className="w-full bg-true-black border border-glow-border rounded-lg p-3 text-white outline-none"
                />
              </div>
              <div>
                <label className="block text-sm text-text-secondary mb-1">Strategy</label>
                <select
                  value={strategy}
                  onChange={(e) => setStrategy(e.target.value)}
                  className="w-full bg-true-black border border-glow-border rounded-lg p-3 text-white outline-none"
                >
                  <option>Supertrend + RSI</option>
                  <option>VWAP Bounce</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-text-secondary mb-1">Interval</label>
                <select
                  value={interval}
                  onChange={(e) => setIntervalValue(e.target.value)}
                  className="w-full bg-true-black border border-glow-border rounded-lg p-3 text-white outline-none"
                >
                  <option value="1m">1 minute</option>
                  <option value="2m">2 minutes</option>
                  <option value="5m">5 minutes</option>
                  <option value="15m">15 minutes</option>
                  <option value="30m">30 minutes</option>
                  <option value="1h">1 hour</option>
                  <option value="1d">1 day</option>
                  <option value="1wk">1 week</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-text-secondary mb-1">Range</label>
                <select
                  value={range}
                  onChange={(e) => setRange(e.target.value)}
                  className="w-full bg-true-black border border-glow-border rounded-lg p-3 text-white outline-none"
                >
                  <option value="5d">5 days</option>
                  <option value="1mo">1 month</option>
                  <option value="3mo">3 months</option>
                  <option value="6mo">6 months</option>
                  <option value="1y">1 year</option>
                  <option value="2y">2 years</option>
                  <option value="5y">5 years</option>
                  <option value="max">Max</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-text-secondary mb-1">Initial Capital</label>
                <input
                  type="number"
                  value={initialCapital}
                  onChange={(e) => setInitialCapital(Number(e.target.value))}
                  className="w-full bg-true-black border border-glow-border rounded-lg p-3 text-white outline-none"
                />
              </div>
              <div>
                <label className="block text-sm text-text-secondary mb-1">Quantity</label>
                <input
                  type="number"
                  value={quantity}
                  onChange={(e) => setQuantity(Number(e.target.value))}
                  className="w-full bg-true-black border border-glow-border rounded-lg p-3 text-white outline-none"
                />
              </div>
              <div>
                <label className="block text-sm text-text-secondary mb-1">Stop Loss %</label>
                <input
                  type="number"
                  value={slPct}
                  onChange={(e) => setSlPct(Number(e.target.value))}
                  className="w-full bg-true-black border border-glow-border rounded-lg p-3 text-white outline-none"
                />
              </div>
              <div>
                <label className="block text-sm text-text-secondary mb-1">Target %</label>
                <input
                  type="number"
                  value={targetPct}
                  onChange={(e) => setTargetPct(Number(e.target.value))}
                  className="w-full bg-true-black border border-glow-border rounded-lg p-3 text-white outline-none"
                />
              </div>
            </div>

            <button
              onClick={runBacktest}
              disabled={isRunning}
              className="w-full py-3 rounded-xl bg-neon-cyan text-true-black font-bold flex items-center justify-center gap-2"
            >
              {isRunning ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Running backtest...
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  Run Backtest (Real Yahoo Data)
                </>
              )}
            </button>
          </div>

          {/* Error */}
          {error && (
            <div className="glass p-4 rounded-xl border border-neon-red/50 bg-neon-red/10">
              <p className="text-neon-red font-semibold">Error:</p>
              <p className="text-text-secondary mt-1">{error}</p>
            </div>
          )}

          {/* Results */}
          {results && (
            <>
              {/* Summary cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="glass p-4 rounded-xl border border-glow-border">
                  <Target className="w-5 h-5 text-neon-cyan mb-2" />
                  <p className="text-text-secondary text-sm">Total Trades</p>
                  <p className="text-2xl font-bold">{results.total_trades}</p>
                </div>
                <div className="glass p-4 rounded-xl border border-glow-border">
                  <TrendingUp className="w-5 h-5 text-neon-green mb-2" />
                  <p className="text-text-secondary text-sm">Win Rate</p>
                  <p className="text-2xl font-bold text-neon-green">{results.win_rate}%</p>
                </div>
                <div className="glass p-4 rounded-xl border border-glow-border">
                  <TrendingUp className="w-5 h-5 text-neon-green mb-2" />
                  <p className="text-text-secondary text-sm">Total PnL</p>
                  <p className={`text-2xl font-bold ${results.total_pnl >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                    {results.total_pnl >= 0 ? "+" : ""}{results.total_pnl}
                  </p>
                </div>
                <div className="glass p-4 rounded-xl border border-glow-border">
                  <TrendingDown className="w-5 h-5 text-neon-red mb-2" />
                  <p className="text-text-secondary text-sm">Max Drawdown</p>
                  <p className="text-2xl font-bold text-neon-red">{results.max_drawdown}</p>
                </div>
              </div>

              {/* Meta info */}
              <div className="glass p-4 rounded-xl border border-glow-border text-sm text-text-secondary space-y-1">
                <p><span className="text-white">Data Source:</span> {results.data_source}</p>
                <p><span className="text-white">Symbol:</span> {results.symbol} → {results.yahoo_symbol}</p>
                <p><span className="text-white">Candles:</span> {results.candles_used} | <span className="text-white">Interval:</span> {results.interval} | <span className="text-white">Range:</span> {results.range}</p>
                <p><span className="text-white">Wins:</span> {results.winning_trades} | <span className="text-white">Losses:</span> {results.losing_trades} | <span className="text-white">Final Capital:</span> {results.final_capital}</p>
              </div>

              {/* Trades table */}
              {results.trades.length > 0 && (
                <div className="glass rounded-2xl border border-glow-border overflow-hidden">
                  <div className="p-4 border-b border-glow-border">
                    <h3 className="text-lg font-bold flex items-center gap-2">
                      <BarChart3 className="w-5 h-5 text-neon-cyan" />
                      Trade Details (Entry & Exit Times)
                    </h3>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-true-black/50">
                        <tr className="text-text-secondary">
                          <th className="p-3 text-left">#</th>
                          <th className="p-3 text-left">Side</th>
                          <th className="p-3 text-left">Entry Time</th>
                          <th className="p-3 text-left">Exit Time</th>
                          <th className="p-3 text-right">Entry Price</th>
                          <th className="p-3 text-right">Exit Price</th>
                          <th className="p-3 text-right">PnL</th>
                          <th className="p-3 text-left">Exit Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {results.trades.map((trade, idx) => (
                          <tr key={idx} className="border-t border-glow-border/50 hover:bg-glow-border/10">
                            <th className="p-3 text-text-secondary text-center">{idx + 1}</th>
                            <th className="p-3">
                              <span className={`badge ${trade.side === "BUY" ? "badge-success" : "badge-error"}`}>
                                {trade.side}
                              </span>
                            </th>
                            <th className="p-3 whitespace-nowrap">{trade.entry_time}</th>
                            <th className="p-3 whitespace-nowrap">{trade.exit_time}</th>
                            <th className="p-3 text-right">{trade.entry_price}</th>
                            <th className="p-3 text-right">{trade.exit_price}</th>
                            <th className={`p-3 text-right font-semibold ${trade.pnl >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                              {trade.pnl >= 0 ? "+" : ""}{trade.pnl} ({trade.pnl_pct}%)
                            </th>
                            <th className="p-3">{trade.exit_reason}</th>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
