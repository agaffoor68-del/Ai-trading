"use client";

import { motion } from "framer-motion";
import { Brain, Zap, X, Check, Settings, SlidersHorizontal, AlertCircle, Wifi, Loader2 } from "lucide-react";
import { useAISignals, SERVER_WAKING_MESSAGE } from "@/lib/hooks";

export function AISignalCard() {
  const { signals, isLoading, isError, error, isFyersNotConnected, isServerWakingUp: wakingUp, mutate } = useAISignals(["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]);

  // Get the first signal (NIFTY) or none
  const signal = signals[0];

  // Backend sends confidence as a 0-1 score; both the label and the bar need a
  // percentage, otherwise 0.5 renders as "0.5%" and the bar looks empty.
  const rawConfidence = Number(signal?.confidence);
  const confidencePct = Number.isFinite(rawConfidence)
    ? (rawConfidence <= 1 ? rawConfidence * 100 : rawConfidence)
    : 0;
  const confidenceLabel = Number.isFinite(rawConfidence) ? confidencePct.toFixed(0) + "%" : "—";

  const showConnectCard = isFyersNotConnected;

  // The backend reports data_available=false with a reason instead of
  // inventing an RSI. Render that reason rather than a fabricated number.
  const dataUnavailable = signal ? signal.data_available === false : false;

  // Loading state
  if (isLoading) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[300px] flex flex-col"
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-glow-border bg-card-bg/50">
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-neon-purple" strokeWidth={2.5} />
            <h3 className="font-semibold text-white">Grok AI Radar</h3>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-orange/20 text-neon-orange font-medium animate-pulse">LOADING</span>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3 text-text-secondary">
            <span className="animate-spin">⏳</span>
            <span>Loading AI signals...</span>
          </div>
        </div>
      </motion.div>
    );
  }

  // Error state
  if (isError) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[300px] flex flex-col"
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-glow-border bg-card-bg/50">
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-neon-purple" strokeWidth={2.5} />
            <h3 className="font-semibold text-white">Grok AI Radar</h3>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-red/20 text-neon-red font-medium">ERROR</span>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-center text-text-secondary max-w-sm">
            {wakingUp ? (
              <>
                <Loader2 className="w-7 h-7 mx-auto mb-3 text-neon-cyan animate-spin" strokeWidth={2.5} />
                <p className="font-medium text-white mb-1">{SERVER_WAKING_MESSAGE}</p>
                <p className="text-sm text-text-muted">The backend is spinning up. This can take a few seconds.</p>
              </>
            ) : (
              <>
                <p className="mb-2">{showConnectCard ? "Fyers is not connected" : "Failed to load AI signals"}</p>
                <p className={`text-sm mb-4 ${showConnectCard ? "text-neon-orange/90" : "text-neon-red/80"}`}>
                  {showConnectCard ? "Connect your Fyers account to generate AI signals." : error}
                </p>
                {showConnectCard && (
                  <motion.a
                    href="/broker-connect"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black font-bold transition-all duration-300 shadow-glow-cyan hover:opacity-90"
                  >
                    <Wifi className="w-4 h-4" strokeWidth={2.5} />
                    Connect Fyers
                  </motion.a>
                )}
              </>
            )}
          </div>
        </div>
      </motion.div>
    );
  }

  // No data state (backend not ready or no Fyers connection)
  if (!signal) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[300px] flex flex-col"
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-glow-border bg-card-bg/50">
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-neon-purple" strokeWidth={2.5} />
            <h3 className="font-semibold text-white">Grok AI Radar</h3>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-orange/20 text-neon-orange font-medium">NO DATA</span>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-text-muted max-w-sm">
            <AlertCircle className="w-10 h-10 mx-auto mb-3 text-neon-orange/50" strokeWidth={2} />
            <p className="font-medium text-white mb-1">No AI signals available</p>
            <p className="text-sm mb-4">Connect Fyers and enable AI signals in settings</p>
            {showConnectCard && (
              <motion.a
                href="/broker-connect"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black font-bold transition-all duration-300 shadow-glow-cyan hover:opacity-90"
              >
                <Wifi className="w-4 h-4" strokeWidth={2.5} />
                Connect Fyers
              </motion.a>
            )}
          </div>
        </div>
      </motion.div>
    );
  }

  // Has signal - display it
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.5 }}
      className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[300px] flex flex-col"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-glow-border bg-card-bg/50">
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-neon-purple" strokeWidth={2.5} />
          <h3 className="font-semibold text-white">Grok AI Radar</h3>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-[10px] px-2 py-0.5 rounded font-medium flex items-center gap-1 ${
              dataUnavailable
                ? "bg-neon-orange/20 text-neon-orange"
                : "bg-neon-green/20 text-neon-green"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                dataUnavailable ? "bg-neon-orange" : "bg-neon-green animate-pulse-glow"
              }`}
            />
            {dataUnavailable ? "NO DATA" : "LIVE"}
          </span>
        </div>
      </div>

      {dataUnavailable ? (
        <div className="flex-1 flex items-center justify-center p-5">
          <div className="text-center text-text-muted max-w-sm">
            <AlertCircle className="w-10 h-10 mx-auto mb-3 text-neon-orange/60" strokeWidth={2} />
            <p className="font-medium text-white mb-1">Data unavailable</p>
            <p className="text-sm mb-1">{signal.symbol}</p>
            <p className="text-sm">
              {signal.message || "No candle history was returned for this symbol."}
            </p>
            {signal.timestamp && (
              <p className="mt-3 text-[11px]">
                Checked at{" "}
                {new Date(signal.timestamp).toLocaleTimeString("en-IN", {
                  timeZone: "Asia/Kolkata",
                })}
              </p>
            )}
            {showConnectCard && (
              <motion.a
                href="/broker-connect"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-4 inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black font-bold transition-all duration-300 shadow-glow-cyan hover:opacity-90"
              >
                <Wifi className="w-4 h-4" strokeWidth={2.5} />
                Connect Fyers
              </motion.a>
            )}
          </div>
        </div>
      ) : (
        <>
      {/* Signal Content */}
      <div className="flex-1 p-5 flex flex-col justify-center">
        {/* Signal Type & Instrument */}
        <div className="mb-5">
          <div className="flex items-center gap-3 mb-2">
            <motion.span
              className={`px-3 py-1 rounded-full text-xs font-bold ${signal.signal === "BUY" ? "bg-neon-green/20 text-neon-green border border-neon-green/30" : signal.signal === "SELL" ? "bg-neon-red/20 text-neon-red border border-neon-red/30" : "bg-neon-orange/20 text-neon-orange border border-neon-orange/30"}`}
              animate={signal.signal === "BUY" ? { boxShadow: ["0 0 0 0 rgba(0, 255, 102, 0.4)", "0 0 0 8px rgba(0, 255, 102, 0)"] } : signal.signal === "SELL" ? { boxShadow: ["0 0 0 0 rgba(255, 0, 60, 0.4)", "0 0 0 8px rgba(255, 0, 60, 0)"] } : undefined}
              transition={{ duration: 2, repeat: Infinity }}
            >
              {signal.signal}
            </motion.span>
            <Zap className="w-4 h-4 text-neon-orange animate-pulse" strokeWidth={2.5} />
          </div>
          <p className="text-2xl font-bold text-white tracking-tight">{signal.symbol}</p>
        </div>

        {/* Confidence */}
        <div className="mb-5">
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm text-text-secondary">Confidence Score</span>
            <span className="font-mono font-bold text-neon-cyan text-glow-cyan">{confidenceLabel}</span>
          </div>
          <div className="h-2 bg-card-bg rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${confidencePct}%` }}
              transition={{ type: "spring", stiffness: 100, damping: 15, delay: 0.6 }}
              className="h-full bg-gradient-to-r from-neon-cyan to-neon-green rounded-full shadow-glow-cyan"
            />
          </div>
        </div>

        {/* Price Levels */}
        <div className="grid grid-cols-3 gap-3 mb-5">
          <div className="p-3 rounded-xl bg-card-bg border border-glow-border">
            <p className="text-[11px] text-text-muted uppercase tracking-wider">Entry</p>
            <p className="font-mono font-semibold text-white text-lg">₹{signal.price.toFixed(2)}</p>
          </div>
          <div className="p-3 rounded-xl bg-card-bg border border-glow-border">
            <p className="text-[11px] text-text-muted uppercase tracking-wider">RSI</p>
            <p className="font-mono font-semibold text-neon-cyan text-lg">{signal.rsi.toFixed(1)}</p>
          </div>
          <div className="p-3 rounded-xl bg-card-bg border border-glow-border">
            <p className="text-[11px] text-text-muted uppercase tracking-wider">EMA Trend</p>
            <p className={`font-mono font-semibold ${signal.ema_trend === "BULLISH" ? "text-neon-green" : signal.ema_trend === "BEARISH" ? "text-neon-red" : "text-neon-orange"} text-lg`}>{signal.ema_trend}</p>
          </div>
        </div>

        {/* Details */}
        <div className="p-3 rounded-xl bg-neon-purple/5 border border-neon-purple/20 mb-5">
          <p className="text-sm text-text-secondary">
            {signal.timestamp ? `Last updated: ${new Date(signal.timestamp).toLocaleTimeString()}` : "Real-time signal from Grok AI"}
          </p>
        </div>

        {/* Refresh Button */}
        <motion.button
          onClick={() => mutate()}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-neon-purple to-neon-cyan text-true-black font-bold text-lg shadow-glow-purple transition-all duration-300 flex items-center justify-center gap-2"
        >
          <Check className="w-5 h-5" strokeWidth={2.5} />
          Refresh Signal
        </motion.button>
        </div>
        </>
      )}
    </motion.div>
  );
}
