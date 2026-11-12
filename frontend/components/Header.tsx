"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Wifi, Bell, User, Circle, ChevronDown, Menu, X } from "lucide-react";
import { api } from "@/lib/api";
import { useSidebar } from "./Sidebar";

interface BrokerStatus {
  label: string;
  connected: boolean;
}

export function Header() {
  const { isOpen, toggle } = useSidebar();
  const [brokers, setBrokers] = useState<BrokerStatus[]>([
    { label: "Fyers", connected: false },
    { label: "Kotak", connected: false },
  ]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.getBrokerStatus();
      if (data) {
        setBrokers([
          { label: "Fyers", connected: data.fyers?.connected ?? false },
          { label: "Kotak", connected: data.kotak?.connected ?? false },
        ]);
      }
    } catch (err) {
      console.warn("Failed to fetch broker status:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    // Refresh every 30 seconds
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  return (
    <motion.header
      initial={{ y: -80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="fixed left-0 right-0 top-0 z-40 h-16 bg-true-black/80 backdrop-blur-md border-b border-glow-border glass flex items-center justify-between px-4 md:px-6 lg:ml-64"
    >
      {/* Left: Hamburger Menu + Title */}
      <div className="flex items-center gap-4">
        {/* Hamburger Menu - Mobile only */}
        <motion.button
          onClick={toggle}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="lg:hidden p-2 rounded-xl bg-card-bg border border-glow-border hover:border-neon-cyan/50 hover:bg-card-bg/80 transition-all duration-300 glass"
          aria-label={isOpen ? "Close sidebar" : "Open sidebar"}
        >
          {isOpen ? (
            <X className="w-6 h-6 text-white" strokeWidth={2.5} />
          ) : (
            <Menu className="w-6 h-6 text-white" strokeWidth={2.5} />
          )}
        </motion.button>
        
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-white tracking-tight">Dashboard</h1>
          <p className="hidden md:block text-xs text-text-muted">Welcome back, Abdul</p>
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-3 md:gap-4">
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
                animate={broker.connected ? { boxShadow: ["0 0 0 0 rgba(0, 255, 102, 0.7)", "0 0 0 8px rgba(0, 255, 102, 0)"] } : undefined}
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
          className="hidden sm:flex items-center gap-2 px-3 md:px-4 py-2 rounded-xl bg-gradient-to-r from-neon-orange/20 to-neon-red/20 border border-neon-orange/30 glass shadow-glow-orange"
        >
          <span className="text-xs text-text-muted">Daily PnL</span>
          <span className="font-mono text-sm md:text-lg font-bold text-neon-orange text-glow-green">+₹12,450</span>
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