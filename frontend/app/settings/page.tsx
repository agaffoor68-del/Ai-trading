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

type Tab = "general" | "api-keys" | "notifications";

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
    { id: "api-keys", label: "Broker Config", icon: Key },
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
              {/* Broker Config Tab */}
              {activeTab === "api-keys" && <BrokerConfigTab />}
              {/* Notifications Tab */}
              {activeTab === "notifications" && <NotificationsTab />}
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

function BrokerConfigTab() {
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [showToast, setShowToast] = useState(false);

  const showToastMsg = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setShowToast(true);
    setTimeout(() => setShowToast(false), 4000);
  };

  // Fyers config state
  const [fyersConfig, setFyersConfig] = useState({
    clientId: "",
    clientSecret: "",
    redirectUri: "",
    isConnected: false,
    showSecret: false,
  });

  // Kotak config state
  const [kotakConfig, setKotakConfig] = useState({
    consumerKey: "",
    consumerSecret: "",
    totpSecret: "",
    mobileNumber: "",
    mpin: "",
    ucc: "",
    isConnected: false,
  });

  // Load status on mount
  useEffect(() => {
    const loadStatus = async () => {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com"}/api/fyers/status`);
        if (response.ok) {
          const data = await response.json();
          setFyersConfig(prev => ({ ...prev, isConnected: data.fyers?.connected && data.fyers?.valid }));
          setKotakConfig(prev => ({ ...prev, isConnected: data.kotak?.connected }));
        }
      } catch (err) {
        console.warn("Failed to load broker status:", err);
      }
    };
    loadStatus();
  }, []);

  const handleFyersSaveAndConnect = async () => {
    if (!fyersConfig.clientId.trim() || !fyersConfig.clientSecret.trim()) {
      showToastMsg("Please enter both Fyers Client ID and Secret Key", "error");
      return;
    }

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com"}/api/v1/fyers/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: fyersConfig.clientId.trim(),
          client_secret: fyersConfig.clientSecret.trim(),
        }),
        signal: AbortSignal.timeout(10000),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ message: "Failed" }));
        throw new Error(err.message || `HTTP ${response.status}`);
      }

      const data = await response.json();
      window.location.href = data.auth_url;
    } catch (err) {
      showToastMsg(err instanceof Error ? err.message : "Failed to connect Fyers", "error");
    }
  };

  const handleKotakSave = async () => {
    // Kotak credentials saved to backend admin panel
    showToastMsg("Kotak credentials should be configured in Admin Panel", "error");
  };

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
        <KeyIcon className="w-5 h-5 text-neon-cyan" strokeWidth={2.5} />
        Broker Configuration
      </h3>
      <p className="text-text-secondary text-sm mb-6">
        Configure your broker connections. Credentials are encrypted and stored securely on the backend.
        The frontend only initiates OAuth flows; sensitive secrets are never stored in the browser.
      </p>

      {/* Fyers Section */}
      <SectionCard title="Fyers API v3 (Market Data)" icon={Database} iconColor="text-neon-cyan">
        <div className="space-y-4">
          <ConfigRow
            label="Client ID"
            value={fyersConfig.clientId}
            onChange={(v) => setFyersConfig(prev => ({ ...prev, clientId: v }))}
            placeholder="Enter your Fyers Client ID"
            showSecret={fyersConfig.showSecret}
            onToggleSecret={() => setFyersConfig(prev => ({ ...prev, showSecret: !prev.showSecret }))}
          />
          <ConfigRow
            label="Client Secret"
            value={fyersConfig.clientSecret}
            onChange={(v) => setFyersConfig(prev => ({ ...prev, clientSecret: v }))}
            placeholder="Enter your Fyers Secret Key"
            showSecret={fyersConfig.showSecret}
            onToggleSecret={() => setFyersConfig(prev => ({ ...prev, showSecret: !prev.showSecret }))}
            isSecret
          />
          <ConfigRow
            label="Redirect URI"
            value={fyersConfig.redirectUri || `${process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com"}/api/v1/fyers/callback`}
            onChange={(v) => setFyersConfig(prev => ({ ...prev, redirectUri: v }))}
            placeholder="OAuth redirect URI"
            disabled
          />
          
          <div className="pt-4 border-t border-glow-border flex gap-3">
            {fyersConfig.isConnected ? (
              <motion.button
                disabled
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex-1 py-3 rounded-xl bg-gradient-to-r from-neon-green to-neon-cyan text-true-black font-bold cursor-not-allowed opacity-60 flex items-center justify-center gap-2"
              >
                <CheckCircle className="w-5 h-5" strokeWidth={2.5} />
                Fyers Connected
              </motion.button>
            ) : (
              <motion.button
                onClick={handleFyersSaveAndConnect}
                whileHover={{ scale: 1.02, boxShadow: "0 0 20px rgba(0, 240, 255, 0.3)" }}
                whileTap={{ scale: 0.98 }}
                className="flex-1 py-3 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black font-bold shadow-glow-cyan hover:shadow-glow-cyan/50 flex items-center justify-center gap-2"
              >
                <Save className="w-5 h-5" strokeWidth={2.5} />
                Save & Connect to Fyers
              </motion.button>
            )}
          </div>
          
          <p className="mt-4 text-center text-xs text-text-muted">
            Clicking "Save & Connect" will store credentials securely and redirect to Fyers OAuth for authorization.
          </p>
        </div>
      </SectionCard>

      {/* Kotak Section */}
      <SectionCard title="Kotak Neo (Order Execution)" icon={Terminal} iconColor="text-neon-orange">
        <div className="space-y-4">
          <ConfigRow
            label="Consumer Key"
            value={kotakConfig.consumerKey}
            onChange={(v) => setKotakConfig(prev => ({ ...prev, consumerKey: v }))}
            placeholder="Kotak Consumer Key"
            isSecret
          />
          <ConfigRow
            label="Consumer Secret"
            value={kotakConfig.consumerSecret}
            onChange={(v) => setKotakConfig(prev => ({ ...prev, consumerSecret: v }))}
            placeholder="Kotak Consumer Secret"
            isSecret
          />
          <ConfigRow
            label="TOTP Secret"
            value={kotakConfig.totpSecret}
            onChange={(v) => setKotakConfig(prev => ({ ...prev, totpSecret: v }))}
            placeholder="TOTP Secret for 2FA"
            isSecret
          />
          <ConfigRow
            label="Mobile Number"
            value={kotakConfig.mobileNumber}
            onChange={(v) => setKotakConfig(prev => ({ ...prev, mobileNumber: v }))}
            placeholder="Registered Mobile Number"
          />
          <ConfigRow
            label="MPIN"
            value={kotakConfig.mpin}
            onChange={(v) => setKotakConfig(prev => ({ ...prev, mpin: v }))}
            placeholder="6-digit MPIN"
            isSecret
          />
          <ConfigRow
            label="UCC (Optional)"
            value={kotakConfig.ucc}
            onChange={(v) => setKotakConfig(prev => ({ ...prev, ucc: v }))}
            placeholder="UCC"
          />
          
          <div className="pt-4 border-t border-glow-border flex gap-3">
            {kotakConfig.isConnected ? (
              <motion.button
                disabled
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="flex-1 py-3 rounded-xl bg-gradient-to-r from-neon-green to-neon-cyan text-true-black font-bold cursor-not-allowed opacity-60 flex items-center justify-center gap-2"
              >
                <CheckCircle className="w-5 h-5" strokeWidth={2.5} />
                Kotak Connected
              </motion.button>
            ) : (
              <motion.button
                onClick={handleKotakSave}
                whileHover={{ scale: 1.02, boxShadow: "0 0 20px rgba(249, 115, 22, 0.4)" }}
                whileTap={{ scale: 0.98 }}
                className="flex-1 py-3 rounded-xl bg-gradient-to-r from-neon-orange to-neon-red text-white font-bold shadow-glow-orange hover:shadow-glow-orange/50 flex items-center justify-center gap-2"
              >
                <Save className="w-5 h-5" strokeWidth={2.5} />
                Configure Kotak (via Admin Panel)
              </motion.button>
            )}
          </div>
          
          <p className="mt-4 text-center text-xs text-text-muted">
            Kotak Neo credentials are managed via the Admin Panel for security.
          </p>
        </div>
      </SectionCard>

      {/* AI Section */}
      <SectionCard title="AI Integration" icon={Zap} iconColor="text-neon-purple">
        <div className="space-y-4">
          <ConfigRow
            label="Grok API Key (xAI)"
            value=""
            onChange={() => {}}
            placeholder="xai-..."
            isSecret
            disabled
          />
          <p className="text-text-secondary text-sm">
            Grok API key is configured via environment variables on the backend.
          </p>
        </div>
      </SectionCard>
    </div>
  );
}

