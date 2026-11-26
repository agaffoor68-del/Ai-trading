"use client";

import { Loader2, Wifi, AlertCircle, RefreshCw, TrendingUp, TrendingDown, Minus } from "lucide-react";
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
};

/** Backend returns confidence as a 0-1 score; tolerate an already-percent value. */
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

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="w-full lg:ml-64 min-h-screen flex flex-col">
        <Header />
        <main className="flex-1 p-4 md:p-8">
          <div className="flex items-center justify-between gap-3 mb-4">
            <h1 className="text-3xl font-bold text-white">AI Signals</h1>
            <button
              type="button"
              onClick={() => mutate()}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-card-bg border border-glow-border text-white text-sm"
              aria-label="Refresh AI signals"
            >
              <RefreshCw className="w-4 h-4" strokeWidth={2.5} />
              Refresh
            </button>
          </div>

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
            signals.length === 0 ? (
              <div className="col-span-full text-center text-text-muted py-8">
                <p>No signals available right now.</p>
                <p className="text-sm mt-1">
                  Signals are derived from live Fyers quotes. Reconnect Fyers or press Refresh to retry.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {signals.map((signal: any, index: number) => {
                  const tone = signalTone(signal.signal);
                  const SignalIcon =
                    signal.signal === "BUY" ? TrendingUp :
                    signal.signal === "SELL" ? TrendingDown : Minus;

                  return (
                    <div key={signal.symbol ?? index} className="glass rounded-xl border border-glow-border p-4">
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="font-bold text-white">{signal.symbol}</h3>
                        <span className={`text-[10px] px-2 py-0.5 rounded border ${tone.bg} ${tone.text} font-semibold`}>
                          {signal.signal}
                        </span>
                      </div>

                      <dl className="space-y-1.5 text-sm">
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
                      </dl>

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
            )
          )}

          <p className="mt-6 text-xs text-text-muted">
            Signals are heuristic indicators from live Fyers quotes, not verified predictions. Treat confidence as a
            rough score, not a calibrated probability.
          </p>
        </main>
      </div>
    </div>
  );
}
