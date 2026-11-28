"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Settings,
  Key,
  Bell,
  User,
  Save,
  Eye,
  EyeOff,
  CheckCircle,
  AlertCircle,
  Loader2,
  Shield,
  Globe,
  Smartphone,
  Mail,
  Zap,
  Trash2,
  Plus,
  ChevronDown,
  Copy,
  Check,
  Wifi,
  WifiOff,
  Database,
  Terminal,
  Box,
  CreditCard,
  Key as KeyIcon,
  User as UserIcon,
  RotateCcw,
  Download,
  Search,
  X,
  MoreHorizontal,
  Trash2 as Trash2Icon,
  Edit,
  ShieldCheck,
  ShieldAlert,
  UserPlus,
  Calendar,
  ArrowRight,
  ArrowLeft,
  LucideIcon,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { useMe } from "@/lib/hooks";
import { api } from "@/lib/api-client";

type Tab = "general" | "notifications";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("general");
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // Settings would be saved to backend
      await new Promise((resolve) => setTimeout(resolve, 1000));
      showToast("Settings saved successfully", "success");
    } catch {
      showToast("Failed to save settings", "error");
    } finally {
      setIsSaving(false);
    }
  };

  const tabs: { id: Tab; label: string; icon: LucideIcon }[] = [
    { id: "general", label: "General", icon: Settings },
    { id: "notifications", label: "Notifications", icon: Bell },
  ];

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="w-full lg:ml-64 min-h-screen flex flex-col">
        <Header />

        <main className="flex-1 p-4 md:p-8 lg:p-10 pt-20 lg:pt-24 space-y-8 max-w-5xl mx-auto w-full">
          {/* Page Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="flex items-center justify-between flex-wrap gap-4"
          >
            <div className="flex items-center gap-3">
              <Settings className="w-8 h-8 text-neon-purple drop-shadow-[0_0_10px_rgba(168,85,247,0.6)]" strokeWidth={2.5} />
              <div>
                <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight">Platform Settings</h1>
                <p className="text-text-secondary">Configure your trading platform preferences</p>
              </div>
            </div>
            <motion.button
              onClick={handleSave}
              disabled={isSaving}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-neon-green to-neon-cyan text-true-black font-bold disabled:opacity-50 hover:opacity-90 transition-opacity shadow-glow-green"
            >
              <Save className="w-4 h-4" strokeWidth={2.5} />
              <span>{isSaving ? "Saving..." : "Save All Settings"}</span>
            </motion.button>
          </motion.div>

          {/* Toast Notification */}
          {toast && (
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
              className={`fixed top-6 right-6 px-6 py-4 rounded-xl border text-white font-medium z-50 shadow-lg ${
                toast.type === "success"
                  ? "bg-neon-green/20 border-neon-green/50 text-neon-green shadow-[0_0_20px_rgba(0,255,102,0.3)]"
                  : "bg-neon-red/20 border-neon-red/50 text-neon-red shadow-[0_0_20px_rgba(255,0,60,0.3)]"
              }`}
            >
              <div className="flex items-center gap-2">
                {toast.type === "success" ? <CheckCircle className="w-5 h-5" strokeWidth={2.5} /> : <AlertCircle className="w-5 h-5" strokeWidth={2.5} />}
                <span>{toast.message}</span>
              </div>
            </motion.div>
          )}

          {/* Tabs */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass rounded-2xl border border-glow-border overflow-hidden"
          >
            {/* Tab Navigation */}
            <div className="flex border-b border-glow-border bg-card-bg/30 overflow-x-auto">
              {tabs.map((tab) => (
                <motion.button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  whileHover={{ backgroundColor: "rgba(255,255,255,0.03)" }}
                  whileTap={{ scale: 0.98 }}
                  className={`flex items-center gap-2 px-6 py-4 text-sm font-medium transition-colors relative whitespace-nowrap ${
                    activeTab === tab.id
                      ? "text-white border-b-2 border-neon-cyan"
                      : "text-text-muted hover:text-white"
                  }`}
                >
                  <tab.icon className="w-4 h-4" strokeWidth={2.5} />
                  {tab.label}
                  {activeTab === tab.id && (
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: "100%" }}
                      className="absolute bottom-0 left-0 h-0.5 bg-neon-cyan"
                    />
                  )}
                </motion.button>
              ))}
            </div>

            {/* Tab Content */}
            <div className="p-4 md:p-6">
              {/* General Tab */}
              {activeTab === "general" && <GeneralSettingsTab />}
            </div>
          </motion.div>
        </main>
      </div>
    </div>
  );
}

function GeneralSettingsTab() {
  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-white mb-4">General Preferences</h3>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <SettingGroup title="Trading Preferences" items={[
          <SettingItem label="Default Order Type" type="select" options={["MARKET", "LIMIT", "SL-M", "SL-L"]} defaultValue="MARKET" />,
          <SettingItem label="Default Product Type" type="select" options={["MIS", "CNC", "NRML"]} defaultValue="MIS" />,
          <SettingItem label="Default Exchange" type="select" options={["NSE", "BSE", "NSE_FO"]} defaultValue="NSE" />,
          <SettingItem label="Chart Timeframe" type="select" options={["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"]} defaultValue="15m" />,
        ]} />
        
        <SettingGroup title="Display & Theme" items={[
          <SettingItem label="Theme" type="select" options={["Dark (OLED)", "Dark", "Light", "System"]} defaultValue="Dark (OLED)" />,
          <SettingItem label="Color Scheme" type="select" options={["Neon (Default)", "Classic", "High Contrast"]} defaultValue="Neon (Default)" />,
          <SettingItem label="Show PnL in Header" type="toggle" defaultChecked={true} />,
          <SettingItem label="Compact Mode" type="toggle" defaultChecked={false} />,
        ]} />
      </div>

      <div className="pt-6 border-t border-glow-border">
        <h3 className="text-lg font-semibold text-white mb-4">Account</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <SettingItem label="Trading Name" type="input" placeholder="Enter display name" defaultValue="AlphaTrader" />,
          <SettingItem label="Email" type="input" placeholder="Email for notifications" defaultValue="trader@example.com" />,
        </div>
      </div>
    </div>
  );
}

}
