"use client";

import { motion } from "framer-motion";
import { Brain, Zap, X, Check, Settings, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";

interface AISignal {
  symbol: string;
  signal: string;
  confidence: number;
  rsi: number;
  ema_trend: string;
  price: number;
  timestamp: string;
}

interface AISignalsResponse {
  signals: AISignal[];
  timestamp: string;
}

export function AISignalCard() {
  const { data: signalsData, isLoading, error, mutate } = useSWR<AISignalsResponse>(
    "dashboard-ai-signals",
    async () => {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com"}/api/v1/ai/signals?symbols=NIFTY,BANKNIFTY,FINNIFTY,MIDCPNIFTY`, {
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    },
    {
      refreshInterval: 30000, // Refresh every 30 seconds for signals
      revalidateOnFocus: false,
      dedupingInterval: 10000,
    }
  );

  // Get the first signal (NIFTY) or none
  const signal = signalsData?.signals?.[0];

  if (isLoading) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[300px] flex flex-col"
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-glow-border bg-card-bg/50">
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-neon-purple" strokeWidth={2.5} />
            <h3 className="font-semibold text-white">Grok AI Radar</h3>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-orange/20 text-neon-orange font-medium animate-pulse">LOADING</span>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3 text-text-secondary">
            <span className="animate-spin">⏳</span>
            <span>Loading AI signals...</span>
          </div>
        </div>
      </motion.div>
    );
  }

  if (error) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[300px] flex flex-col"
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-glow-border bg-card-bg/50">
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-neon-purple" strokeWidth={2.5} />
            <h3 className="font-semibold text-white">Grok AI Radar</h3>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-red/20 text-neon-red font-medium">ERROR</span>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-center text-text-secondary">
            <p className="mb-2">Failed to load AI signals</p>
            <p className="text-sm text-neon-red/80">{error.message}</p>
          </div>
        </div>
      </motion.div>
    );
  }

  if (!signal) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[300px] flex flex-col"
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-glow-border bg-card-bg/50">
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-neon-purple" strokeWidth={2.5} />
            <h3 className="font-semibold text-white">Grok AI Radar</h3>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-orange/20 text-neon-orange font-medium">NO DATA</span>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-text-muted">
            <p>No signals available</p>
            <p className="text-sm mt-1">Connect Fyers to get live AI signals</p>
          </div>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.5 }}
      className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[300px] flex flex-col"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-glow-border bg-card-bg/50">
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-neon-purple" strokeWidth={2.5} />
          <h3 className="font-semibold text-white">Grok AI Radar</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] px-2 py-0.5 rounded bg-neon-green/20 text-neon-green font-medium flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-neon-green animate-pulse-glow" />
            LIVE
          </span>
        </div>
      </div>

      {/* Signal Content */}
      <div className="flex-1 p-5 flex flex-col justify-center">
        {/* Signal Type & Instrument */}
        <div className="mb-5">
          <div className="flex items-center gap-3 mb-2">
            <motion.span
              className={`px-3 py-1 rounded-full text-xs font-bold ${signal.signal === "BUY" ? "bg-neon-green/20 text-neon-green border border-neon-green/30" : signal.signal === "SELL" ? "bg-neon-red/20 text-neon-red border border-neon-red/30" : "bg-neon-orange/20 text-neon-orange border border-neon-orange/30"}`}
              animate={signal.signal === "BUY" ? { boxShadow: ["0 0 0 0 rgba(0, 255, 102, 0.4)", "0 0 0 8px rgba(0, 255, 102, 0)"] } : signal.signal === "SELL" ? { boxShadow: ["0 0 0 0 rgba(255, 0, 60, 0.4)", "0 0 0 8px rgba(255, 0, 60, 0)"] } : undefined}
              transition={{ duration: 2, repeat: Infinity }}
            >
              {signal.signal}
            </motion.span>
            <Zap className="w-4 h-4 text-neon-orange animate-pulse" strokeWidth={2.5} />
          </div>
          <p className="text-2xl font-bold text-white tracking-tight">{signal.symbol}</p>
        </div>

        {/* Confidence */}
        <div className="mb-5">
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm text-text-secondary">Confidence Score</span>
            <span className="font-mono font-bold text-neon-cyan text-glow-cyan">{signal.confidence}%</span>
          </div>
          <div className="h-2 bg-card-bg rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${signal.confidence}%` }}
              transition={{ type: "spring", stiffness: 100, damping: 15, delay: 0.6 }}
              className="h-full bg-gradient-to-r from-neon-cyan to-neon-green rounded-full shadow-glow-cyan"
            />
          </div>
        </div>

        {/* Price Levels */}
        <div className="grid grid-cols-3 gap-3 mb-5">
          <div className="p-3 rounded-xl bg-card-bg border border-glow-border">
            <p className="text-[11px] text-text-muted uppercase tracking-wider">Entry</p>
            <p className="font-mono font-semibold text-white text-lg">₹{signal.price.toFixed(2)}</p>
          </div>
          <div className="p-3 rounded-xl bg-card-bg border border-glow-border">
            <p className="text-[11px] text-text-muted uppercase tracking-wider">RSI</p>
            <p className="font-mono font-semibold text-neon-cyan text-lg">{signal.rsi.toFixed(1)}</p>
          </div>
          <div className="p-3 rounded-xl bg-card-bg border border-glow-border">
            <p className="text-[11px] text-text-muted uppercase tracking-wider">EMA Trend</p>
            <p className={`font-mono font-semibold ${signal.ema_trend === "BULLISH" ? "text-neon-green" : signal.ema_trend === "BEARISH" ? "text-neon-red" : "text-neon-orange"} text-lg`}>{signal.ema_trend}</p>
          </div>
        </div>

        {/* Details */}
        <div className="p-3 rounded-xl bg-neon-purple/5 border border-neon-purple/20 mb-5">
          <p className="text-sm text-text-secondary">
            {signal.timestamp ? `Last updated: ${new Date(signal.timestamp).toLocaleTimeString()}` : "Real-time signal from Grok AI"}
          </p>
        </div>

        {/* Refresh Button */}
        <motion.button
          onClick={() => mutate()}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-neon-purple to-neon-cyan text-true-black font-bold text-lg shadow-glow-purple transition-all duration-300 flex items-center justify-center gap-2"
        >
          <Check className="w-5 h-5" strokeWidth={2.5} />
          Refresh Signal
        </motion.button>
      </div>
    </motion.div>
  );
}