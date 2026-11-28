"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Loader2, Wifi, AlertCircle, RefreshCw, TrendingUp, TrendingDown, Minus, Search, Filter, ChevronDown, Shield } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { useAISignals, SERVER_WAKING_MESSAGE } from "@/lib/hooks";

const AI_SYMBOLS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"];

type AISignal = {
  symbol?: string;
  signal: string;
  price?: number;
  rsi?: number;
  ema_trend?: string;
  confidence?: unknown;
  timestamp?: string;
  regime?: string;
  regime_label?: string;
  supporting_indicators?: string[];
  conflicting_indicators?: string[];
  reason?: string;
  risk_reward_ratio?: number;
  data_freshness?: any;
};

type SignalFilter = {
  symbol: string;
  signal: string;
  regime: string;
};

function formatConfidence(raw: unknown): string {
  const value = Number(raw);
  if (!Number.isFinite(value)) return "—";
  const pct = value <= 1 ? value * 100 : value;
  return `${pct.toFixed(0)}%`;
}

function signalTone(signal: string): { text: string; bg: string } {
  switch ((signal || "").toUpperCase()) {
    case "BUY":
    case "STRONG_BUY":
      return { text: "text-neon-green", bg: "bg-neon-green/15 border-neon-green/30" };
    case "SELL":
    case "STRONG_SELL":
      return { text: "text-neon-red", bg: "bg-neon-red/15 border-neon-red/30" };
    default:
      return { text: "text-neon-orange", bg: "bg-neon-orange/15 border-neon-orange/30" };
  }
}

function getFilterOptions(signals: any[]): {
  symbols: string[];
  signals: string[];
  regimes: string[];
} {
  const symbols = [...new Set(signals.map((s: any) => s.symbol).filter(Boolean))];
  const signalTypes = [...new Set(signals.map((s: any) => s.signal))];
  const regimes = [...new Set(signals.map((s: any) => s.regime).filter(Boolean))];
  return { symbols, signalTypes, regimes };
}

