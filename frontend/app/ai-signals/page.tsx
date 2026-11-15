"use client";

import { useState, useCallback, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Brain,
  Activity,
  RefreshCw,
  Loader2,
  AlertCircle,
  Newspaper,
  ChevronRight,
  Play,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

function getActionColor(action: string): string {
  if (action === "BUY") return "text-neon-green border-neon-green/30 bg-neon-green/10";
  if (action === "SELL") return "text-neon-red border-neon-red/30 bg-neon-red/10";
  return "text-neon-orange border-neon-orange/30 bg-neon-orange/10";
}

function getButtonClass(action: string): string {
  var base = "w-full py-2.5 rounded-xl font-bold text-xs tracking-wider transition-all duration-300 flex items-center justify-center gap-2";
  if (action === "HOLD") {
    return base + " bg-card-bg/50 border border-glow-border text-text-muted disabled:cursor-not-allowed";
  }
  return base + " bg-neon-green/10 border border-neon-green/30 text-neon-green shadow-[0_0_15px_rgba(0,255,102,0.2)] hover:bg-neon-green/20 hover:border-neon-green/50";
}

function getProgressBarClass(confidence: number): string {
  var base = "h-full rounded-full transition-all duration-1000 ease-out";
  if (confidence >= 80) return base + " bg-neon-green shadow-[0_0_10px_rgba(0,255,102,0.6)]";
  if (confidence >= 60) return base + " bg-neon-orange";
  return base + " bg-neon-red";
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 80) return "text-sm font-mono font-bold text-neon-green";
  if (confidence >= 60) return "text-sm font-mono font-bold text-neon-orange";
  return "text-sm font-mono font-bold text-neon-red";
}

function getTrendColor(trend: string): string {
  if (trend === "BULLISH") return "text-neon-green";
  if (trend === "BEARISH") return "text-neon-red";
  return "text-neon-orange";
}

