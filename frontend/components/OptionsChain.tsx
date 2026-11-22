"use client";

import { motion } from "framer-motion";
import { Maximize2, AlertCircle, Wifi } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useOptionChain, useExpiries, SERVER_WAKING_MESSAGE } from "@/lib/hooks";

export function OptionsChain() {
  const [selectedSymbol, setSelectedSymbol] = useState("NIFTY");
  const [selectedExpiry, setSelectedExpiry] = useState("");
  const [strikes, setStrikes] = useState(10);
  const [searchQuery, setSearchQuery] = useState("");
  const { expiries, isLoading: expiriesLoading, isError: expiriesError, error: expiriesErrorMessage, mutate: refreshExpiries } = useExpiries(selectedSymbol);
  useEffect(() => {
    if (expiries.length && (!selectedExpiry || !expiries.includes(selectedExpiry))) {
      setSelectedExpiry(expiries[0]);
    }
  }, [expiries, selectedExpiry]);

  const {
    chainData,
    isLoading,
    isError,
    error,
    isFyersNotConnected,
    isFyersConnected,
    isServerWakingUp: wakingUp,
    mutate,
  } = useOptionChain(selectedSymbol, selectedExpiry, strikes);

  const transformedStrikes = useMemo(() => {
    const rows = chainData?.option_chain ?? [];
    return rows.map((row) => ({
      strike: Number(row.strike),
      isATM: Boolean(row.is_atm),
      ceLtp: row.call?.ltp == null ? null : Number(row.call.ltp),
      ceSymbol: row.call?.symbol ?? null,
      peLtp: row.put?.ltp == null ? null : Number(row.put.ltp),
      peSymbol: row.put?.symbol ?? null,
    }));
  }, [chainData]);

  const filteredStrikes = useMemo(
    () => transformedStrikes.filter((row: any) => !searchQuery.trim() || String(row.strike).includes(searchQuery.trim())),
    [transformedStrikes, searchQuery],
  );
  const formatNumber = (value: number) => value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const showConnectButton = isFyersNotConnected && !isFyersConnected;

  if (isLoading) {
    return <section aria-label="Loading option chain" aria-busy="true" className="glass rounded-2xl border border-glow-border min-h-[350px] overflow-hidden"><header className="border-b border-glow-border px-4 py-3"><div className="h-5 w-36 rounded bg-card-bg animate-pulse" /></header><div className="flex flex-col gap-3 p-4">{Array.from({ length: 6 }, (_, index) => <div key={index} className="grid grid-cols-5 gap-3 py-2"><div className="h-4 rounded bg-card-bg animate-pulse" /><div className="h-4 rounded bg-card-bg animate-pulse" /><div className="h-4 rounded bg-card-bg animate-pulse" /><div className="h-4 rounded bg-card-bg animate-pulse" /><div className="h-4 rounded bg-card-bg animate-pulse" /></div>)}</div></section>;
  }

  if (isError && !isFyersNotConnected) {
    return <section className="glass rounded-2xl border border-glow-border min-h-[350px] flex flex-col items-center justify-center p-6 text-center"><AlertCircle className="mb-3 h-10 w-10 text-neon-orange/70" /><p className="font-medium text-white">{wakingUp ? SERVER_WAKING_MESSAGE : "Failed to load option chain"}</p><p className="mt-2 text-sm text-text-muted">{error}</p><button onClick={() => mutate()} className="mt-4 rounded-lg border border-glow-border px-4 py-2">Retry</button></section>;
  }

  return (
    <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-2xl border border-glow-border min-h-[350px] flex flex-col overflow-hidden">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-glow-border bg-card-bg/50 px-4 py-3">
        <div className="flex items-center gap-2"><h3 className="font-semibold text-white">Options Chain</h3><span className="rounded bg-neon-cyan/20 px-2 py-0.5 text-xs text-neon-cyan">{selectedSymbol}</span></div>
        <div className="flex flex-wrap items-center gap-2">
          <select aria-label="Underlying symbol" value={selectedSymbol} onChange={(event) => { setSelectedSymbol(event.target.value); setSelectedExpiry(""); }} className="rounded-lg border border-glow-border bg-card-bg px-2 py-1.5 text-sm text-white">
            {["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"].map((symbol) => <option key={symbol} value={symbol}>{symbol}</option>)}
          </select>
          <select aria-label="Expiry" value={selectedExpiry} onChange={(event) => setSelectedExpiry(event.target.value)} disabled={expiriesLoading || expiries.length === 0} className="rounded-lg border border-glow-border bg-card-bg px-2 py-1.5 text-sm text-white">
            {expiries.map((expiry) => <option key={expiry} value={expiry}>{expiry}</option>)}
          </select>
          <select aria-label="Number of strikes" value={strikes} onChange={(event) => setStrikes(Number(event.target.value))} className="rounded-lg border border-glow-border bg-card-bg px-2 py-1.5 text-sm text-white">
            {[5, 10, 15, 20].map((count) => <option key={count} value={count}>{count} strikes each side</option>)}
          </select>
          <input aria-label="Search strikes" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search strike..." className="w-32 rounded-lg border border-glow-border bg-card-bg px-2 py-1.5 text-sm text-white" />
          <button onClick={() => mutate()} title="Refresh" className="rounded-lg border border-glow-border bg-card-bg p-1.5"><Maximize2 className="h-4 w-4 text-text-secondary" /></button>
        </div>
      </header>
      {expiriesError ? (
        <div role="alert" className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center"><AlertCircle className="h-10 w-10 text-neon-orange" /><p className="font-semibold text-white">Could not load instrument information.</p><p className="text-sm text-text-muted">{expiriesErrorMessage || "Check the backend URL and Symbol Master availability."}</p><button onClick={() => refreshExpiries()} className="rounded-lg border border-glow-border px-4 py-2">Retry</button></div>
      ) : isFyersNotConnected && !isFyersConnected ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center"><AlertCircle className="h-10 w-10 text-neon-orange" /><p className="font-semibold text-white">Fyers is disconnected. Connect to load the option chain.</p>{showConnectButton && <a href="/broker-connect" className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple px-5 py-3 font-bold text-true-black"><Wifi className="h-4 w-4" />Connect Fyers</a>}</div>
      ) : filteredStrikes.length ? (
        <div className="flex-1 overflow-auto p-2"><table className="w-full min-w-[700px] text-sm"><thead className="sticky top-0 bg-card-bg/90 text-text-muted"><tr><th className="px-2 py-2 text-right">Call LTP</th><th className="px-2 py-2 text-right">Call symbol</th><th className="px-2 py-2 text-center">STRIKE</th><th className="px-2 py-2 text-left">Put symbol</th><th className="px-2 py-2 text-left">Put LTP</th></tr></thead><tbody>{filteredStrikes.map((row: any) => <tr key={row.strike} className={`border-t border-glow-border/40 hover:bg-card-bg/50 ${row.isATM ? "bg-neon-cyan/5" : ""}`}><td className="px-2 py-2 text-right font-mono text-neon-green">{row.ceLtp == null ? "—" : formatNumber(row.ceLtp)}</td><td className="max-w-[180px] truncate px-2 py-2 text-right font-mono text-text-secondary" title={row.ceSymbol ?? "No call contract"}>{row.ceSymbol ?? "—"}</td><td className={`px-2 py-2 text-center font-mono font-bold ${row.isATM ? "text-neon-cyan" : "text-white"}`}>{row.strike.toLocaleString()}{row.isATM && <span className="ml-1 text-[10px]">ATM</span>}</td><td className="max-w-[180px] truncate px-2 py-2 font-mono text-text-secondary" title={row.peSymbol ?? "No put contract"}>{row.peSymbol ?? "—"}</td><td className="px-2 py-2 text-left font-mono text-neon-red">{row.peLtp == null ? "—" : formatNumber(row.peLtp)}</td></tr>)}</tbody></table></div>
      ) : (
        <div className="flex flex-1 items-center justify-center p-6 text-center text-text-muted"><div><AlertCircle className="mx-auto mb-2 h-8 w-8 text-neon-orange/50" /><p>{transformedStrikes.length === 0 ? "No data" : "No matching strikes."}</p></div></div>
      )}
    </motion.section>
  );
}
