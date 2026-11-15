"use client";

import { motion } from "framer-motion";
import { TrendingUp, Sparkles, Zap, Brain, Shield, Globe, BarChart3 } from "lucide-react";
import { useMarketStatus } from "@/lib/hooks";

export function HeroBanner() {
  const { status, isLoading } = useMarketStatus();
  const isMarketOpen = status?.is_open || false;
  const isTradingDay = status?.is_trading_day || false;
  const timeToClose = status?.time_to_close_minutes || 0;
  const nextTradingDay = status?.next_open ? new Date(status.next_open) : new Date();
  
  const marketStatus = isMarketOpen ? "OPEN" : "CLOSED";
  const marketStatusColor = isMarketOpen ? "neon-green" : "neon-red";

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 0.1 }}
      className="glass rounded-3xl border border-glow-border p-4 md:p-6 lg:p-8 relative overflow-hidden"
    >
      <div className="absolute -top-10 -right-10 w-60 h-60 rounded-full bg-neon-cyan/5 blur-3xl" />
      <div className="absolute -bottom-10 -left-10 w-60 h-60 rounded-full bg-neon-purple/5 blur-3xl" />

      <div className="relative z-10 grid grid-cols-1 md:grid-cols-4 gap-4 md:gap-8">
        {/* Main Title */}
        <div className="md:col-span-2">
          <h1 className="text-2xl md:text-3xl lg:text-4xl font-bold text-white tracking-tight leading-tight">
            Autonomous Options Trading Platform
          </h1>
          <p className="text-text-secondary mt-2 md:mt-3 max-w-xl">
            Real-time market data from Fyers API v3 • Paper trading with Kotak Neo • AI signals powered by Grok
          </p>
          
          {/* Market Status Badge */}
          <div className="flex items-center gap-4 mt-4 md:mt-6 flex-wrap">
            <motion.span
              className={`flex items-center gap-2 px-4 py-2 rounded-full bg-${marketStatusColor}/20 border border-${marketStatusColor}/30 text-${marketStatusColor} font-medium glass`}
              animate={{ boxShadow: isMarketOpen ? ["0 0 0 0 rgba(0, 255, 102, 0.6)", "0 0 0 10px rgba(0, 255, 102, 0)"] : undefined }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              <span className={`w-2 h-2 rounded-full bg-${marketStatusColor} ${isMarketOpen ? "animate-pulse-glow" : ""}`} />
              <span className="text-sm md:text-base">
                Market {marketStatus}
                {isMarketOpen && <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-neon-green/30 text-neon-green font-mono">{timeToClose}m to close</span>}
                {!isMarketOpen && !isTradingDay && <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-neon-orange/30 text-neon-orange font-mono">Next: {nextTradingDay.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" })}</span>}
              </span>
            </motion.span>
            
            <span className="text-xs text-text-muted flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-neon-cyan" />
              IST: {new Date().toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })}
            </span>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 gap-3 md:col-span-2 lg:col-span-2">
          {[
            { icon: Zap, label: "Live Data", value: "Fyers v3", color: "neon-cyan", desc: "WebSocket + REST" },
            { icon: Brain, label: "AI Signals", value: "Grok", color: "neon-purple", desc: "RSI + EMA + OI" },
            { icon: Shield, label: "Execution", value: "Kotak Neo", color: "neon-orange", desc: "Paper + Live" },
            { icon: BarChart3, label: "Backtest", value: "Engine", color: "neon-green", desc: "Historical CSV" },
          ].map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 + i * 0.1 }}
              className="glass rounded-2xl border border-glow-border p-4 md:p-5 hover:border-neon-cyan/50 transition-all duration-300 group"
            >
              <div className="flex items-start gap-3">
                <div className={`w-10 h-10 rounded-xl bg-${stat.color}/20 flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform`}>
                  <stat.icon className={`w-5 h-5 text-${stat.color}`} strokeWidth={2.5} />
                </div>
                <div className="min-w-0">
                  <p className="text-[10px] text-text-muted uppercase tracking-wider font-medium">{stat.label}</p>
                  <p className="font-mono font-bold text-white text-lg md:text-xl truncate">{stat.value}</p>
                  <p className="text-[10px] text-text-muted mt-0.5 truncate">{stat.desc}</p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}