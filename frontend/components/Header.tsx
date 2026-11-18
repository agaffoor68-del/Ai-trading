"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Wifi, Bell, User, Circle, ChevronDown, Menu, X, Shield, AlertCircle, CheckCircle, LogOut, Crown, Settings } from "lucide-react";
import { useFullStatus, useMarketStatus } from "@/lib/hooks";
import { useMe } from "@/lib/hooks";
import { useSidebar } from "./Sidebar";
import { api } from "@/lib/api-client";
import { useRouter } from "next/navigation";

interface BrokerStatus {
  label: string;
  connected: boolean;
  valid?: boolean;
  message?: string;
}

export function Header() {
  const { isOpen, toggle } = useSidebar();
  const { status, isLoading, mutate } = useFullStatus();
  const { user, isLoading: userLoading, mutate: mutateMe } = useMe();
  const { status: marketStatus } = useMarketStatus();
  const isMarketOpen = marketStatus?.is_open ?? false;
  const isTradingDay = marketStatus?.is_trading_day ?? false;
  const timeToCloseMinutes = marketStatus?.time_to_close_minutes ?? 0;
  // /api/v1/fyers/status returns a FLAT object: { connected, valid, message, ... }
  const fyersConnected = Boolean(status?.connected) && Boolean(status?.valid);
  const kotakConfigured = false;
  const kotakConnected = false;
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const router = useRouter();

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => mutate(), 30000);
    return () => clearInterval(interval);
  }, [mutate]);

  const handleLogout = async () => {
    try {
      await api.logout();
      mutateMe();
      router.push("/login");
    } catch (err) {
      console.error("Logout failed:", err);
    }
  };

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
          <p className="hidden md:block text-xs text-text-muted">
            {user ? `Welcome back, ${user.email.split("@")[0]}` : "Welcome back, Trader"}
          </p>
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-3 md:gap-4">
        {/* Broker Status Badges */}
        <div className="hidden md:flex items-center gap-4 px-3 py-1.5 rounded-full bg-card-bg border border-glow-border glass">
          {/* Fyers */}
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3 }}
            className="flex items-center gap-1.5"
          >
            <motion.span
              className={`w-2 h-2 rounded-full ${fyersConnected ? "bg-neon-green" : "bg-neon-red"}`}
              animate={fyersConnected ? { boxShadow: ["0 0 0 0 rgba(0, 255, 102, 0.7)", "0 0 0 8px rgba(0, 255, 102, 0)"] } : undefined}
              transition={{ duration: 2, repeat: Infinity }}
            />
            <span className="text-xs font-medium text-white capitalize">Fyers</span>
            <span className={`text-[10px] font-medium ${fyersConnected ? "text-neon-green" : "text-neon-red"}`}>
              {fyersConnected ? "Connected" : "Offline"}
            </span>
          </motion.div>

          {/* Kotak */}
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3 }}
            className="flex items-center gap-1.5"
          >
            <motion.span
              className={`w-2 h-2 rounded-full ${kotakConfigured ? (kotakConnected ? "bg-neon-green" : "bg-neon-orange") : "bg-neon-red"}`}
              animate={kotakConnected ? { boxShadow: ["0 0 0 0 rgba(0, 255, 102, 0.7)", "0 0 0 8px rgba(0, 255, 102, 0)"] } : undefined}
              transition={{ duration: 2, repeat: Infinity }}
            />
            <span className="text-xs font-medium text-white capitalize">Kotak</span>
            <span className={`text-[10px] font-medium ${kotakConnected ? "text-neon-green" : kotakConfigured ? "text-neon-orange" : "text-neon-red"}`}>
              {kotakConnected ? "Connected" : kotakConfigured ? "Configured, not logged in" : "Not configured"}
            </span>
          </motion.div>
        </div>

        {/* Market Status */}
        <motion.div
          className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-card-bg border border-glow-border glass"
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3 }}
        >
          <motion.span
            className={`w-2 h-2 rounded-full ${isMarketOpen ? "bg-neon-green animate-pulse-glow" : "bg-neon-red"}`}
          />
          <span className="text-xs font-medium text-white">
            {isMarketOpen 
              ? `Market Open • ${timeToCloseMinutes}m to close` 
              : isTradingDay 
                ? "Market Closed" 
                : "Weekend / Holiday"
            }
          </span>
        </motion.div>

        {/* Daily PnL - placeholder until backend has it */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.4 }}
          className="hidden sm:flex items-center gap-2 px-3 md:px-4 py-2 rounded-xl bg-gradient-to-r from-neon-orange/20 to-neon-red/20 border border-neon-orange/30 glass shadow-glow-orange"
        >
          <span className="text-xs text-text-muted">Daily PnL</span>
          <span className="font-mono text-sm md:text-lg font-bold text-neon-orange text-glow-green">—</span>
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
            <span className="text-[10px] font-bold text-white">0</span>
          </span>
        </motion.button>

        {/* Profile Avatar with Dropdown */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.6 }}
          className="relative"
        >
          <div className="relative">
            <button
              onClick={() => setShowProfileMenu(!showProfileMenu)}
              className="flex items-center gap-2 p-1.5 pr-3 rounded-xl bg-card-bg border border-glow-border hover:border-neon-cyan/50 transition-all duration-300 glass"
            >
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-neon-purple to-neon-cyan flex items-center justify-center">
                {user ? (
                  <span className="text-true-black font-bold text-sm">
                    {user.email.charAt(0).toUpperCase()}
                  </span>
                ) : (
                  <span className="text-true-black font-bold text-sm">T</span>
                )}
              </div>
              <div className="hidden md:block text-left">
                <p className="text-sm font-medium text-white">
                  {user ? user.email.split("@")[0] : "Trader"}
                </p>
                <p className="text-[11px] text-text-muted">
                  {user?.role === "ADMIN" ? "Admin" : user?.subscription?.plan_type === "Pro" ? "Pro Plan" : "Free Plan"}
                </p>
              </div>
              <ChevronDown className={`w-4 h-4 text-text-muted transition-transform ${showProfileMenu ? "rotate-180" : ""}`} strokeWidth={2.5} />
            </button>

            {/* Profile Dropdown */}
            {showProfileMenu && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                className="absolute right-0 mt-2 w-56 glass rounded-xl border border-glow-border py-2 shadow-xl z-50"
              >
                <div className="px-4 py-3 border-b border-glow-border">
                  <p className="text-sm font-medium text-white">{user?.email || "Not logged in"}</p>
                  <p className="text-xs text-text-muted">
                    {user?.role === "ADMIN" ? (
                      <span className="flex items-center gap-1 text-neon-purple">
                        <Crown className="w-3 h-3" strokeWidth={2.5} />
                        Admin
                      </span>
                    ) : (
                      user?.subscription?.plan_type === "Pro" ? "Pro Plan" : "Free Plan"
                    )}
                  </p>
                </div>
                
                <button
                  onClick={() => { setShowProfileMenu(false); window.location.href = "/settings"; }}
                  className="w-full flex items-center gap-3 px-4 py-2 text-white hover:bg-card-bg/50 transition-colors"
                >
                  <Settings className="w-4 h-4" strokeWidth={2.5} />
                  Settings
                </button>
                
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-3 px-4 py-2 text-neon-red hover:bg-neon-red/10 transition-colors"
                >
                  <LogOut className="w-4 h-4" strokeWidth={2.5} />
                  Logout
                </button>
              </motion.div>
            )}
          </div>
        </motion.div>
      </div>
    </motion.header>
  );
}