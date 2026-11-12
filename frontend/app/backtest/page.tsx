"use client";

import { useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { Play, Activity, Target, TrendingUp, TrendingDown } from "lucide-react";

export default function BacktestPage() {
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState<any>(null);

  const runBacktest = () => {
    setIsRunning(true);
    setTimeout(() => {
      setResults({ trades: 150, winRate: 65, pnl: 25000, drawdown: -5000 });
      setIsRunning(false);
    }, 1500);
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
          </div>

          {/* Form */}
          <div className="glass rounded-2xl border border-glow-border p-4 md:p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div>
                <label className="block text-sm text-text-secondary mb-1">Strategy</label>
                <select className="w-full bg-true-black border border-glow-border rounded-lg p-3 text-white outline-none">
                  <option>Supertrend + RSI</option>
                  <option>VWAP Bounce</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-text-secondary mb-1">Symbol</label>
                <select className="w-full bg-true-black border border-glow-border rounded-lg p-3 text-white outline-none">
                  <option>NIFTY 50</option>
                  <option>BANKNIFTY</option>
                </select>
              </div>
            </div>
            
            <button 
              onClick={runBacktest} 
              disabled={isRunning}
              className="w-full py-3 rounded-xl bg-neon-cyan text-true-black font-bold flex items-center justify-center gap-2"
            >
              <Play className="w-5 h-5" />
              {isRunning ? "Running..." : "Run Backtest"}
            </button>
          </div>

          {/* Results */}
          {results && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="glass p-4 rounded-xl border border-glow-border">
                <Target className="w-5 h-5 text-neon-cyan mb-2" />
                <p className="text-text-secondary text-sm">Total Trades</p>
                <p className="text-2xl font-bold">{results.trades}</p>
              </div>
              <div className="glass p-4 rounded-xl border border-glow-border">
                <TrendingUp className="w-5 h-5 text-neon-green mb-2" />
                <p className="text-text-secondary text-sm">Win Rate</p>
                <p className="text-2xl font-bold text-neon-green">{results.winRate}%</p>
              </div>
              <div className="glass p-4 rounded-xl border border-glow-border">
                <TrendingUp className="w-5 h-5 text-neon-green mb-2" />
                <p className="text-text-secondary text-sm">Total PnL</p>
                <p className="text-2xl font-bold text-neon-green">₹{results.pnl}</p>
              </div>
              <div className="glass p-4 rounded-xl border border-glow-border">
                <TrendingDown className="w-5 h-5 text-neon-red mb-2" />
                <p className="text-text-secondary text-sm">Max Drawdown</p>
                <p className="text-2xl font-bold text-neon-red">₹{results.drawdown}</p>
              </div>
            </div>
          )}

        </main>
      </div>
    </div>
  );
}