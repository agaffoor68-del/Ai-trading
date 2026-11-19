"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { AlertCircle, Loader2, Maximize2, Wifi } from "lucide-react";
import { useOptionChain, useExpiries, SERVER_WAKING_MESSAGE } from "@/lib/hooks";

const OPTIONS_SYMBOLS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"];

export function OptionsChain() {
  const [symbol, setSymbol] = useState("NIFTY");
  const [expiry, setExpiry] = useState("");
  const [strikeCount, setStrikeCount] = useState(10);
  const { expiries, isLoading: expiriesLoading } = useExpiries(symbol);
  useEffect(() => {
    if (expiries.length && (!expiry || !expiries.includes(expiry))) setExpiry(expiries[0]);
  }, [expiries, expiry]);

  const { chainData, isLoading, isError, error, isFyersNotConnected, isFyersConnected, isServerWakingUp, mutate } = useOptionChain(symbol, expiry, strikeCount);
  const rows = useMemo(() => {
    if (Array.isArray(chainData?.option_chain)) return chainData.option_chain;
    if (Array.isArray(chainData?.data)) return chainData.data;
    return [];
  }, [chainData]);
  const showConnect = isFyersNotConnected && !isFyersConnected;

  return (
    <section className="glass flex min-h-[350px] flex-col overflow-hidden rounded-2xl border border-glow-border">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-glow-border bg-card-bg/50 px-4 py-3">
        <div className="flex items-center gap-2"><h3 className="font-semibold text-white">Options Chain</h3><span className="rounded bg-neon-cyan/20 px-2 py-0.5 text-xs text-neon-cyan">{symbol}</span></div>
        <div className="flex flex-wrap items-center gap-2">
          <select aria-label="Index" value={symbol} onChange={(event) => { setSymbol(event.target.value); setExpiry(""); }} className="rounded-lg border border-glow-border bg-card-bg px-2 py-1.5 text-sm text-white">{OPTIONS_SYMBOLS.map((item) => <option key={item} value={item}>{item}</option>)}</select>
          <select aria-label="Expiry" value={expiry} onChange={(event) => setExpiry(event.target.value)} disabled={expiriesLoading || !expiries.length} className="rounded-lg border border-glow-border bg-card-bg px-2 py-1.5 text-sm text-white"><option value="">{expiriesLoading ? "Loading expiries…" : "Select expiry"}</option>{expiries.map((item) => <option key={item} value={item}>{item}</option>)}</select>
          <select aria-label="Strike range" value={strikeCount} onChange={(event) => setStrikeCount(Number(event.target.value))} className="rounded-lg border border-glow-border bg-card-bg px-2 py-1.5 text-sm text-white">{[5, 10, 15, 20].map((item) => <option key={item} value={item}>{item} ITM/OTM</option>)}</select>
          <button type="button" onClick={() => mutate()} title="Refresh option chain" className="rounded-lg border border-glow-border p-2 text-text-secondary"><Maximize2 className="h-4 w-4" /></button>
        </div>
      </header>
      {showConnect ? <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center"><AlertCircle className="h-9 w-9 text-neon-orange" /><p className="font-semibold text-white">Fyers is not connected</p><p className="text-sm text-text-muted">Reconnect Fyers to retrieve the option chain.</p><a href="/broker-connect" className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple px-5 py-3 font-bold text-true-black"><Wifi className="h-4 w-4" />Connect Fyers</a></div>
        : isLoading || expiriesLoading ? <div className="flex flex-1 items-center justify-center gap-2 text-text-secondary"><Loader2 className="h-5 w-5 animate-spin" />Loading Options…</div>
        : isError ? <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center"><AlertCircle className="h-8 w-8 text-neon-orange" /><p className="text-white">{isServerWakingUp ? SERVER_WAKING_MESSAGE : "Could not load option data"}</p><p className="text-sm text-text-muted">{error}</p></div>
        : rows.length === 0 ? <div className="flex flex-1 items-center justify-center p-8 text-center text-text-muted">No Option Data Available</div>
        : <div className="flex-1 overflow-auto p-2"><table className="w-full min-w-[640px] text-sm"><thead><tr className="sticky top-0 border-b border-glow-border bg-card-bg text-text-muted"><th className="p-2 text-right">Call LTP</th><th className="p-2 text-right">Call OI</th><th className="p-2 text-center">Strike</th><th className="p-2 text-right">Put OI</th><th className="p-2 text-right">Put LTP</th></tr></thead><tbody>{rows.map((row: any) => { const call = row.call ?? row.ce ?? {}; const put = row.put ?? row.pe ?? {}; const strike = Number(row.strike); return <motion.tr key={strike} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className={`border-b border-glow-border/50 ${row.is_atm || row.isATM ? "bg-neon-cyan/10" : ""}`}><td className="p-2 text-right font-mono text-neon-green">{Number(call.ltp ?? 0).toFixed(2)}</td><td className="p-2 text-right font-mono text-text-secondary">{Number(call.oi ?? 0).toLocaleString()}</td><td className="p-2 text-center font-mono font-bold text-white">{Number.isFinite(strike) ? strike.toLocaleString() : "—"}{row.is_atm || row.isATM ? " · ATM" : ""}</td><td className="p-2 text-right font-mono text-text-secondary">{Number(put.oi ?? 0).toLocaleString()}</td><td className="p-2 text-right font-mono text-neon-red">{Number(put.ltp ?? 0).toFixed(2)}</td></motion.tr>; })}</tbody></table></div>}
    </section>
  );
}
