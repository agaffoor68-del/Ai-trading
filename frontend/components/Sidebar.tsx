"use client";

import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  TrendingUp,
  List,
  Brain,
  ShoppingBag,
  Briefcase,
  FlaskConical,
  GitBranch,
  RotateCcw,
  BarChart,
  Link as LinkIcon,
  Shield,
  Settings,
  Users,
  Key,
  ChevronDown,
  ChevronUp,
  X,
  Menu,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, createContext, useContext, ReactNode } from "react";

// Mock user with ADMIN role
const user = { role: "ADMIN" as "ADMIN" | "USER" };

const navGroups = [
  {
    label: "MAIN DESK",
    items: [
      { href: "/", label: "Overview", icon: LayoutDashboard },
      { href: "/market-watch", label: "Market Watch", icon: TrendingUp },
      { href: "/option-chain", label: "Option Chain", icon: List },
      { href: "/ai-signals", label: "AI Signals", icon: Brain },
    ],
  },
  {
    label: "TRADING",
    items: [
      { href: "/order-ticket", label: "Order Ticket", icon: ShoppingBag },
      { href: "/positions", label: "Positions", icon: Briefcase },
      { href: "/paper-trading", label: "Paper Trading", icon: FlaskConical },
    ],
  },
  {
    label: "QUANT",
    items: [
      { href: "/strategies", label: "Strategies", icon: GitBranch },
      { href: "/backtest", label: "Backtest", icon: RotateCcw },
      { href: "/analytics", label: "Analytics", icon: BarChart },
    ],
  },
  {
    label: "SYSTEM",
    items: [
      { href: "/broker-connect", label: "Broker Connect", icon: LinkIcon },
      { href: "/risk-management", label: "Risk Management", icon: Shield },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
  {
    label: "ADMIN",
    items: [
      { href: "/admin", label: "Admin Panel", icon: Users },
    ],
    adminOnly: true,
  },
];

interface SidebarContextType {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  toggle: () => void;
}

const SidebarContext = createContext<SidebarContextType | undefined>(undefined);

export function useSidebar() {
  const context = useContext(SidebarContext);
  if (!context) {
    throw new Error("useSidebar must be used within a SidebarProvider");
  }
  return context;
}

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <SidebarContext.Provider value={{ isOpen, setIsOpen, toggle: () => setIsOpen(!isOpen) }}>
      {children}
    </SidebarContext.Provider>
  );
}

function SidebarContent() {
  const pathname = usePathname();
  const [collapsedGroups, setCollapsedGroups] = useState<string[]>([]);
  const { isOpen, setIsOpen } = useSidebar();

  const toggleGroup = (label: string) => {
    setCollapsedGroups((prev) =>
      prev.includes(label) ? prev.filter((g) => g !== label) : [...prev, label]
    );
  };

  return (
    <>
      {/* Backdrop */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
            onClick={() => setIsOpen(false)}
            aria-hidden="true"
          />
        )}
      </AnimatePresence>

      {/* Sidebar Drawer */}
      <AnimatePresence>
        <motion.aside
          initial={{ x: -280 }}
          animate={{ x: isOpen ? 0 : -280 }}
          exit={{ x: -280 }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
          className="fixed left-0 top-0 z-50 w-64 h-screen bg-true-black border-r border-glow-border glass flex flex-col lg:translate-x-0 lg:static lg:z-50"
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

          {/* Navigation Groups */}
          <nav className="flex-1 px-4 py-4 space-y-4 overflow-y-auto">
            {navGroups.map((group, groupIndex) => {
              // Admin-only check
              if (group.adminOnly && user.role !== "ADMIN") {
                return null;
              }

              const isCollapsed = collapsedGroups.includes(group.label);

              return (
                <motion.div
                  key={group.label}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: groupIndex * 0.08 }}
                >
                  {/* Group Header */}
                  <button
                    onClick={() => toggleGroup(group.label)}
                    className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold uppercase tracking-wider text-text-muted hover:text-white transition-colors"
                  >
                    <span>{group.label}</span>
                    <motion.span
                      animate={{ rotate: isCollapsed ? -90 : 0 }}
                      transition={{ type: "spring", stiffness: 300, damping: 25 }}
                    >
                      <ChevronDown className="w-4 h-4" strokeWidth={2.5} />
                    </motion.span>
                  </button>

                  {/* Group Items */}
                  <motion.div
                    initial={false}
                    animate={{ height: isCollapsed ? 0 : "auto", opacity: isCollapsed ? 0 : 1 }}
                    transition={{ duration: 0.2, ease: "easeInOut" }}
                    className="overflow-hidden space-y-1"
                  >
                    {group.items.map((item, itemIndex) => {
                      const Icon = item.icon;
                      const isActive = pathname === item.href;
                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          onClick={() => setIsOpen(false)}
                          className={`flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all duration-300 ${
                            isActive
                              ? "bg-gradient-to-r from-neon-cyan/10 to-neon-purple/10 border-l-4 border-neon-cyan text-white shadow-glow-cyan"
                              : "text-text-secondary hover:text-white hover:bg-card-bg hover:border-l-4 hover:border-neon-cyan/30"
                          } group`}
                        >
                          <motion.div
                            initial={{ scale: 0.8, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            transition={{ delay: groupIndex * 0.08 + itemIndex * 0.03 }}
                            className="w-5 h-5 flex-shrink-0"
                          >
                            <Icon className="w-5 h-5" strokeWidth={2.5} />
                          </motion.div>
                          <span className="font-medium text-sm">{item.label}</span>
                        </Link>
                      );
                    })}
                  </motion.div>
                </motion.div>
              );
            })}
          </nav>

          {/* Bottom: Version & Status */}
          <div className="p-4 border-t border-glow-border">
            <div className="flex items-center justify-between text-xs text-text-muted">
              <span>v2.0.0 Phase 2</span>
              <span className="flex items-center gap-1 text-neon-green">
                <span className="w-1.5 h-1.5 rounded-full bg-neon-green animate-pulse-glow" />
                LIVE
              </span>
            </div>
            <div className="mt-3 pt-3 border-t border-glow-border flex items-center gap-2 text-xs text-text-muted">
              <Key className="w-3.5 h-3.5" strokeWidth={2.5} />
              <span>ADMIN MODE</span>
            </div>
          </div>
        </motion.aside>
      </AnimatePresence>
    </>
  );
}

export function Sidebar() {
  return <SidebarContent />;
}