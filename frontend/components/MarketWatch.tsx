"use client";

import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Minus, Wifi, AlertCircle, Loader2 } from "lucide-react";
import { useMarketQuotes, formatFyersSymbol, SERVER_WAKING_MESSAGE } from "@/lib/hooks";

interface DisplayItem {
  symbol: string;
  name: string;
  price: number | null;
  change: number | null;
  changePercent: number | null;
  updatedAt?: string;
  priceSource: "live" | "stale" | "none";
}

const MARKET_SYMBOLS = [
  { symbol: "NIFTY 50", requestSymbol: "NSE:NIFTY50-INDEX" },
  { symbol: "BANKNIFTY", requestSymbol: "NSE:NIFTYBANK-INDEX" },
  { symbol: "HDFC BANK", requestSymbol: "NSE:HDFCBANK-EQ" },
  { symbol: "RELIANCE", requestSymbol: "NSE:RELIANCE-EQ" },
  { symbol: "TCS", requestSymbol: "NSE:TCS-EQ" },
];

export function MarketWatch() {
  const symbols = MARKET_SYMBOLS.map((item) => item.requestSymbol);
  const { quotes, response, isLoading, isError, error, isFyersNotConnected, isFyersConnected, isServerWakingUp: wakingUp, mutate } = useMarketQuotes(symbols);
  const displayItems: DisplayItem[] = MARKET_SYMBOLS.map(({ symbol, requestSymbol }) => {
    const quote = quotes[requestSymbol] ?? quotes[formatFyersSymbol(symbol)] ?? Object.values(quotes).find((item) => item.symbol === requestSymbol || item.symbol === symbol);
    const price = quote?.ltp;
    if (typeof price !== "number") return { symbol, name: symbol, price: null, change: null, changePercent: null, priceSource: "none" };
    const updatedAt = quote.updated_at;
    const stale = updatedAt ? Date.now() - new Date(updatedAt).getTime() > 60000 : false;
    return { symbol, name: symbol, price, change: typeof quote.change === "number" ? quote.change : 0, changePercent: typeof quote.change_percent === "number" ? quote.change_percent : typeof quote.changePercent === "number" ? quote.changePercent : 0, updatedAt, priceSource: stale ? "stale" : "live" };
  });

  if (isLoading) return <section className="glass rounded-2xl border border-glow-border min-h-[350px] flex items-center justify-center text-text-secondary"><Loader2 className="w-5 h-5 mr-2 animate-spin" />Loading live quotes…</section>;
  if (isError && !isFyersNotConnected) return <section className="glass rounded-2xl border border-glow-border min-h-[350px] flex flex-col items-center justify-center p-6 text-center"><AlertCircle className="w-10 h-10 mb-3 text-neon-orange/70" /><p className="text-white font-medium">{wakingUp ? SERVER_WAKING_MESSAGE : "Failed to load market data"}</p><p className="text-sm text-text-muted mt-2">{error}</p><button onClick={() => mutate()} className="mt-4 rounded-lg border border-glow-border px-4 py-2">Retry</button></section>;

  const disconnected = isFyersNotConnected && !isFyersConnected;
  const hasAnyPrice = !disconnected && displayItems.some((item) => item.price !== null);
  return <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass rounded-2xl border border-glow-border min-h-[350px] flex flex-col overflow-hidden">
    <header className="flex items-center justify-between border-b border-glow-border px-4 py-3"><h3 className="font-semibold text-white flex items-center gap-2"><TrendingUp className="w-5 h-5 text-neon-cyan" />Market Watch</h3><button onClick={() => mutate()} className="flex items-center gap-2 text-xs text-text-secondary"><span className={`h-2 w-2 rounded-full ${hasAnyPrice ? "bg-neon-green" : "bg-neon-orange"}`} />{hasAnyPrice ? "LIVE" : "REFRESH"}</button></header>
    {disconnected ? <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center"><AlertCircle className="h-10 w-10 text-neon-orange" /><p className="font-semibold text-white">Data unavailable. Please reconnect Fyers.</p>{!isFyersConnected && <a href="/broker-connect" className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple px-5 py-3 font-bold text-true-black"><Wifi className="h-4 w-4" />Connect Fyers</a>}</div> : <><div className="flex-1 divide-y divide-glow-border/50 p-2">{displayItems.map((item) => {const positive = (item.change ?? 0) >= 0; const TrendIcon = item.price === null ? Minus : positive ? TrendingUp : TrendingDown; return <div key={item.symbol} className="flex items-center justify-between rounded-xl px-3 py-3 hover:bg-card-bg/50"><div><p className="font-medium text-white">{item.symbol}</p><p className="text-[11px] text-text-muted">{item.name}</p></div><div className="text-right">{item.price !== null ? <><p className="font-mono font-semibold text-white">₹{item.price.toLocaleString()}</p><p className={`flex items-center justify-end gap-1 text-xs ${positive ? "text-neon-green" : "text-neon-red"}`}><TrendIcon className="h-3 w-3" />{positive ? "+" : ""}{item.changePercent?.toFixed(2)}% <span>({positive ? "+" : ""}₹{item.change?.toFixed(2)})</span>{item.priceSource === "stale" && <span className="text-neon-orange">STALE</span>}</p></> : <span className="text-sm text-text-muted">No live data</span>}</div></div>;})}</div>{!hasAnyPrice && <div className="border-t border-glow-border p-4 text-center text-sm text-text-muted">Data unavailable. No live market quotes returned.</div>}</>}
  </motion.section>;
}
