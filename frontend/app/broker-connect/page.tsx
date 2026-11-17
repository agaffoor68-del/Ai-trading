"use client";

import { useState, useCallback, useEffect } from "react";
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
  Save,
  Wifi,
  Eye,
  EyeOff,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { api, isFyersNotConnected, fetchWithTimeout, isServerWakingUp, SERVER_WAKING_MESSAGE } from "@/lib/api-client";

export default function BrokerConnectPage() {
  const [status, setStatus] = useState<{ fyers: any; kotak: any; market: any } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Fyers input fields
  const [fyersClientId, setFyersClientId] = useState("");
  const [fyersSecretKey, setFyersSecretKey] = useState("");
  const [fyersSaving, setFyersSaving] = useState(false);
  const [fyersError, setFyersError] = useState<string | null>(null);
  const [showSecret, setShowSecret] = useState(false);
  
  // Kotak input fields
  const [kotakConsumerKey, setKotakConsumerKey] = useState("");
  const [kotakConsumerSecret, setKotakConsumerSecret] = useState("");
  const [kotakTotpSecret, setKotakTotpSecret] = useState("");
  const [kotakMobileNumber, setKotakMobileNumber] = useState("");
  const [kotakMpin, setKotakMpin] = useState("");
  const [kotakUcc, setKotakUcc] = useState("");
  const [kotakSaving, setKotakSaving] = useState(false);
  const [kotakError, setKotakError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await fetchWithTimeout("/api/v1/fyers/status", {
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setStatus(data);
      setError(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch broker status";
      setError(isServerWakingUp(err) ? SERVER_WAKING_MESSAGE : errorMessage);
      setStatus({
        fyers: { connected: false, valid: false, message: "Failed to load" },
        kotak: { configured: false, connected: false, message: "Failed to load" },
        market: { is_open: false, is_trading_day: false, time_to_close_minutes: 0 },
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const formatTime = (isoString: string | null) => {
    if (!isoString) return "Never";
    try {
      return new Date(isoString).toLocaleString();
    } catch {
      return isoString;
    }
  };

  const handleFyersSaveAndConnect = async () => {
    if (!fyersClientId.trim() || !fyersSecretKey.trim()) {
      setFyersError("Please enter both Fyers Client ID and Secret Key");
      return;
    }

    setFyersSaving(true);
    setFyersError(null);
    try {
      const response = await api.connectFyers(fyersClientId.trim(), fyersSecretKey.trim());
      const authUrl = response.auth_url ?? response.authorization_url;
      if (!authUrl) {
        throw new Error("Fyers did not return an authorization URL");
      }

      window.location.href = authUrl;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to connect to Fyers";
      setFyersError(errorMessage);
      if (isFyersNotConnected(err)) {
        setFyersError("Fyers not connected. Please check credentials and try again.");
      }
    } finally {
      setFyersSaving(false);
    }
  };

  const handleKotakSaveAndConnect = async () => {
    if (!kotakConsumerKey.trim() || !kotakConsumerSecret.trim() || !kotakTotpSecret.trim() || !kotakMobileNumber.trim() || !kotakMpin.trim()) {
      setKotakError("Please fill all required Kotak fields");
      return;
    }

    setKotakSaving(true);
    setKotakError(null);
    try {
      // Save credentials to backend (endpoint would need to be created)
      const response = await fetchWithTimeout("/api/v1/kotak/save-credentials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          consumer_key: kotakConsumerKey.trim(),
          consumer_secret: kotakConsumerSecret.trim(),
          totp_secret: kotakTotpSecret.trim(),
          mobile_number: kotakMobileNumber.trim(),
          mpin: kotakMpin.trim(),
          ucc: kotakUcc.trim(),
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.message || `HTTP ${response.status}`);
      }

      // Initiate Kotak login
      const loginResponse = await fetchWithTimeout("/api/v1/kotak/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
      });

      if (!loginResponse.ok) {
        const errData = await loginResponse.json().catch(() => ({}));
        throw new Error(errData.message || `HTTP ${loginResponse.status}`);
      }

      const data = await loginResponse.json();
      if (data.redirect_url) {
        window.location.href = data.redirect_url;
      } else {
        alert("Kotak login initiated. Check the backend logs.");
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to save Kotak credentials";
      setKotakError(errorMessage);
    } finally {
      setKotakSaving(false);
    }
  };

  // Check for fyers callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const fyersResult = params.get("fyers");
    if (fyersResult) {
      if (fyersResult === "connected") {
        setFyersError(null);
        // Clear the URL params
        window.history.replaceState({}, document.title, window.location.pathname);
        fetchStatus();
      } else {
        setFyersError(`Fyers connection failed: ${params.get("reason") || "unknown reason"}`);
        window.history.replaceState({}, document.title, window.location.pathname);
      }
    }
  }, [fetchStatus]);

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="w-full lg:ml-64 min-h-screen flex flex-col">
        <Header />

        <main className="flex-1 p-4 md:p-8 lg:p-10 pt-20 lg:pt-24 space-y-8 max-w-4xl mx-auto w-full">
          {/* Page Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight flex items-center gap-3">
              <Link className="w-8 h-8 text-neon-cyan" strokeWidth={2.5} />
              Broker Connect
            </h1>
            <p className="text-text-secondary mt-1">Configure and connect Fyers (Data) and Kotak Neo (Execution)</p>
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
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
            {/* Fyers Card */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="glass rounded-2xl border border-glow-border p-4 md:p-6 relative overflow-hidden group"
            >
              <div className="absolute -top-10 -right-10 w-40 h-40 rounded-full bg-neon-cyan/10 blur-3xl" />

              <div className="relative z-10 flex items-start justify-between mb-6 flex-wrap gap-4">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 md:w-14 md:h-14 rounded-xl bg-gradient-to-br from-neon-cyan to-neon-purple flex items-center justify-center shadow-glow-cyan">
                    <Database className="w-6 h-6 md:w-7 md:h-7 text-true-black" strokeWidth={2.5} />
                  </div>
                  <div>
                    <h2 className="text-lg md:text-xl font-bold text-white">Fyers API v3</h2>
                    <p className="text-sm text-text-muted">Market Data Provider</p>
                  </div>
                </div>

                {/* Status Badge */}
                <motion.div
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-full font-medium text-sm ${
                    status?.fyers?.connected && status?.fyers?.valid
                      ? "bg-neon-green/20 text-neon-green border border-neon-green/30"
                      : "bg-neon-red/20 text-neon-red border border-neon-red/30"
                  } glass`}
                >
                  {status?.fyers?.connected && status?.fyers?.valid ? (
                    <>
                      <span className="w-2 h-2 rounded-full bg-neon-green animate-pulse-glow" />
                      Connected
                    </>
                  ) : (
                    <>
                      <span className="w-2 h-2 rounded-full bg-neon-red" />
                      {status?.fyers?.message || "Disconnected"}
                    </>
                  )}
                </motion.div>
              </div>

              {/* Connection Details */}
              {status?.fyers?.connected && status?.fyers?.valid && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  className="space-y-2 mb-6 p-4 rounded-xl bg-card-bg border border-glow-border glass"
                >
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-text-secondary">Token Expires</span>
                    <span className="font-mono text-white">{formatTime(status.fyers.token_expires_at)}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-text-secondary">Data Source</span>
                    <span className="font-mono text-neon-cyan">Fyers API v3 (WebSocket)</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-text-secondary">User</span>
                    <span className="font-mono text-white">{status.fyers.profile?.name || "Unknown"}</span>
                  </div>
                </motion.div>
              )}

              {/* Fyers Credentials Input Fields */}
              {!status?.fyers?.connected && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  className="space-y-4 mb-6 p-4 rounded-xl bg-card-bg/50 border border-glow-border glass"
                >
                  <div>
                    <label className="block text-sm font-medium text-text-secondary mb-2">Fyers Client ID</label>
                    <input
                      type="text"
                      value={fyersClientId}
                      onChange={(e) => setFyersClientId(e.target.value)}
                      placeholder="Enter your Fyers Client ID"
                      className="w-full px-4 py-2.5 bg-true-black border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white placeholder-text-muted transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-text-secondary mb-2">Fyers Secret Key</label>
                    <div className="relative">
                      <input
                        type={showSecret ? "text" : "password"}
                        value={fyersSecretKey}
                        onChange={(e) => setFyersSecretKey(e.target.value)}
                        placeholder="Enter your Fyers Secret Key"
                        className="w-full px-4 py-2.5 bg-true-black border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white placeholder-text-muted transition-colors pr-12"
                      />
                      <motion.button
                        onClick={() => setShowSecret(!showSecret)}
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-text-muted hover:text-white transition-colors"
                        title={showSecret ? "Hide" : "Show"}
                      >
                        {showSecret ? <EyeOff className="w-4 h-4" strokeWidth={2} /> : <Eye className="w-4 h-4" strokeWidth={2} />}
                      </motion.button>
                    </div>
                  </div>
                </motion.div>
              )}

              {/* Error Display */}
              {fyersError && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mb-4 p-3 rounded-lg bg-neon-red/10 border border-neon-red/30 text-neon-red text-sm flex items-center gap-2"
                >
                  <AlertCircle className="w-4 h-4 flex-shrink-0" strokeWidth={2.5} />
                  <span>{fyersError}</span>
                </motion.div>
              )}

              {/* Save & Connect Button */}
              <motion.button
                onClick={handleFyersSaveAndConnect}
                disabled={status?.fyers?.connected || isLoading || fyersSaving}
                whileHover={{ scale: 1.02, boxShadow: "0 0 20px rgba(0, 240, 255, 0.3)" }}
                whileTap={{ scale: 0.98 }}
                className={`w-full py-3.5 rounded-xl font-bold text-lg transition-all duration-300 flex items-center justify-center gap-2 ${
                  status?.fyers?.connected
                    ? "bg-gradient-to-r from-neon-green to-neon-cyan text-true-black cursor-not-allowed opacity-60"
                    : "bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black shadow-glow-cyan hover:shadow-glow-cyan/50 disabled:opacity-50"
                }`}
              >
                {status?.fyers?.connected ? (
                  <>
                    <CheckCircle className="w-5 h-5" strokeWidth={2.5} />
                    Fyers Connected
                  </>
                ) : fyersSaving ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" strokeWidth={2.5} />
                    Saving & Connecting...
                  </>
                ) : (
                  <>
                    <Save className="w-5 h-5" strokeWidth={2.5} />
                    Save & Connect to Fyers
                  </>
                )}
              </motion.button>

              <p className="mt-4 text-center text-xs text-text-muted">
                Enter your Fyers API credentials. Clicking "Save & Connect" will store them securely and redirect to Fyers OAuth for authorization.
              </p>
            </motion.div>

            {/* Kotak Card */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="glass rounded-2xl border border-glow-border p-4 md:p-6 relative overflow-hidden group"
            >
              <div className="absolute -top-10 -right-10 w-40 h-40 rounded-full bg-neon-orange/10 blur-3xl" />

              <div className="relative z-10 flex items-start justify-between mb-6 flex-wrap gap-4">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 md:w-14 md:h-14 rounded-xl bg-gradient-to-br from-neon-orange to-neon-red flex items-center justify-center shadow-glow-orange">
                    <Zap className="w-6 h-6 md:w-7 md:h-7 text-true-black" strokeWidth={2.5} />
                  </div>
                  <div>
                    <h2 className="text-lg md:text-xl font-bold text-white">Kotak Neo</h2>
                    <p className="text-sm text-text-muted">Order Execution Broker</p>
                  </div>
                </div>

                {/* Status Badge */}
                <motion.div
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-full font-medium text-sm ${
                    status?.kotak?.connected
                      ? "bg-neon-green/20 text-neon-green border border-neon-green/30"
                      : status?.kotak?.configured
                        ? "bg-neon-orange/20 text-neon-orange border border-neon-orange/30"
                        : "bg-neon-red/20 text-neon-red border border-neon-red/30"
                  } glass`}
                >
                  {status?.kotak?.connected ? (
                    <>
                      <span className="w-2 h-2 rounded-full bg-neon-green animate-pulse-glow" />
                      Connected
                    </>
                  ) : status?.kotak?.configured ? (
                    <>
                      <span className="w-2 h-2 rounded-full bg-neon-orange" />
                      Configured
                    </>
                  ) : (
                    <>
                      <span className="w-2 h-2 rounded-full bg-neon-red" />
                      Not Configured
                    </>
                  )}
                </motion.div>
              </div>

              {/* Connection Details */}
              {status?.kotak?.connected && (
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

              {/* Kotak Credentials Input Fields */}
              {!status?.kotak?.connected && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  className="space-y-3 mb-6 p-4 rounded-xl bg-card-bg/50 border border-glow-border glass"
                >
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-text-secondary mb-2">Consumer Key</label>
                      <input
                        type="text"
                        value={kotakConsumerKey}
                        onChange={(e) => setKotakConsumerKey(e.target.value)}
                        placeholder="Kotak Consumer Key"
                        className="w-full px-3 py-2 bg-true-black border border-glow-border focus:border-neon-orange focus:outline-none rounded-lg text-white placeholder-text-muted transition-colors text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-text-secondary mb-2">Consumer Secret</label>
                      <input
                        type="password"
                        value={kotakConsumerSecret}
                        onChange={(e) => setKotakConsumerSecret(e.target.value)}
                        placeholder="Kotak Consumer Secret"
                        className="w-full px-3 py-2 bg-true-black border border-glow-border focus:border-neon-orange focus:outline-none rounded-lg text-white placeholder-text-muted transition-colors text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-text-secondary mb-2">TOTP Secret</label>
                      <input
                        type="text"
                        value={kotakTotpSecret}
                        onChange={(e) => setKotakTotpSecret(e.target.value)}
                        placeholder="TOTP Secret"
                        className="w-full px-3 py-2 bg-true-black border border-glow-border focus:border-neon-orange focus:outline-none rounded-lg text-white placeholder-text-muted transition-colors text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-text-secondary mb-2">Mobile Number</label>
                      <input
                        type="text"
                        value={kotakMobileNumber}
                        onChange={(e) => setKotakMobileNumber(e.target.value)}
                        placeholder="Registered Mobile"
                        className="w-full px-3 py-2 bg-true-black border border-glow-border focus:border-neon-orange focus:outline-none rounded-lg text-white placeholder-text-muted transition-colors text-sm"
                      />
                    </div>
                    <div className="col-span-2">
                      <label className="block text-sm font-medium text-text-secondary mb-2">MPIN</label>
                      <input
                        type="password"
                        value={kotakMpin}
                        onChange={(e) => setKotakMpin(e.target.value)}
                        placeholder="MPIN"
                        className="w-full px-3 py-2 bg-true-black border border-glow-border focus:border-neon-orange focus:outline-none rounded-lg text-white placeholder-text-muted transition-colors text-sm"
                      />
                    </div>
                    <div className="col-span-2">
                      <label className="block text-sm font-medium text-text-secondary mb-2">UCC (Optional)</label>
                      <input
                        type="text"
                        value={kotakUcc}
                        onChange={(e) => setKotakUcc(e.target.value)}
                        placeholder="UCC"
                        className="w-full px-3 py-2 bg-true-black border border-glow-border focus:border-neon-orange focus:outline-none rounded-lg text-white placeholder-text-muted transition-colors text-sm"
                      />
                    </div>
                  </div>
                </motion.div>
              )}

              {/* Error Display */}
              {kotakError && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mb-4 p-3 rounded-lg bg-neon-red/10 border border-neon-red/30 text-neon-red text-sm flex items-center gap-2"
                >
                  <AlertCircle className="w-4 h-4 flex-shrink-0" strokeWidth={2.5} />
                  <span>{kotakError}</span>
                </motion.div>
              )}

              {/* Save & Connect Button */}
              <motion.button
                onClick={handleKotakSaveAndConnect}
                disabled={status?.kotak?.connected || isLoading || kotakSaving}
                whileHover={{ scale: 1.02, boxShadow: "0 0 20px rgba(249, 115, 22, 0.4)" }}
                whileTap={{ scale: 0.98 }}
                className={`w-full py-3.5 rounded-xl font-bold text-lg transition-all duration-300 flex items-center justify-center gap-2 ${
                  status?.kotak?.connected
                    ? "bg-gradient-to-r from-neon-green to-neon-cyan text-true-black cursor-not-allowed opacity-60"
                    : "bg-gradient-to-r from-neon-orange to-neon-red text-white shadow-glow-orange hover:shadow-glow-orange/50 disabled:opacity-50"
                }`}
              >
                {status?.kotak?.connected ? (
                  <>
                    <CheckCircle className="w-5 h-5" strokeWidth={2.5} />
                    Kotak Connected
                  </>
                ) : kotakSaving ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" strokeWidth={2.5} />
                    Saving & Connecting...
                  </>
                ) : (
                  <>
                    <Save className="w-5 h-5" strokeWidth={2.5} />
                    Save & Connect to Kotak
                  </>
                )}
              </motion.button>

              <p className="mt-4 text-center text-xs text-text-muted">
                Enter your Kotak Neo API credentials. Uses TOTP + MPIN for secure login. Required for order placement & position management.
              </p>
            </motion.div>
          </div>

          {/* Admin Panel Note */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="glass rounded-2xl border border-neon-purple/30 bg-neon-purple/5 p-4 md:p-6"
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