function NotificationsTab() {
  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-white mb-4">Notification Preferences</h3>
      
      <SectionCard title="Trade Alerts" icon={Zap} iconColor="text-neon-green">
        <NotificationToggle label="Order Filled" description="Notify when an order is executed" defaultChecked={true} />
        <NotificationToggle label="Order Rejected" description="Notify when an order is rejected" defaultChecked={true} />
        <NotificationToggle label="Position Opened" description="Notify when a new position is opened" defaultChecked={true} />
        <NotificationToggle label="Position Closed" description="Notify when a position is closed" defaultChecked={true} />
        <NotificationToggle label="Stop Loss Hit" description="Notify when SL is triggered" defaultChecked={true} />
        <NotificationToggle label="Target Hit" description="Notify when TP is triggered" defaultChecked={true} />
      </SectionCard>

      <SectionCard title="Risk Alerts" icon={Shield} iconColor="text-neon-red">
        <NotificationToggle label="Daily Loss Limit" description="Alert when approaching daily loss limit" defaultChecked={true} />
        <NotificationToggle label="Margin Shortfall" description="Alert when margin falls below threshold" defaultChecked={true} />
        <NotificationToggle label="Position Size Limit" description="Alert when position exceeds max size" defaultChecked={true} />
        <NotificationToggle label="Kill Switch Activated" description="Critical alert when kill switch triggers" defaultChecked={true} />
      </SectionCard>

      <SectionCard title="Daily Summary" icon={Mail} iconColor="text-neon-cyan">
        <NotificationToggle label="End of Day PnL" description="Receive daily PnL summary at market close" defaultChecked={true} />
        <NotificationToggle label="Weekly Performance" description="Weekly performance report every Monday" defaultChecked={false} />
        <NotificationToggle label="Monthly Report" description="Comprehensive monthly analytics report" defaultChecked={false} />
      </SectionCard>

      <SectionCard title="Delivery Channels" icon={Smartphone} iconColor="text-neon-purple">
        <ChannelToggle label="Telegram" description="Send alerts via Telegram bot" icon={Smartphone} defaultChecked={true} />
        <ChannelToggle label="Email" description="Send alerts via email" icon={Mail} defaultChecked={true} />
        <ChannelToggle label="In-App" description="Show notifications in the platform" icon={Bell} defaultChecked={true} />
        <ChannelToggle label="Push Notification" description="Browser push notifications" icon={Wifi} defaultChecked={false} />
      </SectionCard>
    </div>
  );
}