export default function AISignalsPage() {
  const {
    signals,
    isLoading,
    isError,
    error,
    isFyersNotConnected,
    isServerWakingUp: wakingUp,
    mutate,
  } = useAISignals(AI_SYMBOLS);

  // State for filters
  const [filters, setFilters] = useState<SignalFilter>({
    symbol: "",
    signal: "",
    regime: "",
  });

  const [showFilters, setShowFilters] = useState(false);

  // Compute filtered signals
  const filteredSignals = signals?.filter((signal: any) => {
    const matchesSymbol = filters.symbol ? signal.symbol === filters.symbol : true;
    const matchesSignal = filters.signal ? signal.signal === filters.signal : true;
    const matchesRegime = filters.regime ? signal.regime === filters.regime : true;
    return matchesSymbol && matchesSignal && matchesRegime;
  }) || [];

  // Filter options
  const { symbols, signalTypes, regimes } = getFilterOptions(signals || []);

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="w-full lg:ml-64 min-h-screen flex flex-col">
        <Header />
        <main className="flex-1 p-4 md:p-8">
          {/* Header with filters */}
          <div className="flex items-center justify-between gap-3 mb-6">
            <h1 className="text-3xl font-bold text-white">AI Signals</h1>

            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowFilters((v) => !v)}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-card-bg border border-glow-border text-white text-sm"
                aria-label="Toggle filters"
              >
                <Filter className="w-4 h-4" strokeWidth={2} />
                {showFilters ? "Hide filters" : "Filters"}
              </button>
            </div>
          </div>

          {/* Filters panel */}
          {showFilters && (
            <div className="glass rounded-2xl border border-glow-border p-4 md:p-6 mt-4 bg-card-bg/50">
              <h3 className="text-semibold text-white mb-4">Filter Signals</h3>
              <div className="grid grid-cols-2 gap-3 mb-4">
                <div>
                  <label className="block text-xs text-text-muted uppercase tracking-wider mb-1">Symbol</label>
                  <select
                    onChange={(e) => setFilters((prev) => ({ ...prev, symbol: e.target.value }))}
                    className="w-full bg-true-black border border-glow-border rounded-lg p-2 text-white outline-none"
                  >
                    <option value="">All symbols</option>
                    {symbols.map((sym) => (
                      <option key={sym} value={sym}>
                        {sym}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-text-muted uppercase tracking-wider mb-1">Signal Type</label>
                  <select
                    onChange={(e) => setFilters((prev) => ({ ...prev, signal: e.target.value }))}
                    className="w-full bg-true-black border border-glow-border rounded-lg p-2 text-white outline-none"
                  >
                    <option value="">All signal types</option>
                    {signalTypes.map((sig) => (
                      <option key={sig} value={sig}>
                        {sig}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs text-text-muted uppercase tracking-wider mb-1">Regime</label>
                <select
                  onChange={(e) => setFilters((prev) => ({ ...prev, regime: e.target.value }))}
                  className="w-full bg-true-black border border-glow-border rounded-lg p-2 text-white outline-none"
                >
                  <option value="">All regimes</option>
                  {regimes.map((reg) => (
                    <option key={reg} value={reg}>
                      {reg}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {/* Status section */}
          <div className="flex items-center justify-between gap-3 mb-4">
            {isLoading && (
              <p className="text-neon-orange flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading signals...
              </p>
            )}

            {!isLoading && isError && (
              <div className="flex flex-col items-start gap-3">
                <p className="text-neon-red flex items-center gap-2">
                  <AlertCircle className="w-4 h-4" strokeWidth={2.5} />
                  {wakingUp ? SERVER_WAKING_MESSAGE : (error || "Failed to load AI signals")}
                </p>
                {isFyersNotConnected && (
                  <a
                    href="/broker-connect"
                    className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black font-bold shadow-glow-cyan hover:opacity-90"
                  >
                    <Wifi className="w-4 h-4" strokeWidth={2.5} />
                    Connect Fyers
                  </a>
                )}
              </div>
            )}

            {!isLoading && !isError && (
              <div className="flex items-center gap-3">
                <span className="text-text-muted">
                  {filteredSignals.length} {filteredSignals.length === 1 ? "signal" : "signals"} matched
                </span>
                {showFilters ? (
                  <span className="ml-2 text-xs text-neon-cyan">(filtered)</span>
                ) : null}
              </div>
            )}
          </div>

          {/* No signals state */}
          {!isLoading && !isError && (
            filteredSignals.length === 0 ? (
              <div className="col-span-full text-center text-text-muted py-8">
                <p>No signals match the current filters.</p>
                <p className="text-sm mt-1">
                  Adjust the filters above or press Refresh to get new signals.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredSignals.map((signal: any, index: number) => {
                  const tone = signalTone(signal.signal);
                  const SignalIcon =
                    signal.signal === "BUY" ? TrendingUp :
                    signal.signal === "SELL" ? TrendingDown : Minus;
                  const unavailable = signal.data_available === false;

                  return (
                    <div
                      key={signal.symbol ?? index}
                      className="glass rounded-xl border border-glow-border p-4 hover:bg-card-bg/30 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="font-bold text-white">{signal.symbol}</h3>
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded border font-semibold ${
                            unavailable
                              ? "bg-neon-orange/15 border-neon-orange/30 text-neon-orange"
                              : `${tone.bg} ${tone.text}`
                          }`}
                        >
                          {unavailable ? "NO DATA" : signal.signal}
                        </span>
                      </div>

                      {unavailable ? (
                        <div className="text-sm text-text-muted">
                          <p className="font-medium text-white mb-1">Data unavailable</p>
                          <p className="text-xs">
                            {signal.message || "No candle history was returned for this symbol."}
                          </p>
                        </div>
                      ) : (
                      {/* Enhanced signal detail panel */}
                      <dl className="space-y-2.5 text-sm">
                        <div className="flex items-center justify-between">
                          <dt className="text-text-muted">Price</dt>
                          <dd className="font-mono font-semibold text-white">
                            {typeof signal.price === "number" ? `₹${signal.price.toLocaleString()}` : "—"}
                          </dd>
                        </div>

                        <div className="flex items-center justify-between">
                          <dt className="text-text-muted">RSI</dt>
                          <dd className="font-mono font-semibold text-neon-cyan">
                            {typeof signal.rsi === "number" ? signal.rsi.toFixed(1) : "—"}
                          </dd>
                        </div>

                        <div className="flex items-center justify-between">
                          <dt className="text-text-muted">EMA Trend</dt>
                          <dd className={`font-mono font-semibold text-xs ${
                            signal.ema_trend === "BULLISH" ? "text-neon-green" :
                            signal.ema_trend === "BEARISH" ? "text-neon-red" : "text-neon-orange"
                          }`}>
                            {signal.ema_trend ?? "—"}
                          </dd>
                        </div>

                        <div className="flex items-center justify-between">
                          <dt className="text-text-muted">Confidence</dt>
                          <dd className="font-mono font-semibold text-white">
                            {formatConfidence(signal.confidence)}
                          </dd>
                        </div>

                        {/* Regime display */}
                        {signal.regime && signal.regime_label && (
                          <div className="flex items-center gap-2">
                            <dt className="text-text-muted">Regime</dt>
                            <dd className="font-mono text-neon-purple">
                              {signal.regime_label} ({signal.regime})
                            </dd>
                          </div>
                        )}

                        {/* Supporting & Conflicting Indicators */}
                        {signal.supporting_indicators && signal.supporting_indicators.length > 0 && (
                          <div className="flex flex-wrap gap-1 text-xs text-text-secondary">
                            {signal.supporting_indicators.map((ind: string, i: number) => (
                              <span key={i} className="px-2 py-1 rounded bg-neon-purple/20 text-neon-purple text-[10px]">
                                {ind}
                              </span>
                            ))}
                          </div>
                        )}

                        {signal.conflicting_indicators && signal.conflicting_indicators.length > 0 && (
                          <div className="flex flex-wrap gap-1 text-xs text-text-secondary">
                            {signal.conflicting_indicators.map((ind: string, i: number) => (
                              <span key={i} className="px-2 py-1 rounded bg-neon-red/20 text-neon-red">
                                {ind}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Risk/Reward Ratio */}
                        {signal.risk_reward_ratio !== undefined && signal.risk_reward_ratio !== null && (
                          <div className="mt-1 p-2 rounded bg-neon-orange/20 text-neon-orange text-xs">
                            <div className="font-medium text-white">R/R Ratio</div>
                            <div className="font-bold text-neon-orange">{signal.risk_reward_ratio}</div>
                          </div>
                        )}

                        {/* Signal reason */}
                        {signal.reason && (
                          <div className="mt-2 text-xs text-text-secondary line-clamp-3" style={{ "max-height": "60px" }}>
                            <strong>Why:</strong> {signal.reason.substring(0, 120)}${signal.reason.length > 120 ? "..." : ""}
                          </div>
                        )}
                      </dl>
                      )}

                      <p className="mt-3 flex items-center gap-1 text-[11px] text-text-muted">
                        <SignalIcon className="w-3 h-3" strokeWidth={2.5} />
                        {signal.timestamp
                          ? new Date(signal.timestamp).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" })
                          : "Updated just now"}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}

            <p className="mt-6 text-xs text-text-muted">
              Signals are calculated from real Fyers candle history (RSI 14, EMA 9/21) on the 15-minute
              timeframe, not from the day&apos;s price change. When history is unavailable the symbol is
              marked NO DATA rather than given a fabricated value. Treat confidence as a rough score, not
              a calibrated probability.
            </p>
          )}
        </main>
      </div>
    </div>
  );
}
