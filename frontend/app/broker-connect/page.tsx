"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Link,
  Database,
  Zap,
  ExternalLink,
  Loader2,
  CheckCircle,
  AlertCircle,
  Info,
  Shield,
  RefreshCw,
  RotateCcw,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { api } from "@/lib/api";

interface BrokerStatus {
  fyers: {
    connected: boolean;
    tokenExpiresAt: string | null;
  };
  kotak: {
    connected: boolean;
    tokenExpiresAt: string | null;
  };
}

interface FyersLoginResponse {
  authorization_url: string;
  state: string;
  client_id: string;
  message: string;
}

export default function BrokerConnectPage() {
  const [status, setStatus] = useState<BrokerStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await api.getBrokerStatus();
      setStatus(data);
      setError(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch broker status";
      setError(errorMessage);
      setStatus({
        fyers: { connected: false, tokenExpiresAt: null },
        kotak: { connected: false, tokenExpiresAt: null },
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleFyersConnect = async () => {
    try {
      setIsLoading(true);
      const data = await api.getFyersLoginUrl();
      if (data.authorization_url) {
        window.location.href = data.authorization_url;
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to get Fyers login URL";
      alert(errorMessage);
      setIsLoading(false);
    }
  };

  const handleKotakConnect = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com"}/api/v1/kotak/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: AbortSignal.timeout(10000),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${response.status}`);
      }

      const data = await response.json();
      if (data.redirect_url) {
        window.location.href = data.redirect_url;
      } else {
        alert("Kotak login initiated. Check the backend logs.");
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to initiate Kotak login";
      alert(errorMessage);
    }
  };

  const formatTime = (isoString: string | null) => {
    if (!isoString) return "Never";
    try {
      return new Date(isoString).toLocaleString();
    } catch {
      return isoString;
    }
  };

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="ml-64 min-h-screen flex flex-col">
        <Header />

        <main className="flex-1 p-6 md:p-8 lg:p-10 pt-20 lg:pt-24 space-y-8 max-w-4xl mx-auto w-full">
          {/* Page Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <h1 className="text-3xl font-bold text-white tracking-tight flex items-center gap-3">
              <Link className="w-8 h-8 text-neon-cyan" strokeWidth={2.5} />
              Broker Connect
            </h1>
            <p className="text-text-secondary mt-1">Manage Fyers (Data) and Kotak Neo (Execution) connections</p>
          </motion.div>

          {/* Error Banner */}
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-3 px-4 py-3 rounded-xl bg-neon-red/10 border border-neon-red/30 text-neon-red glass"
            >
              <AlertCircle className="w-5 h-5 flex-shrink-0" strokeWidth={2.5} />
              <div>
                <p className="font-medium text-sm">Failed to load broker status</p>
                <p className="text-xs text-neon-red/80 mt-0.5">{error}</p>
              </div>
              <motion.button
                onClick={fetchStatus}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="ml-auto px-3 py-1.5 text-xs rounded-lg bg-neon-red/20 text-neon-red border border-neon-red/30 hover:bg-neon-red/30 transition-colors"
              >
                Retry
              </motion.button>
            </motion.div>
          )}

          {/* Broker Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Fyers Card */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="glass rounded-2xl border border-glow-border p-6 relative overflow-hidden group"
            >
              <div className="absolute -top-10 -right-10 w-40 h-40 rounded-full bg-neon-cyan/10 blur-3xl" />

              <div className="relative z-10 flex items-start justify-between mb-6">
                <div className="flex items-center gap-4">
                  <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-neon-cyan to-neon-purple flex items-center justify-center shadow-glow-cyan">
                    <Database className="w-7 h-7 text-true-black" strokeWidth={2.5} />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-white">Fyers API v3</h2>
                    <p className="text-sm text-text-muted">Market Data Provider</p>
                  </div>
                </div>

                {/* Status Badge */}
                <motion.div
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-full font-medium text-sm ${
                    status?.fyers.connected
                      ? "bg-neon-green/20 text-neon-green border border-neon-green/30"
                      : "bg-neon-red/20 text-neon-red border border-neon-red/30"
                  } glass`}
                >
                  {status?.fyers.connected ? (
                    <>
                      <span className="w-2 h-2 rounded-full bg-neon-green animate-pulse-glow" />
                      Connected
                    </>
                  ) : (
                    <>
                      <span className="w-2 h-2 rounded-full bg-neon-red" />
                      Disconnected
                    </>
                  )}
                </motion.div>
              </div>

              {/* Connection Details */}
              {status?.fyers.connected && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  className="space-y-2 mb-6 p-4 rounded-xl bg-card-bg border border-glow-border glass"
                >
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-text-secondary">Token Expires</span>
                    <span className="font-mono text-white">{formatTime(status.fyers.tokenExpiresAt)}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-text-secondary">Data Source</span>
                    <span className="font-mono text-neon-cyan">Fyers API v3 (WebSocket)</span>
                  </div>
                </motion.div>
              )}

              {/* Connect Button */}
              <motion.button
                onClick={handleFyersConnect}
                disabled={status?.fyers.connected || isLoading}
                whileHover={{ scale: 1.02, boxShadow: "0 0 20px rgba(0, 240, 255, 0.3)" }}
                whileTap={{ scale: 0.98 }}
                className={`w-full py-3.5 rounded-xl font-bold text-lg transition-all duration-300 flex items-center justify-center gap-2 ${
                  status?.fyers.connected
                    ? "bg-gradient-to-r from-neon-green to-neon-cyan text-true-black cursor-not-allowed opacity-60"
                    : "bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black shadow-glow-cyan hover:shadow-glow-cyan/50 disabled:opacity-50"
                }`}
              >
                {status?.fyers.connected ? (
                  <>
                    <CheckCircle className="w-5 h-5" strokeWidth={2.5} />
                    Fyers Connected
                  </>
                ) : isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" strokeWidth={2.5} />
                    Connecting...
                  </>
                ) : (
                  <>
                    <ExternalLink className="w-5 h-5" strokeWidth={2.5} />
                    Login with Fyers
                  </>
                )}
              </motion.button>

              <p className="mt-4 text-center text-xs text-text-muted">
                Redirects to Fyers OAuth for token authorization. Required for market data & quotes.
              </p>
            </motion.div>

            {/* Kotak Card */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="glass rounded-2xl border border-glow-border p-6 relative overflow-hidden group"
            >
              <div className="absolute -top-10 -right-10 w-40 h-40 rounded-full bg-neon-orange/10 blur-3xl" />

              <div className="relative z-10 flex items-start justify-between mb-6">
                <div className="flex items-center gap-4">
                  <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-neon-orange to-neon-red flex items-center justify-center shadow-glow-orange">
                    <Zap className="w-7 h-7 text-true-black" strokeWidth={2.5} />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-white">Kotak Neo</h2>
                    <p className="text-sm text-text-muted">Order Execution Broker</p>
                  </div>
                </div>

                {/* Status Badge */}
                <motion.div
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-full font-medium text-sm ${
                    status?.kotak.connected
                      ? "bg-neon-green/20 text-neon-green border border-neon-green/30"
                      : "bg-neon-red/20 text-neon-red border border-neon-red/30"
                  } glass`}
                >
                  {status?.kotak.connected ? (
                    <>
                      <span className="w-2 h-2 rounded-full bg-neon-green animate-pulse-glow" />
                      Connected
                    </>
                  ) : (
                    <>
                      <span className="w-2 h-2 rounded-full bg-neon-red" />
                      Disconnected
                    </>
                  )}
                </motion.div>
              </div>

              {/* Connection Details */}
              {status?.kotak.connected && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  className="space-y-2 mb-6 p-4 rounded-xl bg-card-bg border border-glow-border glass"
                >
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-text-secondary">Token Expires</span>
                    <span className="font-mono text-white">{formatTime(status.kotak.tokenExpiresAt)}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-text-secondary">Execution</span>
                    <span className="font-mono text-neon-orange">Kotak Neo API</span>
                  </div>
                </motion.div>
              )}

              {/* Connect Button */}
              <motion.button
                onClick={handleKotakConnect}
                disabled={status?.kotak.connected || isLoading}
                whileHover={{ scale: 1.02, boxShadow: "0 0 20px rgba(249, 115, 22, 0.4)" }}
                whileTap={{ scale: 0.98 }}
                className={`w-full py-3.5 rounded-xl font-bold text-lg transition-all duration-300 flex items-center justify-center gap-2 ${
                  status?.kotak.connected
                    ? "bg-gradient-to-r from-neon-green to-neon-cyan text-true-black cursor-not-allowed opacity-60"
                    : "bg-gradient-to-r from-neon-orange to-neon-red text-white shadow-glow-orange hover:shadow-glow-orange/50 disabled:opacity-50"
                }`}
              >
                {status?.kotak.connected ? (
                  <>
                    <CheckCircle className="w-5 h-5" strokeWidth={2.5} />
                    Kotak Connected
                  </>
                ) : isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" strokeWidth={2.5} />
                    Connecting...
                  </>
                ) : (
                  <>
                    <Shield className="w-5 h-5" strokeWidth={2.5} />
                    Login with Kotak
                  </>
                )}
              </motion.button>

              <p className="mt-4 text-center text-xs text-text-muted">
                Uses TOTP + MPIN for secure login. Required for order placement & position management.
              </p>
            </motion.div>
          </div>

          {/* Admin Panel Note */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="glass rounded-2xl border border-neon-purple/30 bg-neon-purple/5 p-6"
          >
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-neon-purple/20 flex items-center justify-center flex-shrink-0">
                <Info className="w-5 h-5 text-neon-purple" strokeWidth={2.5} />
              </div>
              <div>
                <h3 className="font-semibold text-white mb-2">Admin Panel Configuration</h3>
                <p className="text-text-secondary text-sm leading-relaxed">
                  Broker credentials (Fyers Client ID/Secret, Kotak Consumer Key/TOTP/MPIN) are managed securely via the
                  <strong className="text-neon-purple"> Admin Panel backend</strong>.
                  The frontend only initiates OAuth flows; sensitive credentials are never stored in the browser.
                </p>
              </div>
            </div>
          </motion.div>

          {/* Refresh Button */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.4 }}
            className="text-center"
          >
            <motion.button
              onClick={fetchStatus}
              disabled={isLoading}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="flex items-center gap-2 mx-auto px-6 py-2.5 rounded-xl bg-card-bg border border-glow-border hover:border-neon-cyan/50 text-white font-medium transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed glass"
            >
              <RefreshCw className={`w-5 h-5 ${isLoading ? "animate-spin" : ""}`} strokeWidth={2.5} />
              <span>Refresh Status</span>
            </motion.button>
          </motion.div>
        </main>
      </div>
    </div>
  );
}