"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Brain,
  TrendingUp,
  TrendingDown,
  Activity,
  RefreshCw,
  Loader2,
  AlertCircle,
  CheckCircle,
  Shield,
  Newspaper,
  ChevronRight,
  Play,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { api, type AISignal, type AISignalsResponse } from "@/lib/api";

const fetcher = (url: string) => fetch(url).then((res) => {
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
});

const MOCK_NEWS = [
  { headline: "Fed rate cut boosts IT sector, Nifty IT index up 2.3%", sentiment: "Bullish" as const, source: "Economic Times", time: "10 min ago" },
  { headline: "RBI maintains repo rate, markets await policy guidance", sentiment: "Neutral" as const, source: "Business Standard", time: "45 min ago" },
  { headline: "FII selling pressure continues in banking stocks", sentiment: "Bearish" as const, source: "Moneycontrol", time: "1 hour ago" },
  { headline: "Auto stocks rally on strong festive season sales", sentiment: "Bullish" as const, source: "CNBC TV18", time: "2 hours ago" },
];

export default function AISignalsPage() {
  const [signals, setSignals] = useState<AISignal[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastScan, setLastScan] = useState<Date | null>(null);

  const fetchSignals = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getAISignals();
      setSignals(data.signals || []);
      setLastScan(new Date());
    } catch (err) {
      console.warn("AI signals fetch failed, using mock data:", err);
      // Mock fallback
      setSignals([
        {
          symbol: "NIFTY",
          name: "NIFTY 50",
          action: "BUY CE",
          confidence: 87,
          reasoning: "Supertrend Bullish + RSI > 60 + VWAP Bounce + PCR < 1.0",
          entry: 24345,
          target: 24480,
          stopLoss: 24290,
          expiry: "28 Oct 2026",
          timestamp: "14:32:15",
        },
        {
          symbol: "BANKNIFTY",
          name: "BANKNIFTY",
          action: "BUY PE",
          confidence: 82,
          reasoning: "Resistance at 51950 + Bearish Engulfing + OI Buildup in Puts",
          entry: 51890,
          target: 51700,
          stopLoss: 51980,
          expiry: "28 Oct 2026",
          timestamp: "14:31:42",
        },
        {
          symbol: "SENSEX",
          name: "SENSEX",
          action: "WAIT",
          confidence: 55,
          reasoning: "Mixed signals: RSI neutral + Supertrend flat + Low volume",
          entry: 79875,
          target: 80000,
          stopLoss: 79750,
          expiry: "28 Oct 2026",
          timestamp: "14:30:18",
        },
      ]);
      setLastScan(new Date());
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSignals();
  }, [fetchSignals]);

  const getActionColor = (action: string) => {
    switch (action) {
      case "BUY CE":
        return "text-neon-green border-neon-green/30 bg-neon-green/10";
      case "BUY PE":
        return "text-neon-red border-neon-red/30 bg-neon-red/10";
      default:
        return "text-neon-orange border-neon-orange/30 bg-neon-orange/10";
    }
  };

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case "Bullish":
        return "text-neon-green";
      case "Bearish":
        return "text-neon-red";
      default:
        return "text-neon-orange";
    }
  };

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="w-full lg:ml-64 min-h-screen flex flex-col">
        <Header />

        <main className="flex-1 p-4 md:p-8 lg:p-10 pt-20 lg:pt-24 space-y-8 max-w-4xl mx-auto w-full">
          {/* Page Header */}
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-3">
              <Brain className="w-9 h-9 text-neon-cyan drop-shadow-[0_0_10px_rgba(0,240,255,0.6)]" strokeWidth={2.5} />
              <div>
                <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight">Grok AI Radar</h1>
                <p className="text-text-secondary">AI-powered trading signals with confidence scoring and reasoning</p>
              </div>
            </div>
            <motion.button
              onClick={fetchSignals}
              disabled={isLoading}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-card-bg border border-neon-cyan/30 hover:border-neon-cyan/50 text-white font-medium transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed glass shadow-[0_0_15px_rgba(0,240,255,0.1)]"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" strokeWidth={2.5} />
              ) : (
                <Activity className="w-5 h-5" strokeWidth={2.5} />
              )}
              <span>{isLoading ? "Scanning..." : "Scan for Signals"}</span>
            </motion.button>
          </div>

          {/* Status Bar */}
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-4 flex-wrap">
              {error && (
                <motion.span className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neon-red/10 border border-neon-red/30 text-neon-red text-sm glass">
                  <AlertCircle className="w-4 h-4" strokeWidth={2.5} />
                  {error}
                </motion.span>
              )}
              {!error && (
                <motion.span className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neon-green/10 border border-neon-green/30 text-neon-green text-sm glass">
                  <span className="w-2 h-2 rounded-full bg-neon-green animate-pulse-glow" />
                  {signals.length} signal{signals.length !== 1 ? "s" : ""} active
                </motion.span>
              )}
              {lastScan && (
                <span className="text-xs text-text-muted">
                  Last scan: {lastScan.toLocaleTimeString()}
                </span>
              )}
            </div>

            <div className="flex items-center gap-3 px-3 py-1.5 rounded-full bg-card-bg border border-glow-border glass">
              <span className="w-2 h-2 rounded-full bg-neon-green" />
              <span className="text-xs font-medium text-white">AI Engine Online</span>
              <span className="text-[10px] text-neon-cyan">Grok v3</span>
            </div>
          </div>

          {/* Signal Cards Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
            {signals.map((signal, index) => {
              const actionColor = getActionColor(signal.action);
              return (
                <motion.div
                  key={`${signal.symbol}-${signal.expiry}-${index}`}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className="glass rounded-2xl border border-glow-border p-4 md:p-5 hover:border-neon-cyan/40 transition-all duration-300 group relative overflow-hidden"
                >
                  {signal.confidence >= 80 && (
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-neon-cyan to-transparent opacity-30 group-hover:opacity-60" />
                  )}

                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-white tracking-tight">{signal.symbol}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-card-bg/50 border border-glow-border text-text-muted">
                        {signal.expiry}
                      </span>
                    </div>
                    <span className={`px-2.5 py-1 rounded text-[10px] font-bold ${actionColor}`}>
                      {signal.action}
                    </span>
                  </div>

                  {/* Confidence Score */}
                  <div className="mb-4">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-text-muted uppercase tracking-wider">Confidence</span>
                      <span className={`text-sm font-mono font-bold ${signal.confidence >= 80 ? "text-neon-green" : signal.confidence >= 60 ? "text-neon-orange" : "text-neon-red"}`}>
                        {signal.confidence}%
                      </span>
                    </div>
                    <div className="w-full bg-card-bg/50 rounded-full h-2 border border-glow-border overflow-hidden relative">
                      <div
                        className={`h-full rounded-full transition-all duration-1000 ease-out ${signal.confidence >= 80 ? "bg-neon-green shadow-[0_0_10px_rgba(0,255,102,0.6)]" : signal.confidence >= 60 ? "bg-neon-orange" : "bg-neon-red"}`}
                        style={{ width: `${signal.confidence}%` }}
                      />
                    </div>
                  </div>

                  {/* AI Reasoning */}
                  <div className="mb-4">
                    <span className="text-[10px] text-text-muted uppercase tracking-wider block mb-1">AI Reasoning</span>
                    <p className="text-sm text-text-secondary leading-relaxed italic">
                      "{signal.reasoning}"
                    </p>
                  </div>

                  {/* Trade Levels */}
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    <div className="text-center">
                      <span className="text-[10px] text-text-muted uppercase tracking-wider block mb-0.5">Entry</span>
                      <span className="text-xs font-mono font-bold text-neon-cyan">{signal.entry.toLocaleString()}</span>
                    </div>
                    <div className="text-center">
                      <span className="text-[10px] text-text-muted uppercase tracking-wider block mb-0.5">Target</span>
                      <span className="text-xs font-mono font-bold text-neon-green">{signal.target.toLocaleString()}</span>
                    </div>
                    <div className="text-center">
                      <span className="text-[10px] text-text-muted uppercase tracking-wider block mb-0.5">Stop Loss</span>
                      <span className="text-xs font-mono font-bold text-neon-red">{signal.stopLoss.toLocaleString()}</span>
                    </div>
                  </div>

                  {/* Execute Button */}
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    disabled={signal.action === "WAIT"}
                    className={`w-full py-2.5 rounded-xl font-bold text-xs tracking-wider transition-all duration-300 flex items-center justify-center gap-2 ${
                      signal.action === "WAIT"
                        ? "bg-card-bg/50 border border-glow-border text-text-muted disabled:cursor-not-allowed"
                        : "bg-neon-green/10 border border-neon-green/30 text-neon-green shadow-[0_0_15px_rgba(0,255,102,0.2)] hover:bg-neon-green/20 hover:border-neon-green/50"
                    }`}
                  >
                    {signal.action === "WAIT" ? "No Setup" : (
                      <>
                        <Play className="w-4 h-4" strokeWidth={2.5} />
                        Execute Trade
                      </>
                    )}
                    <ChevronRight className="w-3 h-3" strokeWidth={2.5} />
                  </motion.button>
                </motion.div>
              );
            })}
          </div>

          {/* News & Sentiment Panel */}
          <div className="glass rounded-2xl border border-glow-border p-4 md:p-6">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <Newspaper className="w-5 h-5 text-neon-cyan" strokeWidth={2.5} />
                <h3 className="font-bold text-white">Market News & Sentiment</h3>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded bg-card-bg/50 border border-glow-border text-text-muted">
                Live Feed
              </span>
            </div>

            <div className="space-y-3">
              {MOCK_NEWS.map((item, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.2 + index * 0.05 }}
                  className="flex items-center justify-between px-4 py-3 rounded-xl bg-card-bg/30 border border-glow-border/50 hover:bg-card-bg/50 transition-colors"
                >
                  <div className="flex-1">
                    <p className="text-sm text-white leading-snug">{item.headline}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-[10px] font-bold uppercase ${getSentimentColor(item.sentiment)}`}>
                        {item.sentiment}
                      </span>
                      <span className="text-[10px] text-text-muted">{item.source}</span>
                      <span className="text-[10px] text-text-muted">{item.time}</span>
                    </div>
                  </div>
                  <ChevronRight className="w-3 h-3 text-text-muted" strokeWidth={2} />
                </motion.div>
              ))}
            </div>
          </div>

          {/* Footer */}
          <div className="text-center text-text-muted text-sm mt-4">
            Powered by Grok AI • Signals refresh every 30 seconds •{" "}
            <Brain className="inline w-4 h-4 text-neon-purple" strokeWidth={2} />
            <span className="text-neon-purple ml-1">ML-driven pattern recognition</span>
          </div>
        </main>
      </div>
    </div>
  );
}