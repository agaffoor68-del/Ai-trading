"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

const watchlist = [
  { symbol: "NIFTY 50", exchange: "NSE", price: "24,839.10", change: "+0.82%", positive: true, line: "12,22 25,20 38,24 51,14 64,18 78,10 91,12 104,5 118,8" },
  { symbol: "BANKNIFTY", exchange: "NSE", price: "51,244.65", change: "+1.14%", positive: true, line: "12,25 25,20 38,22 51,17 64,19 78,9 91,13 104,7 118,9" },
  { symbol: "RELIANCE", exchange: "NSE", price: "1,428.30", change: "+0.42%", positive: true, line: "12,21 25,18 38,20 51,15 64,17 78,13 91,15 104,8 118,11" },
  { symbol: "HDFCBANK", exchange: "NSE", price: "1,704.90", change: "-0.18%", positive: false, line: "12,9 25,13 38,10 51,17 64,14 78,20 91,17 104,23 118,21" },
  { symbol: "TCS", exchange: "NSE", price: "3,921.25", change: "+0.64%", positive: true, line: "12,22 25,25 38,16 51,18 64,11 78,14 91,7 104,10 118,5" },
  { symbol: "INFY", exchange: "NSE", price: "1,882.70", change: "-0.31%", positive: false, line: "12,8 25,12 38,10 51,16 64,12 78,19 91,14 104,22 118,18" },
];

const options = [
  ["24,700", "12.40", "-0.62", "98.15", "102.20", "+1.18"],
  ["24,750", "22.15", "-0.84", "143.80", "147.50", "+1.36"],
  ["24,800", "38.90", "-1.12", "202.65", "207.10", "+1.58"],
  ["24,850", "64.30", "+0.24", "274.40", "281.90", "-0.92"],
  ["24,900", "104.80", "+1.08", "362.50", "370.20", "-0.64"],
];

function Sparkline({ points, positive }: { points: string; positive: boolean }) {
  return <svg viewBox="0 0 130 30" className="h-7 w-[84px]" aria-hidden="true"><polyline points={points} fill="none" stroke={positive ? "#00ff66" : "#ff003c"} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

function Panel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`panel ${className}`}>{children}</section>;
}

