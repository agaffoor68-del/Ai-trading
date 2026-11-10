"use client";

import { motion } from "framer-motion";
import { Brain, Zap, X, Check, Settings, SlidersHorizontal } from "lucide-react";
import { useState } from "react";

interface Signal {
  id: string;
  type: "BUY" | "SELL";
  instrument: string;
  confidence: number;
  entry: number;
  target: number;
  stopLoss: number;
  reasoning: string;
}

const mockSignal: Signal = {
  id: "sig_001",
  type: "BUY",
  instrument: "NIFTY 24350 CE",
  confidence: 85,
  entry: 120.40,
  target: 185.00,
  stopLoss: 85.00,
  reasoning: "Strong bullish structure on 15min. OI buildup at 24300-24350 strikes. Grok sentiment: Positive on banking heavyweights.",
};

export function AISignalCard() {
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
          <span className="text-[10px] px-2 py-0.5 rounded bg-neon-green/20 text-neon-green font-medium">LIVE</span>
        </div>
      </div>

      {/* Signal Content */}
      <div className="flex-1 p-5 flex flex-col justify-center">
        {/* Signal Type & Instrument */}
        <div className="mb-5">
          <div className="flex items-center gap-3 mb-2">
            <motion.span
              className={`px-3 py-1 rounded-full text-xs font-bold ${mockSignal.type === "BUY" ? "bg-neon-green/20 text-neon-green border border-neon-green/30" : "bg-neon-red/20 text-neon-red border border-neon-red/30"}`}
              animate={{ boxShadow: mockSignal.type === "BUY" ? ["0 0 0 0 rgba(0, 255, 102, 0.4)", "0 0 0 8px rgba(0, 255, 102, 0)"] : ["0 0 0 0 rgba(255, 0, 60, 0.4)", "0 0 0 8px rgba(255, 0, 60, 0)"] }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              {mockSignal.type}
            </motion.span>
            <Zap className="w-4 h-4 text-neon-orange animate-pulse" strokeWidth={2.5} />
          </div>
          <p className="text-2xl font-bold text-white tracking-tight">{mockSignal.instrument}</p>
        </div>

        {/* Confidence */}
        <div className="mb-5">
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm text-text-secondary">Confidence Score</span>
            <span className="font-mono font-bold text-neon-cyan text-glow-cyan">{mockSignal.confidence}%</span>
          </div>
          <div className="h-2 bg-card-bg rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${mockSignal.confidence}%` }}
              transition={{ type: "spring", stiffness: 100, damping: 15, delay: 0.6 }}
              className="h-full bg-gradient-to-r from-neon-cyan to-neon-green rounded-full shadow-glow-cyan"
            />
          </div>
        </div>

        {/* Price Levels */}
        <div className="grid grid-cols-3 gap-3 mb-5">
          <div className="p-3 rounded-xl bg-card-bg border border-glow-border">
            <p className="text-[11px] text-text-muted uppercase tracking-wider">Entry</p>
            <p className="font-mono font-semibold text-white text-lg">₹{mockSignal.entry.toFixed(2)}</p>
          </div>
          <div className="p-3 rounded-xl bg-card-bg border border-glow-border">
            <p className="text-[11px] text-text-muted uppercase tracking-wider">Target</p>
            <p className="font-mono font-semibold text-neon-green text-lg">₹{mockSignal.target.toFixed(2)}</p>
          </div>
          <div className="p-3 rounded-xl bg-card-bg border border-glow-border">
            <p className="text-[11px] text-text-muted uppercase tracking-wider">Stop Loss</p>
            <p className="font-mono font-semibold text-neon-red text-lg">₹{mockSignal.stopLoss.toFixed(2)}</p>
          </div>
        </div>

        {/* Reasoning */}
        <div className="p-3 rounded-xl bg-neon-purple/5 border border-neon-purple/20 mb-5">
          <p className="text-sm text-text-secondary">{mockSignal.reasoning}</p>
        </div>

        {/* Execute Button */}
        <motion.button
          whileHover={{ scale: 1.02, boxShadow: "0 0 25px rgba(0, 255, 102, 0.4)" }}
          whileTap={{ scale: 0.98 }}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-neon-green to-neon-cyan text-true-black font-bold text-lg shadow-glow-green transition-all duration-300 flex items-center justify-center gap-2"
        >
          <Check className="w-5 h-5" strokeWidth={2.5} />
          Execute Trade
        </motion.button>
      </div>
    </motion.div>
  );
}