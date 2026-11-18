"use client";

import { motion } from "framer-motion";
import { Maximize2, AlertCircle, Loader2, Wifi } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useOptionChain, useExpiries, SERVER_WAKING_MESSAGE } from "@/lib/hooks";

export function OptionsChain() {
  const [selectedSymbol, setSelectedSymbol] = useState("NIFTY");
  const [selectedExpiry, setSelectedExpiry] = useState("");
  const [strikes, setStrikes] = useState(10);
  const [searchQuery, setSearchQuery] = useState("");
  const { expiries, isLoading: expiriesLoading } = useExpiries(selectedSymbol);
  useEffect(() => {
    if (expiries.length && (!selectedExpiry || !expiries.includes(selectedExpiry))) setSelectedExpiry(expiries[0]);
  }, [expiries, selectedExpiry]);

  const { chainData, isLoading, isError, error, isFyersNotConnected, isServerWakingUp: wakingUp, mutate } = useOptionChain(selectedSymbol, selectedExpiry, strikes);
  const transformedStrikes = useMemo(() => {
    const rows = Array.isArray(chainData?.option_chain) ? chainData.option_chain : Array.isArray(chainData?.data) ? chainData.data : Array.isArray(chainData) ? chainData : [];
    return rows.map((row: any) => {
      const call = row.call ?? row.ce ?? {};
      const put = row.put ?? row.pe ?? {};
      return {
        strike: Number(row.strike),
        isATM: Boolean(row.is_atm ?? row.isATM),
        callITM: Boolean(row.call_itm ?? row.callITM),
        putITM: Boolean(row.put_itm ?? row.putITM),
        ceLtp: Number(call.ltp ?? row.call_ltp ?? row.ce_ltp ?? 0),
        ceOI: Number(call.oi ?? row.call_oi ?? 0),
        ceOIChange: Number(call.oi_change_pct ?? row.call_oi_change_pct ?? 0),
        peLtp: Number(put.ltp ?? row.put_ltp ?? row.pe_ltp ?? 0),
        peOI: Number(put.oi ?? row.put_oi ?? 0),
        peOIChange: Number(put.oi_change_pct ?? row.put_oi_change_pct ?? 0),
      };
    }).filter((row: any) => Number.isFinite(row.strike));
  }, [chainData]);

  const filteredStrikes = useMemo(() => transformedStrikes.filter((row: any) => !searchQuery.trim() || String(row.strike).includes(searchQuery.trim())), [transformedStrikes, searchQuery]);
  const formatNumber = (value: number) => value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  if (isLoading) return <section className="glass rounded-2xl border border-glow-border min-h-[350px] flex items-center justify-center text-text-secondary"><Loader2 className="mr-2 h-5 w-5 animate-spin" />Loading option chain…</section>;
  if (isError) return <section className="glass rounded-2xl border border-glow-border min-h-[350px] flex flex-col items-center justify-center p-6 text-center"><AlertCircle className="mb-3 h-9 w-9 text-neon-orange/70" /><p className="font-medium text-white">{wakingUp ? SERVER_WAKING_MESSAGE : isFyersNotConnected ? "Fyers is not connected" : "Failed to load option chain"}</p><p className="mt-2 text-sm text-text-muted">{error}</p>{isFyersNotConnected ? <a href="/broker-connect" className="mt-4 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple px-4 py-2 font-bold text-true-black"><Wifi className="h-4 w-4" />Connect Fyers</a> : <button onClick={() => mutate()} className="mt-4 rounded-lg border border-glow-border px-4 py-2">Retry</button>}</section>;

  return <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-2xl border border-glow-border min-h-[350px] flex flex-col overflow-hidden">
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-glow-border bg-card-bg/50 px-4 py-3">
      <div className="flex items-center gap-2"><h3 className="font-semibold text-white">Options Chain</h3><span className="rounded bg-neon-cyan/20 px-2 py-0.5 text-[10px] text-neon-cyan">{selectedSymbol}</span>{chainData?.expiry && <span className="rounded bg-neon-orange/20 px-2 py-0.5 text-[10px] text-neon-orange">{chainData.expiry}</span>}</div>
      <div className="flex flex-wrap items-center gap-2">
        <select value={selectedSymbol} onChange={(event) => { setSelectedSymbol(event.target.value); setSelectedExpiry(""); }} className="rounded-lg border border-glow-border bg-card-bg px-2 py-1.5 text-sm text-white">{["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"].map((symbol) => <option key={symbol}>{symbol}</option>)}</select>
        <select value={selectedExpiry} onChange={(event) => setSelectedExpiry(event.target.value)} disabled={expiriesLoading || !expiries.length} className="rounded-lg border border-glow-border bg-card-bg px-2 py-1.5 text-sm text-white"><option value="">Select expiry</option>{expiries.map((expiry) => <option key={expiry} value={expiry}>{expiry}</option>)}</select>
        <select value={strikes} onChange={(event) => setStrikes(Number(event.target.value))} className="rounded-lg border border-glow-border bg-card-bg px-2 py-1.5 text-sm text-white">{[5, 10, 15, 20].map((count) => <option key={count} value={count}>{count} ITM/OTM</option>)}</select>
        <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search strike…" className="w-32 rounded-lg border border-glow-border bg-card-bg px-2 py-1.5 text-sm text-white" />
        <button onClick={() => mutate()} title="Refresh" className="rounded-lg border border-glow-border p-2 text-text-secondary"><Maximize2 className="h-4 w-4" /></button>
      </div>
    </header>
    {filteredStrikes.length ? <div className="flex-1 overflow-auto p-2"><table className="w-full min-w-[700px] text-sm"><thead className="sticky top-0 bg-card-bg/90 text-text-muted"><tr><th className="px-2 py-2 text-right">Call LTP</th><th className="px-2 py-2 text-right">Call OI</th><th className="px-2 py-2 text-center">STRIKE</th><th className="px-2 py-2 text-right">Put OI</th><th className="px-2 py-2 text-right">Put LTP</th></tr></thead><tbody>{filteredStrikes.map((row: any) => <tr key={row.strike} className={`border-t border-glow-border/40 hover:bg-card-bg/50 ${row.isATM ? "bg-neon-cyan/5" : ""}`}><td className="px-2 py-2 text-right font-mono text-neon-green">{formatNumber(row.ceLtp)}</td><td className="px-2 py-2 text-right font-mono text-text-secondary">{row.ceOI.toLocaleString()}</td><td className={`px-2 py-2 text-center font-mono font-bold ${row.isATM ? "text-neon-cyan" : "text-white"}`}>{row.strike.toLocaleString()}{row.isATM && <span className="ml-1 text-[10px]">ATM</span>}</td><td className="px-2 py-2 text-right font-mono text-text-secondary">{row.peOI.toLocaleString()}</td><td className="px-2 py-2 text-right font-mono text-neon-red">{formatNumber(row.peLtp)}</td></tr>)}</tbody></table></div> : <div className="flex flex-1 items-center justify-center p-6 text-center text-text-muted"><div><AlertCircle className="mx-auto mb-2 h-8 w-8 text-neon-orange/50" /><p>{chainData ? "No option strikes are available for this expiry." : "Select an expiry to load the option chain."}</p>{isFyersNotConnected && <a href="/broker-connect" className="mt-3 inline-flex items-center gap-1 text-neon-cyan"><Wifi className="h-4 w-4" />Connect Fyers</a>}</div></div>}
  </motion.section>;
}
