"use client";

import { motion } from "framer-motion";
import { Wifi, Bell, User, Circle, ChevronDown } from "lucide-react";

interface BrokerStatus {
  label: string;
  connected: boolean;
}

const brokers: BrokerStatus[] = [
  { label: "Fyers", connected: true },
  { label: "Kotak", connected: true },
];

export function Header() {
  return (
    <motion.header
      initial={{ y: -80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="fixed left-64 right-0 top-0 z-40 h-16 bg-true-black/80 backdrop-blur-md border-b border-glow-border glass flex items-center justify-between px-6"
    >
      {/* Left: Title */}
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Dashboard</h1>
        <p className="text-xs text-text-muted">Welcome back, Abdul</p>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-4">
        {/* Broker Status */}
        <div className="hidden md:flex items-center gap-4 px-3 py-1.5 rounded-full bg-card-bg border border-glow-border glass">
          {brokers.map((broker) => (
            <motion.div
              key={broker.label}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.3 }}
              className="flex items-center gap-1.5"
            >
              <motion.span
                className={`w-2 h-2 rounded-full ${broker.connected ? "bg-neon-green" : "bg-neon-red"}`}
                animate={{ boxShadow: broker.connected ? ["0 0 0 0 rgba(0, 255, 102, 0.7)", "0 0 0 8px rgba(0, 255, 102, 0)"] : undefined }}
                transition={{ duration: 2, repeat: Infinity }}
              />
              <span className="text-xs font-medium text-white capitalize">{broker.label}</span>
              <span className={`text-[10px] font-medium ${broker.connected ? "text-neon-green" : "text-neon-red"}`}>
                {broker.connected ? "Connected" : "Offline"}
              </span>
            </motion.div>
          ))}
        </div>

        {/* Daily PnL */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.4 }}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-neon-orange/20 to-neon-red/20 border border-neon-orange/30 glass shadow-glow-orange"
        >
          <span className="text-xs text-text-muted">Daily PnL</span>
          <span className="font-mono text-lg font-bold text-neon-orange text-glow-green">+₹12,450</span>
        </motion.div>

        {/* Notification Bell */}
        <motion.button
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.5 }}
          className="relative p-2 rounded-xl bg-card-bg border border-glow-border hover:border-neon-cyan/50 hover:bg-card-bg/80 transition-all duration-300 glass"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          <Bell className="w-5 h-5 text-text-secondary hover:text-white transition-colors" strokeWidth={2} />
          <span className="absolute -top-1 -right-1 w-4 h-4 bg-neon-red rounded-full flex items-center justify-center">
            <span className="text-[10px] font-bold text-white">3</span>
          </span>
        </motion.button>

        {/* Profile Avatar */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.6 }}
          className="relative"
        >
          <button className="flex items-center gap-2 p-1.5 pr-3 rounded-xl bg-card-bg border border-glow-border hover:border-neon-cyan/50 transition-all duration-300 glass">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-neon-purple to-neon-cyan flex items-center justify-center">
              <span className="text-true-black font-bold text-sm">A</span>
            </div>
            <div className="hidden md:block text-left">
              <p className="text-sm font-medium text-white">Abdul</p>
              <p className="text-[11px] text-text-muted">Pro Trader</p>
            </div>
            <ChevronDown className="w-4 h-4 text-text-muted" strokeWidth={2.5} />
          </button>
        </motion.div>
      </div>
    </motion.header>
  );
}