// Helper Components
function SettingGroup({ title, items }: { title: string; items: React.ReactNode[] }) {
  return (
    <div className="p-4 rounded-xl bg-card-bg/30 border border-glow-border/50">
      <h4 className="text-sm font-semibold text-white mb-4">{title}</h4>
      <div className="space-y-4">{items}</div>
    </div>
  );
}

function SettingItem({ label, type, options, defaultValue, defaultChecked, placeholder }: {
  label: string;
  type: "select" | "toggle" | "input";
  options?: string[];
  defaultValue?: string;
  defaultChecked?: boolean;
  placeholder?: string;
}) {
  const [value, setValue] = useState(defaultValue || "");
  const [checked, setChecked] = useState(defaultChecked || false);

  if (type === "select") {
    return (
      <div>
        <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">{label}</label>
        <select
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="w-full pl-4 pr-10 py-2.5 bg-true-black border border-glow-border focus:border-neon-cyan focus:outline-none rounded-lg text-white cursor-pointer appearance-none"
        >
          {options?.map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      </div>
    );
  }

  if (type === "toggle") {
    return (
      <div className="flex items-center justify-between">
        <label className="text-sm text-text-secondary">{label}</label>
        <motion.button
          onClick={() => setChecked(!checked)}
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

  return (
    <div>
      <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        defaultValue={defaultValue}
        className="w-full pl-4 py-2.5 bg-true-black border border-glow-border focus:border-neon-cyan focus:outline-none rounded-lg text-white"
      />
    </div>
  );
}

function SectionCard({ title, icon: Icon, iconColor, children }: { title: string; icon: LucideIcon; iconColor: string; children: React.ReactNode }) {
  return (
    <div className="p-5 rounded-xl bg-card-bg/30 border border-glow-border/50">
      <h4 className="flex items-center gap-2 text-sm font-semibold text-white mb-4">
        <Icon className="w-5 h-5" strokeWidth={2.5} style={{ color: "currentColor" }} />
        {title}
      </h4>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function ConfigRow({ 
  label, 
  value, 
  onChange, 
  placeholder, 
  showSecret = false, 
  onToggleSecret, 
  isSecret = false, 
  disabled = false 
}: { 
  label: string; 
  value: string; 
  onChange: (v: string) => void; 
  placeholder: string; 
  showSecret?: boolean; 
  onToggleSecret?: () => void; 
  isSecret?: boolean; 
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-true-black/50 border border-glow-border/50">
      <div className="flex-1 min-w-0">
        <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">{label}</label>
        <div className="flex items-center gap-2">
          <input
            type={(showSecret || !isSecret) ? "text" : "password"}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            disabled={disabled}
            className="flex-1 pl-4 py-2 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-lg text-white text-sm font-mono disabled:opacity-50"
          />
          {(isSecret || showSecret !== undefined) && onToggleSecret && (
            <motion.button
              onClick={onToggleSecret}
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
              className="p-2 rounded-lg bg-card-bg/50 border border-glow-border text-text-muted hover:text-white hover:border-neon-cyan/50 transition-colors"
              title={showSecret ? "Hide" : "Show"}
            >
              {showSecret ? <EyeOff className="w-4 h-4" strokeWidth={2} /> : <Eye className="w-4 h-4" strokeWidth={2} />}
            </motion.button>
          )}
        </div>
      </div>
    </div>
  );
}

function NotificationToggle({ label, description, defaultChecked }: { label: string; description: string; defaultChecked: boolean }) {
  const [checked, setChecked] = useState(defaultChecked);
  return (
    <div className="flex items-center justify-between px-4 py-3 rounded-lg bg-true-black/50 border border-glow-border/50">
      <div className="flex-1">
        <p className="font-medium text-white">{label}</p>
        <p className="text-xs text-text-muted">{description}</p>
      </div>
      <motion.button
        onClick={() => setChecked(!checked)}
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

function ChannelToggle({ label, description, icon: Icon, defaultChecked }: { label: string; description: string; icon: LucideIcon; defaultChecked: boolean }) {
  const [checked, setChecked] = useState(defaultChecked);
  return (
    <div className="flex items-center justify-between px-4 py-3 rounded-lg bg-true-black/50 border border-glow-border/50">
      <div className="flex items-center gap-3 flex-1">
        <div className="w-10 h-10 rounded-lg bg-true-black/50 flex items-center justify-center">
          <Icon className="w-5 h-5 text-text-muted" strokeWidth={2} />
        </div>
        <div>
          <p className="font-medium text-white">{label}</p>
          <p className="text-xs text-text-muted">{description}</p>
        </div>
      </div>
      <motion.button
        onClick={() => setChecked(!checked)}
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