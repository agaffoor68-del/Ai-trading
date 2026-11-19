"use client";

import { motion } from "framer-motion";
import { AlertCircle, Brain, Check, Loader2, Wifi } from "lucide-react";
import { useAISignals, SERVER_WAKING_MESSAGE } from "@/lib/hooks";

export function AISignalCard() {
  const { signals, isLoading, isError, error, errorCode, isFyersNotConnected, isFyersConnected, isServerWakingUp, mutate } = useAISignals(["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]);
  const showConnect = isFyersNotConnected && !isFyersConnected && (errorCode === 401 || errorCode === "FYERS_NOT_CONNECTED" || errorCode === "FYERS_TOKEN_EXPIRED");
  const signal = signals[0];

  return (
    <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass flex min-h-[300px] flex-col overflow-hidden rounded-2xl border border-glow-border">
      <header className="flex items-center gap-2 border-b border-glow-border bg-card-bg/50 px-5 py-4"><Brain className="h-5 w-5 text-neon-purple" /><h3 className="font-semibold text-white">Grok AI Radar</h3></header>
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
        {isLoading ? <><Loader2 className="h-7 w-7 animate-spin text-neon-cyan" /><p className="text-text-secondary">Loading AI signals…</p></>
          : showConnect ? <><AlertCircle className="h-9 w-9 text-neon-orange" /><p className="font-semibold text-white">Fyers is not connected</p><p className="text-sm text-text-muted">Reconnect Fyers to retrieve AI signals.</p><a href="/broker-connect" className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple px-5 py-3 font-bold text-true-black"><Wifi className="h-4 w-4" />Connect Fyers</a></>
          : isError ? <><AlertCircle className="h-8 w-8 text-neon-orange" /><p className="text-white">{isServerWakingUp ? SERVER_WAKING_MESSAGE : "Could not load AI signals"}</p><p className="text-sm text-text-muted">{error}</p></>
          : signal ? <><span className="rounded-full bg-neon-green/20 px-3 py-1 text-sm font-bold text-neon-green">{signal.signal ?? "SIGNAL"}</span><p className="text-2xl font-bold text-white">{signal.symbol ?? "Market signal"}</p>{signal.confidence != null && <p className="text-text-secondary">Confidence: {signal.confidence}%</p>}<button type="button" onClick={() => mutate()} className="mt-2 inline-flex items-center gap-2 rounded-lg bg-neon-purple px-4 py-2 font-semibold text-true-black"><Check className="h-4 w-4" />Refresh signals</button></>
          : <><AlertCircle className="h-8 w-8 text-neon-orange" /><p className="font-semibold text-white">No AI signals available</p><p className="text-sm text-text-muted">Fyers is connected; signals will appear when data is available.</p><button type="button" onClick={() => mutate()} className="mt-2 rounded-lg border border-glow-border px-4 py-2 text-text-secondary">Refresh</button></>}
      </div>
    </motion.section>
  );
}
