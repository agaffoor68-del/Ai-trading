"use client";

import { useState, useEffect } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

export default function AISignalsPage() {
  const [signals, setSignals] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastScan, setLastScan] = useState<Date | null>(null);

  const fetchSignals = async () => {
    try {
      const res = await fetch("/api/v1/market/ai/signals?symbols=NIFTY,BANKNIFTY,FINNIFTY,MIDCPNIFTY", {
        credentials: "same-origin",
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      setSignals(data.signals || []);
      setLastScan(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch AI signals");
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
          {isLoading && <p className="text-neon-orange">Loading signals...</p>}
          {error && <p className="text-neon-red">Error: {error}</p>}
          {!isLoading && !error && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {signals.length === 0 ? (
                <div className="col-span-full text-center text-text-muted py-8">
                  <p>No signals available</p>
                  <button onClick={fetchSignals} className="mt-4 px-4 py-2 bg-neon-cyan/20 border border-neon-cyan rounded text-neon-cyan">
                    Scan for Signals
                  </button>
                </div>
              ) : (
                signals.map((signal: any, index: number) => (
                  <div key={index} className="glass rounded-xl border border-glow-border p-4">
                    <h3 className="font-bold text-white">{signal.symbol}</h3>
                    <p className="text-sm">Signal: {signal.signal}</p>
                    <p className="text-sm">Confidence: {signal.confidence}%</p>
                    <p className="text-sm">RSI: {signal.rsi}</p>
                    <p className="text-sm">EMA Trend: {signal.ema_trend}</p>
                    <p className="text-sm">Price: {signal.price}</p>
                  </div>
                ))
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}