export default function Home() {
  const [status, setStatus] = useState<string | null>(null);
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");

  useEffect(() => {
    fetch(`${API_URL}/`).then((res) => res.json()).then((data) => setStatus(data?.status ?? "connected")).catch(() => setStatus("offline"));
  }, []);

  return (
    <main className="min-h-screen bg-[#000] px-4 py-4 text-white md:px-6 lg:px-8">
      <header className="mx-auto flex max-w-[1800px] flex-wrap items-center gap-4 border-b border-[#1d2428] pb-4">
        <div className="flex items-center gap-3 pr-3"><div className="logo-mark">A</div><div><p className="font-mono text-sm font-bold tracking-[0.28em] text-[#00f0ff]">ALPHATRADE</p><p className="font-mono text-[9px] tracking-[0.35em] text-[#768087]">PRO TERMINAL // 01</p></div></div>
        <div className="flex min-w-[220px] flex-1 items-center rounded-md border border-[#263139] bg-[#0a0a0a] px-3 py-2 text-xs text-[#697980] shadow-[inset_0_0_20px_rgba(0,240,255,.03)]"><span className="mr-2 text-[#00f0ff]">⌕</span><span className="font-mono">Search symbol, strategy or command...</span><span className="ml-auto rounded border border-[#33424a] px-1.5 py-0.5 text-[9px]">⌘ K</span></div>
        <div className="flex items-center gap-4 font-mono text-[10px] text-[#9ca9ae]"><span className="flex items-center gap-2"><i className="status-dot" /> FYERS <b className="text-[#00ff66]">CONNECTED</b></span><span className="flex items-center gap-2"><i className="status-dot" /> API <b className="text-[#00ff66]">LIVE</b></span><button className="rounded border border-[#263139] px-3 py-2 text-[#aab7bb] hover:border-[#00f0ff] hover:text-[#00f0ff]">⌄</button></div>
      </header>

      <div className="ticker-wrap mx-auto mt-3 max-w-[1800px] overflow-hidden border-y border-[#172126] bg-[#050707] py-2"><div className="ticker-track flex min-w-max gap-12 font-mono text-[11px]"><span>NIFTY 50 <b className="text-white">24,839.10</b> <em className="up">+201.45 (+0.82%)</em></span><span>BANKNIFTY <b className="text-white">51,244.65</b> <em className="up">+578.60 (+1.14%)</em></span><span>SENSEX <b className="text-white">81,786.25</b> <em className="up">+602.75 (+0.74%)</em></span><span>INDIA VIX <b className="text-white">13.82</b> <em className="down">-0.42 (-2.94%)</em></span><span>USDINR <b className="text-white">83.94</b> <em className="down">-0.08 (-0.10%)</em></span></div></div>

      <div className="mx-auto mt-4 grid max-w-[1800px] gap-4 xl:grid-cols-[20%_50%_30%]">
        <Panel><div className="panel-heading"><div><p className="eyebrow">01 / MARKET WATCH</p><h2>Watchlist <span className="text-[#66767d]">(06)</span></h2></div><button className="icon-button">＋</button></div><div className="watch-tabs"><span className="active">All</span><span>Indices</span><span>Equities</span></div><div className="space-y-1">{watchlist.map((item, i) => <motion.div whileHover={{ x: 3, backgroundColor: "#10181a" }} key={item.symbol} className="watch-row"><div className="min-w-0"><p className="truncate font-mono text-[11px] font-bold">{item.symbol}</p><p className="font-mono text-[9px] text-[#68777c]">{item.exchange} <span className="text-[#36464b]">•</span> {i % 2 === 0 ? "EQ" : "FO"}</p></div><Sparkline points={item.line} positive={item.positive} /><div className="text-right"><p className="font-mono text-[11px]">{item.price}</p><p className={`font-mono text-[10px] ${item.positive ? "up" : "down"}`}>{item.change}</p></div></motion.div>)}</div><div className="mt-3 border-t border-[#1d272a] pt-3 font-mono text-[9px] text-[#617177]">MARKET OPEN <span className="float-right text-[#00ff66]">● 02:41:38</span></div></Panel>

        <div className="space-y-4"><Panel className="overflow-hidden"><div className="panel-heading"><div><p className="eyebrow">02 / PRICE ACTION</p><h2>NIFTY 50 <span className="text-base text-[#00ff66]">+0.82%</span></h2></div><div className="flex gap-1">{["1m", "5m", "15m", "1h", "1D"].map((t) => <button key={t} className={`time-pill ${t === "5m" ? "selected" : ""}`}>{t}</button>)}</div></div><div className="chart-toolbar"><span className="font-mono text-[10px] text-[#64757a]">NIFTY · NSE · 5 MINUTES</span><span className="font-mono text-[10px] text-[#00f0ff]">EMA 20　 RSI 14　⌗</span></div><div className="chart-area"><div className="chart-grid" /><svg viewBox="0 0 800 270" preserveAspectRatio="none" className="absolute inset-0 h-full w-full"><defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#00f0ff" stopOpacity=".2" /><stop offset="1" stopColor="#00f0ff" stopOpacity="0" /></linearGradient></defs><path d="M0 220 L35 195 L70 210 L105 170 L140 180 L175 140 L210 155 L245 115 L280 132 L315 98 L350 120 L385 105 L420 150 L455 128 L490 145 L525 90 L560 105 L595 64 L630 86 L665 55 L700 76 L735 40 L770 57 L800 25 V270 H0Z" fill="url(#fill)" /><path d="M0 220 L35 195 L70 210 L105 170 L140 180 L175 140 L210 155 L245 115 L280 132 L315 98 L350 120 L385 105 L420 150 L455 128 L490 145 L525 90 L560 105 L595 64 L630 86 L665 55 L700 76 L735 40 L770 57 L800 25" fill="none" stroke="#00f0ff" strokeWidth="2" /></svg><span className="chart-price">24,839.10</span><span className="chart-time">10:35</span></div><div className="flex items-center justify-between border-t border-[#1c282d] px-4 py-3 font-mono text-[10px] text-[#728188]"><span>O 24,771.30　H 24,854.90　L 24,720.10　C 24,839.10</span><span className="text-[#00ff66]">+201.45</span></div></Panel>

          <Panel className="overflow-hidden"><div className="panel-heading"><div><p className="eyebrow">03 / DERIVATIVES</p><h2>Options Chain <span className="text-xs text-[#64757a]">NIFTY · 26 JUN</span></h2></div><button className="text-xs text-[#00f0ff]">View full chain ↗</button></div><div className="options-table"><div className="options-head"><span>CALLS</span><span>STRIKE</span><span>PUTS</span></div>{options.map((row, i) => <div className={`options-row ${i === 2 ? "atm" : ""}`} key={row[0]}><span className={i > 2 ? "down" : "up"}>{row[1]} <i>{row[2]}</i></span><b>{row[0]}{i === 2 && <small> ATM</small>}</b><span className={i > 2 ? "up" : "down"}>{row[3]} <i>{row[5]}</i></span></div>)}</div></Panel></div>

        <div className="space-y-4"><Panel className="ai-card"><div className="panel-heading"><div><p className="eyebrow cyan">04 / INTELLIGENCE</p><h2>Grok AI Signal</h2></div><span className="ai-live">● LIVE</span></div><div className="ai-signal"><div><p className="font-mono text-[10px] text-[#78939a]">NIFTY 50 · INTRADAY</p><p className="mt-1 text-3xl font-black tracking-tight text-[#00f0ff]">BULLISH</p></div><div className="signal-score"><strong>87</strong><span>/ 100</span></div></div><div className="confidence-bar"><span /></div><p className="mt-4 text-xs leading-relaxed text-[#b2c4c9]">Momentum is accelerating above VWAP with strong breadth. Smart money flow suggests a continuation toward <b className="text-white">24,920</b>.</p><div className="mt-4 grid grid-cols-3 gap-2 border-t border-[#14545b] pt-3 font-mono text-[9px] text-[#719098]"><span>CONFIDENCE <b className="block text-[#00ff66]">HIGH</b></span><span>HORIZON <b className="block text-white">2–4 HRS</b></span><span>RISK <b className="block text-[#ffc247]">MEDIUM</b></span></div><button className="ai-action">View reasoning ↗</button></Panel>
          <Panel><div className="panel-heading"><div><p className="eyebrow">05 / EXECUTION</p><h2>Order Ticket</h2></div><span className="font-mono text-[9px] text-[#00ff66]">● READY</span></div><div className="toggle"><button onClick={() => setSide("BUY")} className={side === "BUY" ? "buy-active" : ""}>BUY</button><button onClick={() => setSide("SELL")} className={side === "SELL" ? "sell-active" : ""}>SELL</button></div><label className="field-label">INSTRUMENT<input value="NIFTY 24,850 CE" readOnly /></label><div className="grid grid-cols-2 gap-2"><label className="field-label">QUANTITY<input value="50" readOnly /></label><label className="field-label">ORDER TYPE<select defaultValue="LIMIT"><option>LIMIT</option><option>MARKET</option></select></label></div><label className="field-label">LIMIT PRICE<div className="input-suffix"><input value="274.40" readOnly /><span>₹</span></div></label><div className="flex items-center justify-between py-2 font-mono text-[10px] text-[#728188]"><span>EST. MARGIN</span><b className="text-white">₹13,720.00</b></div><motion.button whileTap={{ scale: .98 }} className={`execute ${side === "SELL" ? "execute-sell" : ""}`}>CONFIRM {side} ORDER <span>↗</span></motion.button><p className="mt-3 text-center font-mono text-[9px] text-[#536269]">Orders routed via FYERS · RMS protected</p></Panel></div>
      </div>
      <footer className="mx-auto mt-5 flex max-w-[1800px] justify-between border-t border-[#141c1f] pt-3 font-mono text-[9px] text-[#4e5b60]"><span>ALPHATRADEPRO // HDR OLED TERMINAL</span><span>BACKEND <b className={status === "offline" ? "down" : "up"}>● {status === "offline" ? "CHECK" : "HEALTHY"}</b></span><span>v2.4.1 · NSE DATA DELAY 0.02s</span></footer>
    </main>
  );
}