export default function AISignalsPage() {
  var signalsState = useState<any[]>([]);
  var signals = signalsState[0];
  var setSignals = signalsState[1];
  var isLoadingState = useState(true);
  var isLoading = isLoadingState[0];
  var setIsLoading = isLoadingState[1];
  var isManualLoadingState = useState(false);
  var isManualLoading = isManualLoadingState[0];
  var setIsManualLoading = isManualLoadingState[1];
  var errorState = useState<string | null>(null);
  var error = errorState[0];
  var setError = errorState[1];
  var lastScanState = useState<Date | null>(null);
  var lastScan = lastScanState[0];
  var setLastScan = lastScanState[1];

  var fetchSignals = useCallback(function () {
    setIsManualLoading(true);
    setError(null);
    fetch(API_URL + "/api/v1/ai/signals?symbols=NIFTY,BANKNIFTY,FINNIFTY,MIDCPNIFTY")
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        setSignals(data.signals || []);
        setLastScan(new Date());
      })
      .catch(function (err) {
        var errorMessage = err instanceof Error ? err.message : "Failed to fetch AI signals";
        setError(errorMessage);
        console.error("AI signals fetch failed:", err);
      })
      .finally(function () {
        setIsLoading(false);
        setIsManualLoading(false);
      });
  }, []);

  useEffect(function () {
    fetchSignals();
  }, [fetchSignals]);

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="w-full lg:ml-64 min-h-screen flex flex-col">
        <Header />

        <main className="flex-1 p-4 md:p-8 lg:p-10 pt-20 lg:pt-24 space-y-8 max-w-4xl mx-auto w-full">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-3">
              <Brain className="w-9 h-9 text-neon-cyan drop-shadow-[0_0_10px_rgba(0,240,255,0.6)]" strokeWidth={2.5} />
              <div>
                <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight">AI Signals</h1>
                <p className="text-text-secondary">Real-time trading signals based on RSI/EMA analysis of live Fyers data</p>
              </div>
            </div>
            <motion.button
              onClick={fetchSignals}
              disabled={isLoading || isManualLoading}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-card-bg border border-neon-cyan/30 hover:border-neon-cyan/50 text-white font-medium transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed glass shadow-[0_0_15px_rgba(0,240,255,0.1)]"
            >
              {(isLoading || isManualLoading) ? (
                <Loader2 className="w-5 h-5 animate-spin" strokeWidth={2.5} />
              ) : (
                <Activity className="w-5 h-5" strokeWidth={2.5} />
              )}
              <span>{(isLoading || isManualLoading) ? "Scanning..." : "Scan for Signals"}</span>
            </motion.button>
          </div>

          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-4 flex-wrap">
              {error && (
                <motion.span className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neon-red/10 border border-neon-red/30 text-neon-red text-sm glass">
                  <AlertCircle className="w-4 h-4" strokeWidth={2.5} />
                  {error}
                </motion.span>
              )}
              {!error && signals.length > 0 && (
                <motion.span className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neon-green/10 border border-neon-green/30 text-neon-green text-sm glass">
                  <span className="w-2 h-2 rounded-full bg-neon-green animate-pulse-glow" />
                  {signals.length} signal{signals.length !== 1 ? "s" : ""} active
                </motion.span>
              )}
              {isLoading && (
                <motion.span className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neon-orange/10 border border-neon-orange/30 text-neon-orange text-sm glass">
                  <Loader2 className="w-4 h-4 animate-spin" strokeWidth={2.5} />
                  Fetching AI signals...
                </motion.span>
              )}
              {lastScan && !isLoading && (
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

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
            {signals.length === 0 && !isLoading ? (
              <div className="col-span-full glass rounded-2xl border border-glow-border p-8 text-center">
                <Brain className="w-12 h-12 text-neon-purple/50 mx-auto mb-4" strokeWidth={2} />
                <p className="text-text-secondary">No signals available</p>
                <p className="text-text-muted text-sm mt-1">Click "Scan for Signals" or wait for auto-refresh</p>
              </div>
            ) : (
              signals.map(function (signal, index) {
                var actionColor = getActionColor(signal.signal);
                return (
                  <motion.div
                    key={signal.symbol + "-" + signal.timestamp + "-" + index}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="glass rounded-2xl border border-glow-border p-4 md:p-5 hover:border-neon-cyan/40 transition-all duration-300 group relative overflow-hidden"
                  >
                    {signal.confidence >= 80 && (
                      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-neon-cyan to-transparent opacity-30 group-hover:opacity-60" />
                    )>

                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white tracking-tight">{signal.symbol}</span>
                        <span className="text-[10px] px-2 py-0.5 rounded bg-card-bg/50 border border-glow-border text-text-muted">
                          {signal.ema_trend}
                        </span>
                      </div>
                      <span className={"px-2.5 py-1 rounded text-[10px] font-bold " + actionColor}>
                        {signal.signal}
                      </span>
                    </div>

                    <div className="mb-4">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-text-muted uppercase tracking-wider">Confidence</span>
                        <span className={getConfidenceColor(signal.confidence)}>
                          {signal.confidence}%
                        </span>
                      </div>
                      <div className="w-full bg-card-bg/50 rounded-full h-2 border border-glow-border overflow-hidden relative">
                        <div
                          className={getProgressBarClass(signal.confidence)}
                          style={{ width: signal.confidence + "%" }}
                        />
                      </div>
                    </div>

                    <div className="mb-4 grid grid-cols-2 gap-3">
                      <div className="text-center p-2 rounded bg-card-bg/30 border border-glow-border/50">
                        <span className="text-[10px] text-text-muted uppercase tracking-wider block mb-0.5">RSI</span>
                        <span className="text-sm font-mono font-bold text-neon-cyan">{signal.rsi.toFixed(1)}</span>
                      </div>
                      <div className="text-center p-2 rounded bg-card-bg/30 border border-glow-border/50">
                        <span className="text-[10px] text-text-muted uppercase tracking-wider block mb-0.5">EMA Trend</span>
                        <span className={"text-xs font-mono font-bold " + getTrendColor(signal.ema_trend)}>{signal.ema_trend}</span>
                      </div>
                    </div>

                    <div className="mb-4 text-center">
                      <span className="text-[10px] text-text-muted uppercase tracking-wider block mb-0.5">Current Price</span>
                      <span className="text-lg font-mono font-bold text-neon-cyan">{signal.price.toLocaleString()}</span>
                    </div>

                    <motion.button
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      disabled={signal.signal === "HOLD"}
                      className={getButtonClass(signal.signal)}
                    >
                      {signal.signal === "HOLD" ? "No Setup" : (
                        <>
                          <Play className="w-4 h-4" strokeWidth={2.5} />
                          Execute Trade
                        </>
                      )}
                      <ChevronRight className="w-3 h-3" strokeWidth={2.5} />
                    </motion.button>
                  </motion.div>
                );
              })
            )}
          </div>

          <div className="glass rounded-2xl border border-glow-border p-4 md:p-6">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <Newspaper className="w-5 h-5 text-neon-cyan" strokeWidth={2.5} />
                <h3 className="font-bold text-white">Market News & Sentiment</h3>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded bg-card-bg/50 border border-glow-border text-text-muted">
                Coming Soon
              </span>
            </div>

            <div className="space-y-3 text-center py-4">
              <Brain className="w-10 h-10 text-neon-purple/50 mx-auto mb-3" strokeWidth={2} />
              <p className="text-text-secondary">Grok AI news analysis will be integrated here</p>
              <p className="text-text-muted text-sm mt-1">Financial news sentiment and AI reasoning</p>
            </div>
          </div>

          <div className="text-center text-text-muted text-sm mt-4">
            Powered by Grok AI • Signals refresh every 30 seconds •{" "}
            <Brain className="inline w-4 h-4 text-neon-purple" strokeWidth={2} />
            <span className="text-neon-purple ml-1">RSI/EMA pattern recognition</span>
          </div>
        </main>
      </div>
    </div>
  );
}