"use client";

import { useState, useEffect } from "react";
import { Loader2, Wifi } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { fetchWithTimeout, parseApiError, isFyersNotConnected, isServerWakingUp, SERVER_WAKING_MESSAGE } from "@/lib/api-client";
import { useFyersStatus } from "@/lib/hooks";

function isFyersConnected(status: any): boolean {
  const fyers = status?.fyers ?? status;
  return Boolean(fyers?.connected && fyers?.valid);
}

export default function AISignalsPage() {
  const [signals, setSignals] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fyersOffline, setFyersOffline] = useState(false);
  const { status: fyersStatus } = useFyersStatus();
  const fyersConnected = isFyersConnected(fyersStatus);

  const fetchSignals = async () => {
    setIsLoading(true);
    setError(null);
    setFyersOffline(false);
    try {
      const res = await fetchWithTimeout("/api/v1/market/ai/signals?symbols=NIFTY,BANKNIFTY,FINNIFTY,MIDCPNIFTY", {
        credentials: "same-origin",
      });
      if (!res.ok) {
        const apiError = parseApiError(await res.json().catch(() => null), res.status);
        if (isFyersNotConnected(apiError)) setFyersOffline(true);
        throw new Error(apiError.message);
      }
      const data = await res.json();
      setSignals(data.signals || []);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch AI signals";
      setError(isServerWakingUp(err) ? SERVER_WAKING_MESSAGE : message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSignals();
  }, []);

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="w-full lg:ml-64 min-h-screen flex flex-col">
        <Header />
        <main className="flex-1 p-8">
          <h1 className="text-3xl font-bold text-white mb-4">AI Signals</h1>
          {isLoading && <p className="text-neon-orange flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />Loading signals...</p>}
          {error && <div className="flex flex-col items-start gap-3"><p className="text-neon-red">Error: {error}</p>{fyersOffline && !fyersConnected && <a href="/settings" className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black font-bold shadow-glow-cyan hover:opacity-90"><Wifi className="w-4 h-4" strokeWidth={2.5} />Connect Fyers</a>}</div>}
          {!isLoading && !error && <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">{signals.length === 0 ? <div className="col-span-full text-center text-text-muted py-8"><p>{fyersConnected ? "No data available" : "No signals available"}</p>{!fyersConnected && <button onClick={fetchSignals} className="mt-4 px-4 py-2 bg-neon-cyan/20 border border-neon-cyan rounded text-neon-cyan">Scan for Signals</button>}</div> : signals.map((signal: any, index: number) => <div key={index} className="glass rounded-xl border border-glow-border p-4"><h3 className="font-bold text-white">{signal.symbol}</h3><p className="text-sm">Signal: {signal.signal}</p><p className="text-sm">Confidence: {signal.confidence}%</p><p className="text-sm">RSI: {signal.rsi}</p><p className="text-sm">EMA Trend: {signal.ema_trend}</p><p className="text-sm">Price: {signal.price}</p></div>)}</div>}
        </main>
      </div>
    </div>
  );
}
