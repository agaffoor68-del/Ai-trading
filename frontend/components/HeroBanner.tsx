"use client";

import { motion } from "framer-motion";
import { Sparkles, ArrowRight, TrendingUp } from "lucide-react";

export function HeroBanner() {
  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 0.3 }}
      className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-purple-900/30 via-purple-900/10 to-true-black border border-neon-purple/30 p-8 glass shadow-glow-purple"
    >
      {/* Background glow orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-20 -right-20 w-80 h-80 rounded-full bg-neon-purple/20 blur-3xl animate-pulse" />
        <div className="absolute -bottom-20 -left-20 w-60 h-60 rounded-full bg-neon-cyan/15 blur-3xl animate-pulse" style={{ animationDelay: "1s" }} />
      </div>

      <div className="relative flex flex-col md:flex-row md:items-center md:justify-between gap-6">
        <div className="max-w-2xl">
          <div className="flex items-center gap-2 mb-4">
            <motion.div
              animate={{ rotate: [0, 5, -5, 0] }}
              transition={{ duration: 3, repeat: Infinity }}
              className="w-2 h-2 rounded-full bg-neon-green"
            />
            <span className="text-sm font-medium text-neon-green uppercase tracking-wider">AI Brain Active</span>
          </div>
          <h2 className="text-3xl md:text-4xl font-bold text-white leading-tight mb-3">
            3 High-Probability Signals
            <br />
            <span className="text-neon-cyan text-glow-cyan">Found Today</span>
          </h2>
          <p className="text-text-secondary text-lg max-w-md">
            Grok AI has analyzed market structure, order flow, and news sentiment.
            NIFTY & BANKNIFTY showing strong directional bias.
          </p>
        </div>

        <motion.button
          whileHover={{ scale: 1.02, boxShadow: "0 0 30px rgba(0, 240, 255, 0.4)" }}
          whileTap={{ scale: 0.98 }}
          className="flex items-center gap-2 px-8 py-4 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black font-bold text-lg shadow-glow-cyan transition-all duration-300 group"
        >
          <Sparkles className="w-5 h-5" strokeWidth={2.5} />
          <span>View AI Signals</span>
          <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" strokeWidth={2.5} />
        </motion.button>
      </div>

      {/* Stats bar at bottom */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-neon-purple/30 to-transparent" />
      <div className="relative mt-8 flex flex-wrap gap-6 md:gap-10 pt-6 border-t border-glow-border">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-neon-green" strokeWidth={2.5} />
          <div>
            <p className="text-2xl font-bold text-white">87%</p>
            <p className="text-xs text-text-muted">Avg Win Rate</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-neon-orange" strokeWidth={2.5} />
          <div>
            <p className="text-2xl font-bold text-white">2.4:1</p>
            <p className="text-xs text-text-muted">Risk:Reward</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-neon-cyan" strokeWidth={2.5} />
          <div>
            <p className="text-2xl font-bold text-white">14</p>
            <p className="text-xs text-text-muted">Signals/Week</p>
          </div>
        </div>
      </div>
    </motion.section>
  );
}