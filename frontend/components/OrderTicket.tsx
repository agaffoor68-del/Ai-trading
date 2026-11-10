"use client";

import { motion } from "framer-motion";
import { ShoppingBag, TrendingUp, Target, Shield, Radio, Check } from "lucide-react";
import { useState } from "react";

export function OrderTicket() {
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [mode, setMode] = useState<"PAPER" | "LIVE">("PAPER");
  const [quantity, setQuantity] = useState(50);
  const [price, setPrice] = useState(120.40);
  const [stopLoss, setStopLoss] = useState(85.00);
  const [target, setTarget] = useState(185.00);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.6 }}
      className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[380px] flex flex-col"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-glow-border bg-card-bg/50">
        <div className="flex items-center gap-2">
          <ShoppingBag className="w-5 h-5 text-neon-orange" strokeWidth={2.5} />
          <h3 className="font-semibold text-white">Order Ticket</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${mode === "LIVE" ? "bg-neon-red/20 text-neon-red" : "bg-neon-green/20 text-neon-green"}`}>
            {mode}
          </span>
        </div>
      </div>

      {/* Form */}
      <div className="flex-1 p-5 space-y-4 overflow-y-auto">
        {/* Side Toggle */}
        <div>
          <label className="text-[11px] text-text-muted uppercase tracking-wider mb-2 block">Side</label>
          <div className="flex gap-2">
            {["BUY", "SELL"].map((s) => (
              <motion.button
                key={s}
                onClick={() => setSide(s as "BUY" | "SELL")}
                whileTap={{ scale: 0.97 }}
                className={`flex-1 py-2.5 rounded-xl font-bold text-sm transition-all duration-300 ${
                  side === s
                    ? s === "BUY"
                      ? "bg-neon-green/20 text-neon-green border border-neon-green/30 shadow-glow-green"
                      : "bg-neon-red/20 text-neon-red border border-neon-red/30 shadow-glow-red"
                    : "bg-card-bg text-text-secondary border border-glow-border hover:border-neon-cyan/30"
                }`}
              >
                {s}
              </motion.button>
            ))}
          </div>
        </div>

        {/* Mode Toggle */}
        <div>
          <label className="text-[11px] text-text-muted uppercase tracking-wider mb-2 block">Mode</label>
          <div className="flex gap-2">
            {["PAPER", "LIVE"].map((m) => (
              <motion.button
                key={m}
                onClick={() => setMode(m as "PAPER" | "LIVE")}
                whileTap={{ scale: 0.97 }}
                className={`flex-1 py-2.5 rounded-xl font-bold text-sm transition-all duration-300 ${
                  mode === m
                    ? m === "LIVE"
                      ? "bg-neon-red/20 text-neon-red border border-neon-red/30 shadow-glow-red"
                      : "bg-neon-green/20 text-neon-green border border-neon-green/30 shadow-glow-green"
                    : "bg-card-bg text-text-secondary border border-glow-border hover:border-neon-cyan/30"
                }`}
              >
                {m}
              </motion.button>
            ))}
          </div>
        </div>

        {/* Inputs Grid */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] text-text-muted uppercase tracking-wider mb-1 block">Qty (Lot Size)</label>
            <div className="relative">
              <ShoppingBag className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none text-white placeholder-text-muted"
                placeholder="50"
              />
            </div>
          </div>
          <div>
            <label className="text-[11px] text-text-muted uppercase tracking-wider mb-1 block">Price</label>
            <div className="relative">
              <TrendingUp className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
              <input
                type="number"
                step="0.05"
                value={price}
                onChange={(e) => setPrice(parseFloat(e.target.value) || 0)}
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none text-white placeholder-text-muted"
                placeholder="120.40"
              />
            </div>
          </div>
          <div>
            <label className="text-[11px] text-text-muted uppercase tracking-wider mb-1 block">Stop Loss</label>
            <div className="relative">
              <Shield className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
              <input
                type="number"
                step="0.05"
                value={stopLoss}
                onChange={(e) => setStopLoss(parseFloat(e.target.value) || 0)}
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none text-white placeholder-text-muted"
                placeholder="85.00"
              />
            </div>
          </div>
          <div>
            <label className="text-[11px] text-text-muted uppercase tracking-wider mb-1 block">Target</label>
            <div className="relative">
              <Target className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
              <input
                type="number"
                step="0.05"
                value={target}
                onChange={(e) => setTarget(parseFloat(e.target.value) || 0)}
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none text-white placeholder-text-muted"
                placeholder="185.00"
              />
            </div>
          </div>
        </div>

        {/* Risk Summary */}
        <div className="p-3 rounded-xl bg-card-bg border border-glow-border">
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-text-secondary">Risk:Reward</span>
            <span className="font-mono font-bold text-neon-cyan">1:{( (target - price) / (price - stopLoss) ).toFixed(2)}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-text-secondary">Max Loss</span>
            <span className="font-mono font-bold text-neon-red">₹{(quantity * (price - stopLoss)).toLocaleString()}</span>
          </div>
        </div>

        {/* Place Order Button */}
        <motion.button
          whileHover={{ scale: 1.02, boxShadow: "0 0 25px rgba(249, 115, 22, 0.5)" }}
          whileTap={{ scale: 0.98 }}
          className="w-full py-3.5 rounded-xl bg-gradient-to-r from-neon-orange to-neon-red text-white font-bold text-lg shadow-glow-orange transition-all duration-300 flex items-center justify-center gap-2"
        >
          <Radio className="w-5 h-5" strokeWidth={2.5} />
          Place Order
        </motion.button>
      </div>
    </motion.div>
  );
}