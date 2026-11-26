"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { BarChart3, Activity, Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { useIndicators } from "@/lib/hooks";

export default function IndicatorsPage() {
  const [symbol, setSymbol] = useState("RELIANCE");
  const [interval, setInterval] = useState("15m");
  const { indicators, isLoading, isError, error, timestamp, data_source, mutate } = useIndicators(symbol, interval);

  const getColor = (name: string, v: number | null): string => {
    if (v === null) return "text-text-muted";
    const l = name.toLowerCase();
    if (l.includes("rsi")) return v > 70 ? "text-neon-red" : v < 30 ? "text-neon-green" : "text-text-secondary";
    if (l.includes("macd")) return v > 0 ? "text-neon-green" : "text-neon-red";
    if (l.includes("supertrend")) return v > 0 ? "text-neon-green" : "text-neon-red";
    return "text-white";
  };

  const getBadge = (name: string, v: number | null): string => {
    if (v === null) return "N/A";
    const l = name.toLowerCase();
    if (l.includes("rsi")) { if (v > 70) return "Overbought"; if (v < 30) return "Oversold"; return "Neutral"; }
    if (l.includes("macd")) return v > 0 ? "Bullish" : "Bearish";
    if (l.includes("supertrend")) return v > 0 ? "Uptrend" : "Downtrend";
    return "";
  };

  const badgeColor = (name: string, v: number | null): string => {
    if (v === null) return "bg-card-bg text-text-muted";
    const l = name.toLowerCase();
    if (l.includes("rsi")) { if (v > 70) return "bg-neon-red/20 text-neon-red border border-neon-red/30"; if (v < 30) return "bg-neon-green/20 text-neon-green border border-neon-green/30"; return "bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/30"; }
    if (l.includes("macd")) return v > 0 ? "bg-neon-green/20 text-neon-green border border-neon-green/30" : "bg-neon-red/20 text-neon-red border border-neon-red/30";
    if (l.includes("supertrend")) return v > 0 ? "bg-neon-green/20 text-neon-green border border-neon-green/30" : "bg-neon-red/20 text-neon-red border border-neon-red/30";
    return "bg-card-bg text-text-secondary";
  };

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="w-full lg:ml-64 min-h-screen flex flex-col">
        <Header />
        <main className="flex-1 p-4 md:p-8 lg:p-10 pt-20 lg:pt-24 space-y-6 max-w-5xl mx-auto w-full">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-3"><BarChart3 className="w-8 h-8 text-neon-cyan" strokeWidth={2.5} /><div><h1 className="text-2xl md:text-3xl font-bold text-white">Technical Indicators</h1><p className="text-text-secondary">Real-time indicators from Yahoo Finance data</p></div></div>
            <button onClick={() => mutate()} className="flex items-center gap-2 px-4 py-2 rounded-xl bg-card-bg border border-glow-border text-white hover:border-neon-cyan"><RefreshCw className="w-4 h-4" />Refresh</button>
          </div>
          <div className="glass rounded-2xl border border-glow-border p-4 md:p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div><label className="block text-sm text-text-secondary mb-1">Symbol</label><input type="text" value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="e.g. RELIANCE, NIFTY 50" className="w-full bg-true-black border border-glow-border rounded-lg p-3 text-white outline-none" /></div>
              <div><label className="block text-sm text-text-secondary mb-1">Interval</label><select value={interval} onChange={(e) => setInterval(e.target.value)} className="w-full bg-true-black border border-glow-border rounded-lg p-3 text-white outline-none"><option value="1m">1 minute</option><option value="2m">2 minutes</option><option value="5m">5 minutes</option><option value="15m">15 minutes</option><option value="30m">30 minutes</option><option value="1h">1 hour</option><option value="1d">1 day</option><option value="1wk">1 week</option></select></div>
            </div>
          </div>
          {isLoading && <div className="flex items-center justify-center h-32"><Loader2 className="w-6 h-6 text-neon-cyan animate-spin" /><span className="ml-2 text-text-secondary">Loading indicators...</span></div>}
          {isError && <div className="glass p-4 rounded-xl border border-neon-red/50 bg-neon-red/10"><div className="flex items-center gap-2 text-neon-red"><AlertCircle className="w-5 h-5" /><span className="font-semibold">Error loading indicators</span></div><p className="text-text-secondary mt-1">{error}</p></div>}
          {!isLoading && !isError && indicators.length > 0 && (
            <div className="glass rounded-2xl border border-glow-border p-4 md:p-6">
              <div className="flex items-center justify-between mb-4"><h2 className="text-lg font-semibold text-white">Live Indicators</h2><div className="text-xs text-text-secondary">{data_source && <span className="mr-3">Source: {data_source}</span>}{timestamp && <span>{new Date(timestamp).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" })}</span>}</div></div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">{indicators.map((ind: any, idx: number) => (
                <div key={idx} className="bg-card-bg/50 border border-glow-border rounded-xl p-4">
                  <div className="flex items-center justify-between mb-2"><span className="text-sm font-medium text-white">{ind.name || ind.display_name || "Unknown"}</span>{getBadge(ind.name || "", ind.value) && <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${badgeColor(ind.name || "", ind.value)}`}>{getBadge(ind.name || "", ind.value)}</span>}</div>
                  <div className={`text-2xl font-bold font-mono ${getColor(ind.name || "", ind.value)}`}>{ind.value !== null && ind.value !== undefined ? ind.value.toFixed(2) : "N/A"}</div>
                  {ind.category && <p className="text-xs text-text-muted mt-1">{ind.category}</p>}
                </div>
              ))}</div>
            </div>
          )}
          {!isLoading && !isError && indicators.length === 0 && <div className="glass rounded-2xl border border-glow-border p-12 text-center"><Activity className="w-12 h-12 text-text-muted mx-auto mb-4" /><h3 className="text-lg font-semibold text-white mb-2">No Indicator Data</h3><p className="text-text-secondary">Try a different symbol or interval, or wait for data to load.</p></div>}
        </main>
      </div>
    </div>
  );
}
