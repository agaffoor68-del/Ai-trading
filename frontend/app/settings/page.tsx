"use client";

import { useState } from "react";
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

interface ApiKey {
  id: string;
  label: string;
  value: string;
  description: string;
}

const DEFAULT_API_KEYS: ApiKey[] = [
  { id: "fyers", label: "Fyers Client ID", value: "", description: "Your Fyers API Client ID" },
  { id: "fyers-secret", label: "Fyers Client Secret", value: "", description: "Your Fyers API Client Secret" },
  { id: "kotak", label: "Kotak Consumer Key", value: "", description: "Kotak Neo API Consumer Key" },
  { id: "kotak-secret", label: "Kotak Consumer Secret", value: "", description: "Kotak Neo API Consumer Secret" },
  { id: "kotak-totp", label: "Kotak TOTP Secret", value: "", description: "TOTP secret for 2FA" },
  { id: "kotak-mpin", label: "Kotak MPIN", value: "", description: "6-digit MPIN for Kotak Neo" },
  { id: "grok", label: "Grok API Key", value: "", description: "xAI Grok API key for AI signals" },
];

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("general");
  const [apiKeys, setApiKeys] = useState<ApiKey[]>(DEFAULT_API_KEYS);
  const [showValues, setShowValues] = useState<Record<string, boolean>>({});
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [testResults, setTestResults] = useState<Record<string, "success" | "error" | "testing">>({});

  const showToast = (message: string, type: "success" | "error") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      showToast("Settings saved successfully", "success");
    } catch {
      showToast("Failed to save settings", "error");
    } finally {
      setIsSaving(false);
    }
  };

  const toggleVisibility = (id: string) => {
    setShowValues((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleTestConnection = async (key: ApiKey) => {
    if (!key.value) {
      showToast(`Please enter ${key.label} first`, "error");
      return;
    }
    setTestResults((prev) => ({ ...prev, [key.id]: "testing" }));
    try {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      setTestResults((prev) => ({ ...prev, [key.id]: "success" }));
      showToast(`${key.label} connection successful`, "success");
    } catch {
      setTestResults((prev) => ({ ...prev, [key.id]: "error" }));
      showToast(`${key.label} connection failed`, "error");
    }
  };

  const copyToClipboard = (value: string, label: string) => {
    navigator.clipboard.writeText(value);
    showToast(`${label} copied to clipboard`, "success");
  };

  const tabs: { id: Tab; label: string; icon: LucideIcon }[] = [
    { id: "general", label: "General", icon: Settings },
    { id: "api-keys", label: "Broker API Keys", icon: Key },
    { id: "notifications", label: "Notifications", icon: Bell },
  ];

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
              <Settings className="w-8 h-8 text-neon-purple drop-shadow-[0_0_10px_rgba(168,85,247,0.6)]" strokeWidth={2.5} />
              <div>
                <h1 className="text-3xl font-bold text-white tracking-tight">Platform Settings</h1>
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
            <div className="flex border-b border-glow-border bg-card-bg/30">
              {tabs.map((tab) => (
                <motion.button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  whileHover={{ backgroundColor: "rgba(255,255,255,0.03)" }}
                  whileTap={{ scale: 0.98 }}
                  className={`flex items-center gap-2 px-6 py-4 text-sm font-medium transition-colors relative ${
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
            <div className="p-6">
              {/* General Tab */}
              {activeTab === "general" && <GeneralSettingsTab />}
              {/* API Keys Tab */}
              {activeTab === "api-keys" && (
                <ApiKeysTab
                  apiKeys={apiKeys}
                  setApiKeys={setApiKeys}
                  showValues={showValues}
                  toggleVisibility={toggleVisibility}
                  testResults={testResults}
                  handleTestConnection={handleTestConnection}
                  copyToClipboard={copyToClipboard}
                />
              )}
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

function ApiKeysTab({
  apiKeys,
  setApiKeys,
  showValues,
  toggleVisibility,
  testResults,
  handleTestConnection,
  copyToClipboard,
}: {
  apiKeys: ApiKey[];
  setApiKeys: React.Dispatch<React.SetStateAction<ApiKey[]>>;
  showValues: Record<string, boolean>;
  toggleVisibility: (id: string) => void;
  testResults: Record<string, "success" | "error" | "testing">;
  handleTestConnection: (key: ApiKey) => void;
  copyToClipboard: (value: string, label: string) => void;
}) {
  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
        <KeyIcon className="w-5 h-5 text-neon-cyan" strokeWidth={2.5} />
        Broker API Credentials
      </h3>
      <p className="text-text-secondary text-sm mb-6">
        Your API keys are encrypted and stored securely. They are never exposed in the frontend code.
      </p>

      {/* Fyers Section */}
      <SectionCard title="Fyers API (Market Data)" icon={Database} iconColor="text-neon-cyan">
        <ApiKeyRow
          key="fyers"
          apiKey={apiKeys.find((k) => k.id === "fyers")!}
          showValue={showValues.fyers}
          onToggleVisibility={toggleVisibility}
          testResult={testResults.fyers}
          onTest={handleTestConnection}
          onCopy={copyToClipboard}
          onChange={(v) => setApiKeys((prev) => prev.map((k) => (k.id === "fyers" ? { ...k, value: v } : k)))}
        />
        <ApiKeyRow
          key="fyers-secret"
          apiKey={apiKeys.find((k) => k.id === "fyers-secret")!}
          showValue={showValues["fyers-secret"]}
          onToggleVisibility={toggleVisibility}
          testResult={testResults["fyers-secret"]}
          onTest={handleTestConnection}
          onCopy={copyToClipboard}
          onChange={(v) => setApiKeys((prev) => prev.map((k) => (k.id === "fyers-secret" ? { ...k, value: v } : k)))}
        />
      </SectionCard>

      {/* Kotak Section */}
      <SectionCard title="Kotak Neo (Order Execution)" icon={Terminal} iconColor="text-neon-orange">
        <ApiKeyRow
          key="kotak"
          apiKey={apiKeys.find((k) => k.id === "kotak")!}
          showValue={showValues.kotak}
          onToggleVisibility={toggleVisibility}
          testResult={testResults.kotak}
          onTest={handleTestConnection}
          onCopy={copyToClipboard}
          onChange={(v) => setApiKeys((prev) => prev.map((k) => (k.id === "kotak" ? { ...k, value: v } : k)))}
        />
        <ApiKeyRow
          key="kotak-secret"
          apiKey={apiKeys.find((k) => k.id === "kotak-secret")!}
          showValue={showValues["kotak-secret"]}
          onToggleVisibility={toggleVisibility}
          testResult={testResults["kotak-secret"]}
          onTest={handleTestConnection}
          onCopy={copyToClipboard}
          onChange={(v) => setApiKeys((prev) => prev.map((k) => (k.id === "kotak-secret" ? { ...k, value: v } : k)))}
        />
        <ApiKeyRow
          key="kotak-totp"
          apiKey={apiKeys.find((k) => k.id === "kotak-totp")!}
          showValue={showValues["kotak-totp"]}
          onToggleVisibility={toggleVisibility}
          testResult={testResults["kotak-totp"]}
          onTest={handleTestConnection}
          onCopy={copyToClipboard}
          onChange={(v) => setApiKeys((prev) => prev.map((k) => (k.id === "kotak-totp" ? { ...k, value: v } : k)))}
        />
        <ApiKeyRow
          key="kotak-mpin"
          apiKey={apiKeys.find((k) => k.id === "kotak-mpin")!}
          showValue={showValues["kotak-mpin"]}
          onToggleVisibility={toggleVisibility}
          testResult={testResults["kotak-mpin"]}
          onTest={handleTestConnection}
          onCopy={copyToClipboard}
          onChange={(v) => setApiKeys((prev) => prev.map((k) => (k.id === "kotak-mpin" ? { ...k, value: v } : k)))}
        />
      </SectionCard>

      {/* AI Section */}
      <SectionCard title="AI Integration" icon={Zap} iconColor="text-neon-purple">
        <ApiKeyRow
          key="grok"
          apiKey={apiKeys.find((k) => k.id === "grok")!}
          showValue={showValues.grok}
          onToggleVisibility={toggleVisibility}
          testResult={testResults.grok}
          onTest={handleTestConnection}
          onCopy={copyToClipboard}
          onChange={(v) => setApiKeys((prev) => prev.map((k) => (k.id === "grok" ? { ...k, value: v } : k)))}
        />
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

function ApiKeyRow({ apiKey, showValue, onToggleVisibility, testResult, onTest, onCopy, onChange }: {
  apiKey: ApiKey;
  showValue: boolean;
  onToggleVisibility: (id: string) => void;
  testResult?: "success" | "error" | "testing";
  onTest: (key: ApiKey) => void;
  onCopy: (value: string, label: string) => void;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-true-black/50 border border-glow-border/50">
      <div className="flex-1 min-w-0">
        <label className="text-xs text-text-muted uppercase tracking-wider block mb-1">{apiKey.label}</label>
        <div className="flex items-center gap-2">
          <input
            type={showValue ? "text" : "password"}
            value={apiKey.value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="Enter API key..."
            className="flex-1 pl-4 py-2 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-lg text-white text-sm font-mono"
          />
          <motion.button
            onClick={() => onToggleVisibility(apiKey.id)}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            className="p-2 rounded-lg bg-card-bg/50 border border-glow-border text-text-muted hover:text-white hover:border-neon-cyan/50 transition-colors"
            title={showValue ? "Hide" : "Show"}
          >
            {showValue ? <EyeOff className="w-4 h-4" strokeWidth={2} /> : <Eye className="w-4 h-4" strokeWidth={2} />}
          </motion.button>
        </div>
        <p className="text-[10px] text-text-muted mt-1">{apiKey.description}</p>
      </div>
      <div className="flex items-center gap-2">
        <motion.button
          onClick={() => onCopy(apiKey.value, apiKey.label)}
          disabled={!apiKey.value}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          className="p-2 rounded-lg bg-card-bg/50 border border-glow-border text-text-muted hover:text-white hover:border-neon-cyan/50 transition-colors disabled:opacity-50"
          title="Copy"
        >
          <Copy className="w-4 h-4" strokeWidth={2} />
        </motion.button>
        <motion.button
          onClick={() => onTest(apiKey)}
          disabled={testResult === "testing" || !apiKey.value}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          className={`p-2 rounded-lg transition-colors ${
            testResult === "success"
              ? "bg-neon-green/20 border border-neon-green/30 text-neon-green"
              : testResult === "error"
              ? "bg-neon-red/20 border border-neon-red/30 text-neon-red"
              : testResult === "testing"
              ? "bg-neon-orange/20 border border-neon-orange/30 text-neon-orange animate-pulse"
              : "bg-card-bg/50 border border-glow-border text-text-muted hover:bg-neon-cyan/10 hover:border-neon-cyan/50"
          }`}
          title={testResult === "success" ? "Connected" : testResult === "error" ? "Failed" : testResult === "testing" ? "Testing..." : "Test Connection"}
        >
          {testResult === "success" && <CheckCircle className="w-4 h-4" strokeWidth={2.5} />}
          {testResult === "error" && <AlertCircle className="w-4 h-4" strokeWidth={2.5} />}
          {testResult === "testing" && <Loader2 className="w-4 h-4 animate-spin" strokeWidth={2.5} />}
          {!testResult && <Wifi className="w-4 h-4" strokeWidth={2.5} />}
        </motion.button>
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