"use client";

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  ShieldAlert,
  Shield,
  Trash2,
  AlertCircle,
  CheckCircle,
  Settings,
  Save,
  RotateCcw,
  Bell,
  ToggleLeft,
  ToggleRight,
  Zap,
  DollarSign,
  Hash,
  Percent,
  AlertTriangle,
  Lock,
  Unlock,
  RefreshCw,
  Layers,
  Target,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";

interface RiskSettings {
  maxDailyLoss: number;
  maxTradesPerDay: number;
  defaultStopLoss: number;
  defaultTarget: number;
  maxPositionSize: number;
  maxOpenPositions: number;
  killSwitchEnabled: boolean;
  telegramAlerts: boolean;
  emailAlerts: boolean;
  autoSquareOff: boolean;
}

const DEFAULT_SETTINGS: RiskSettings = {
  maxDailyLoss: 50000,
  maxTradesPerDay: 20,
  defaultStopLoss: 1.5,
  defaultTarget: 3.0,
  maxPositionSize: 2,
  maxOpenPositions: 5,
  killSwitchEnabled: false,
  telegramAlerts: true,
  emailAlerts: false,
  autoSquareOff: true,
};

export default function RiskManagementPage() {
  const [settings, setSettings] = useState<RiskSettings>(DEFAULT_SETTINGS);
  const [isSaving, setIsSaving] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [killSwitchConfirm, setKillSwitchConfirm] = useState(false);

  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // await api.saveRiskSettings(settings);
      await new Promise((resolve) => setTimeout(resolve, 1000));
      showToast("Risk settings saved successfully", "success");
    } catch {
      showToast("Failed to save settings", "error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    if (confirm("Reset all risk settings to defaults?")) {
      setSettings(DEFAULT_SETTINGS);
      showToast("Settings reset to defaults", "success");
    }
  };

  const toggleKillSwitch = () => {
    if (!settings.killSwitchEnabled) {
      setKillSwitchConfirm(true);
    } else {
      setSettings((prev) => ({ ...prev, killSwitchEnabled: false }));
      showToast("Kill Switch DEACTIVATED - Trading resumed", "success");
    }
  };

  const confirmKillSwitch = () => {
    setSettings((prev) => ({ ...prev, killSwitchEnabled: true }));
    setKillSwitchConfirm(false);
    showToast("⚠️ KILL SWITCH ACTIVATED - ALL TRADING HALTED", "error");
  };

  const riskRewardRatio = (settings.defaultTarget / settings.defaultStopLoss).toFixed(2);

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="ml-64 min-h-screen flex flex-col">
        <Header />

        <main className="flex-1 p-6 md:p-8 lg:p-10 pt-20 lg:pt-24 space-y-8 max-w-5xl mx-auto w-full">
          {/* Page Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <ShieldAlert className="w-8 h-8 text-neon-red drop-shadow-[0_0_10px_rgba(255,0,60,0.6)]" strokeWidth={2.5} />
              <div>
                <h1 className="text-3xl font-bold text-white tracking-tight">Risk Management</h1>
                <p className="text-text-secondary">Configure risk limits, position sizing, and emergency controls</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <motion.button
                onClick={handleReset}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-card-bg border border-glow-border hover:border-neon-orange/50 text-text-secondary font-medium transition-all glass"
              >
                <RotateCcw className="w-4 h-4" strokeWidth={2.5} />
                Reset Defaults
              </motion.button>
              <motion.button
                onClick={handleSave}
                disabled={isSaving}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-neon-green to-neon-cyan text-true-black font-bold disabled:opacity-50 hover:opacity-90 transition-opacity shadow-glow-green"
              >
                <Save className="w-4 h-4" strokeWidth={2.5} />
                <span>{isSaving ? "Saving..." : "Save Settings"}</span>
              </motion.button>
            </div>
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

          {/* Kill Switch Banner */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className={`relative glass rounded-2xl border-2 p-6 flex items-center justify-between ${
              settings.killSwitchEnabled
                ? "border-neon-red bg-neon-red/5 animate-pulse-glow"
                : "border-glow-border"
            }`}
          >
            <div className="flex items-center gap-4">
              <div className={`w-14 h-14 rounded-xl flex items-center justify-center ${
                settings.killSwitchEnabled
                  ? "bg-neon-red/20 text-neon-red animate-pulse"
                  : "bg-neon-green/20 text-neon-green"
              }`}>
                {settings.killSwitchEnabled ? (
                  <AlertTriangle className="w-7 h-7" strokeWidth={2.5} />
                ) : (
                  <Shield className="w-7 h-7" strokeWidth={2.5} />
                )}
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">{settings.killSwitchEnabled ? "KILL SWITCH ACTIVE" : "Kill Switch Armed"}</h2>
                <p className="text-text-secondary text-sm">
                  {settings.killSwitchEnabled
                    ? "All trading is halted. Positions will be squared off immediately."
                    : "Click to activate emergency kill switch and halt all trading."}
                </p>
              </div>
            </div>
            <motion.button
              onClick={toggleKillSwitch}
              disabled={killSwitchConfirm}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className={`flex items-center gap-2 px-6 py-3 rounded-xl font-bold text-lg transition-all ${
                settings.killSwitchEnabled
                  ? "bg-gradient-to-r from-neon-green to-neon-cyan text-true-black"
                  : "bg-neon-red/10 border border-neon-red/30 text-neon-red hover:bg-neon-red/20"
              }`}
            >
              {killSwitchConfirm ? (
                <>
                  <AlertTriangle className="w-5 h-5" strokeWidth={2.5} />
                  CONFIRM ACTIVATION
                </>
              ) : settings.killSwitchEnabled ? (
                <>
                  <Unlock className="w-5 h-5" strokeWidth={2.5} />
                  Deactivate
                </>
              ) : (
                <>
                  <Lock className="w-5 h-5" strokeWidth={2.5} />
                  Activate Kill Switch
                </>
              )}
            </motion.button>
          </motion.div>

          {/* Kill Switch Confirmation Modal */}
          {killSwitchConfirm && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
              onClick={() => setKillSwitchConfirm(false)}
            >
              <motion.div
                onClick={(e) => e.stopPropagation()}
                className="w-full max-w-md glass rounded-2xl border border-neon-red/50 bg-neon-red/5 p-6"
              >
                <div className="text-center mb-6">
                  <div className="w-16 h-16 rounded-full bg-neon-red/20 flex items-center justify-center mx-auto mb-4">
                    <AlertTriangle className="w-8 h-8 text-neon-red" strokeWidth={2.5} />
                  </div>
                  <h3 className="text-xl font-bold text-white mb-2">Activate Kill Switch?</h3>
                  <p className="text-text-secondary">
                    This will immediately halt ALL trading activity, cancel pending orders, 
                    and square off open positions. This action cannot be undone automatically.
                  </p>
                </div>
                <div className="flex gap-3">
                  <motion.button
                    onClick={() => setKillSwitchConfirm(false)}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="flex-1 py-3 rounded-xl bg-card-bg/50 border border-glow-border text-text-secondary hover:bg-card-bg hover:text-white transition-colors"
                  >
                    Cancel
                  </motion.button>
                  <motion.button
                    onClick={confirmKillSwitch}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="flex-1 py-3 rounded-xl bg-gradient-to-r from-neon-red to-neon-orange text-white font-bold hover:opacity-90 transition-opacity shadow-glow-red"
                  >
                    YES, ACTIVATE
                  </motion.button>
                </div>
              </motion.div>
            </motion.div>
          )}

          {/* Risk Limits */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass rounded-2xl border border-glow-border p-6"
          >
            <h2 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
              <Settings className="w-5 h-5 text-neon-cyan" strokeWidth={2.5} />
              Risk Limits
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <SettingInput
                label="Max Daily Loss (₹)"
                value={settings.maxDailyLoss}
                onChange={(v) => setSettings((prev) => ({ ...prev, maxDailyLoss: v }))}
                type="number"
                min={0}
                step={1000}
                icon={DollarSign}
                color="text-neon-red"
                help="Trading stops for the day if this loss is reached"
              />
              <SettingInput
                label="Max Trades Per Day"
                value={settings.maxTradesPerDay}
                onChange={(v) => setSettings((prev) => ({ ...prev, maxTradesPerDay: v }))}
                type="number"
                min={1}
                max={100}
                step={1}
                icon={Hash}
                color="text-neon-orange"
                help="Maximum number of trades allowed per session"
              />
              <SettingInput
                label="Max Open Positions"
                value={settings.maxOpenPositions}
                onChange={(v) => setSettings((prev) => ({ ...prev, maxOpenPositions: v }))}
                type="number"
                min={1}
                max={20}
                step={1}
                icon={Layers}
                color="text-neon-cyan"
                help="Maximum concurrent open positions"
              />
              <SettingInput
                label="Max Position Size (Lots)"
                value={settings.maxPositionSize}
                onChange={(v) => setSettings((prev) => ({ ...prev, maxPositionSize: v }))}
                type="number"
                min={1}
                max={50}
                step={1}
                icon={Hash}
                color="text-neon-purple"
                help="Maximum lots per single position"
              />
            </div>
          </motion.div>

          {/* Default Trade Parameters */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="glass rounded-2xl border border-glow-border p-6"
          >
            <h2 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
              <Zap className="w-5 h-5 text-neon-orange" strokeWidth={2.5} />
              Default Trade Parameters
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <SettingInput
                label="Default Stop Loss (%)"
                value={settings.defaultStopLoss}
                onChange={(v) => setSettings((prev) => ({ ...prev, defaultStopLoss: v }))}
                type="number"
                min={0.1}
                max={10}
                step={0.1}
                icon={ShieldAlert}
                color="text-neon-red"
                help="Default stop loss percentage for new orders"
              />
              <SettingInput
                label="Default Target (%)"
                value={settings.defaultTarget}
                onChange={(v) => setSettings((prev) => ({ ...prev, defaultTarget: v }))}
                type="number"
                min={0.1}
                max={20}
                step={0.1}
                icon={Target}
                color="text-neon-green"
                help="Default take profit percentage for new orders"
              />
            </div>

            <div className="mt-6 p-4 rounded-xl bg-neon-purple/5 border border-neon-purple/20 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-neon-purple/20 flex items-center justify-center">
                  <Zap className="w-5 h-5 text-neon-purple" strokeWidth={2.5} />
                </div>
                <div>
                  <p className="text-xs text-text-muted uppercase tracking-wider">Risk:Reward Ratio</p>
                  <p className="text-2xl font-bold text-neon-purple">1 : {riskRewardRatio}</p>
                </div>
              </div>
              <span className={`text-sm font-medium ${parseFloat(riskRewardRatio) >= 2 ? "text-neon-green" : parseFloat(riskRewardRatio) >= 1.5 ? "text-neon-orange" : "text-neon-red"}`}>
                {parseFloat(riskRewardRatio) >= 2 ? "Excellent" : parseFloat(riskRewardRatio) >= 1.5 ? "Good" : "Needs Improvement"}
              </span>
            </div>
          </motion.div>

          {/* Automation & Alerts */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass rounded-2xl border border-glow-border p-6"
          >
            <h2 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
              <Bell className="w-5 h-5 text-neon-cyan" strokeWidth={2.5} />
              Automation & Alerts
            </h2>

            <div className="space-y-4">
              <ToggleRow
                label="Auto Square-off at EOD"
                description="Automatically close all positions 15 minutes before market close"
                checked={settings.autoSquareOff}
                onChange={(v) => setSettings((prev) => ({ ...prev, autoSquareOff: v }))}
                icon={RotateCcw}
              />
              <ToggleRow
                label="Telegram Alerts"
                description="Receive trade notifications via Telegram bot"
                checked={settings.telegramAlerts}
                onChange={(v) => setSettings((prev) => ({ ...prev, telegramAlerts: v }))}
                icon={Bell}
              />
              <ToggleRow
                label="Email Alerts"
                description="Receive daily PnL summary and risk alerts via email"
                checked={settings.emailAlerts}
                onChange={(v) => setSettings((prev) => ({ ...prev, emailAlerts: v }))}
                icon={Mail}
              />
            </div>
          </motion.div>
        </main>
      </div>
    </div>
  );
}

function SettingInput({ label, value, onChange, type, min, max, step, icon: Icon, color, help }: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  type: string;
  min?: number;
  max?: number;
  step?: number;
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  color: string;
  help: string;
}) {
  return (
    <div className="p-4 rounded-xl bg-card-bg/30 border border-glow-border/50">
      <label className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider mb-2">
        <Icon className="w-3 h-3" strokeWidth={2.5} style={{ color: "currentColor" }} />
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        min={min}
        max={max}
        step={step}
        className={`w-full pl-4 py-3 bg-true-black border border-glow-border focus:border-${color.replace("text-", "neon-")} focus:outline-none rounded-xl text-white text-lg font-mono ${color}`}
      />
      <p className="text-[10px] text-text-muted mt-1">{help}</p>
    </div>
  );
}

function ToggleRow({ label, description, checked, onChange, icon: Icon }: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
}) {
  return (
    <div className="flex items-center justify-between px-4 py-3 rounded-xl bg-card-bg/30 border border-glow-border/50">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-true-black/50 flex items-center justify-center">
          <Icon className="w-5 h-5 text-text-muted" strokeWidth={2} />
        </div>
        <div>
          <p className="font-medium text-white">{label}</p>
          <p className="text-xs text-text-muted">{description}</p>
        </div>
      </div>
      <motion.button
        onClick={() => onChange(!checked)}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        className={`relative w-12 h-7 rounded-full transition-colors ${
          checked ? "bg-neon-green shadow-[0_0_10px_rgba(0,255,102,0.5)]" : "bg-card-bg border border-glow-border"
        }`}
      >
        <motion.div
          className="w-5 h-5 rounded-full bg-white shadow-lg"
          animate={{ x: checked ? 24 : 2 }}
          transition={{ type: "spring", stiffness: 500, damping: 30 }}
        />
      </motion.button>
    </div>
  );
}

// Import missing icons
