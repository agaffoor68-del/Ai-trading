"use client";

import { motion } from "framer-motion";
import { LayoutDashboard, TrendingUp, Brain, List, BarChart, Settings, LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/market", label: "Market Watch", icon: TrendingUp },
  { href: "/signals", label: "AI Signals", icon: Brain },
  { href: "/options", label: "Options Chain", icon: List },
  { href: "/analytics", label: "Analytics", icon: BarChart },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <motion.aside
      initial={{ x: -280 }}
      animate={{ x: 0 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      className="fixed left-0 top-0 z-50 w-64 h-screen bg-true-black border-r border-glow-border glass flex flex-col"
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-8 border-b border-glow-border">
        <div className="relative">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-neon-green to-neon-cyan flex items-center justify-center">
            <span className="text-true-black font-bold text-lg">A</span>
          </div>
          <motion.div
            className="absolute -bottom-1 -right-1 w-3 h-3 rounded-full bg-neon-green border-2 border-true-black"
            animate={{ boxShadow: ["0 0 0 0 rgba(0, 255, 102, 0.7)", "0 0 0 8px rgba(0, 255, 102, 0)", "0 0 0 0 rgba(0, 255, 102, 0.7)"] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
        </div>
        <span className="text-xl font-bold text-white tracking-tight">AlphaTradePro</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
        {navItems.map((item, index) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 ${
                isActive
                  ? "bg-gradient-to-r from-neon-cyan/10 to-neon-purple/10 border-l-4 border-neon-cyan text-white shadow-glow-cyan"
                  : "text-text-secondary hover:text-white hover:bg-card-bg hover:border-l-4 hover:border-neon-cyan/30"
              } group`}
            >
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: index * 0.05 }}
                className="w-5 h-5 flex-shrink-0"
              >
                <Icon className="w-5 h-5" strokeWidth={2.5} />
              </motion.div>
              <span className="font-medium text-sm">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Bottom: Version & Logout */}
      <div className="p-4 border-t border-glow-border">
        <div className="flex items-center justify-between text-xs text-text-muted">
          <span>v2.0.0 Phase 2</span>
          <span className="flex items-center gap-1 text-neon-green">
            <span className="w-1.5 h-1.5 rounded-full bg-neon-green animate-pulse-glow" />
            LIVE
          </span>
        </div>
      </div>
    </motion.aside>
  );
}