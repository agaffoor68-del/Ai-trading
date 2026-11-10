"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

const watchlist = [
  { symbol: "NIFTY 50", price: "24,362.75", change: "+0.84%", positive: true },
  { symbol: "BANKNIFTY", price: "52,186.40", change: "+0.41%", positive: true },
  { symbol: "RELIANCE", price: "1,426.20", change: "-0.28%", positive: false },
  { symbol: "HDFCBANK", price: "1,782.55", change: "+1.12%", positive: true },
];

const calls = [
  ["24,400", "1,284", "-", "88,420", "24.15"],
  ["24,350", "2,016", "-", "64,880", "42.80"],
  ["24,300", "3,542", "-", "48,610", "65.35"],
  ["24,250", "4,806", "-", "31,205", "91.10"],
];

function PriceChart() {
  return (
    <div className="chart-wrap" aria-label="NIFTY 50 intraday price chart">
      <div className="chart-y-axis"><span>24,400</span><span>24,350</span><span>24,300</span><span>24,250</span><span>24,200</span></div>
      <svg viewBox="0 0 760 250" role="img" aria-label="Rising green line chart">
        <defs><linearGradient id="fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#27c98a" stopOpacity=".26"/><stop offset="1" stopColor="#27c98a" stopOpacity="0"/></linearGradient></defs>
        <path d="M0 208 L55 185 L110 191 L165 145 L220 158 L275 115 L330 130 L385 84 L440 98 L495 70 L550 78 L605 38 L660 52 L760 18 L760 250 L0 250Z" fill="url(#fill)"/>
        <path d="M0 208 L55 185 L110 191 L165 145 L220 158 L275 115 L330 130 L385 84 L440 98 L495 70 L550 78 L605 38 L660 52 L760 18" fill="none" stroke="#27c98a" strokeWidth="3"/>
      </svg>
      <div className="chart-x-axis"><span>09:15</span><span>11:00</span><span>13:00</span><span>15:30</span></div>
    </div>
  );
}

export default function Home() {
  const [reconnecting, setReconnecting] = useState(false);

  useEffect(() => {
    if (!API_URL) {
      setReconnecting(true);
      return;
    }
    fetch(`${API_URL}/`, { signal: AbortSignal.timeout(5000) })
      .then((response) => { if (!response.ok) throw new Error("Backend unavailable"); })
      .catch(() => setReconnecting(true));
  }, []);

  return (
    <main className="trading-app">
      <header className="topbar">
        <div className="brand"><span className="brand-mark">◈</span><span>Trade<span className="brand-accent">Flow</span></span><span className="live-pill">LIVE</span></div>
        <nav className="main-nav" aria-label="Main navigation"><a className="active" href="#dashboard">Dashboard</a><a href="#positions">Positions</a><a href="#orders">Orders</a><a href="#analytics">Analytics</a></nav>
        <div className="account"><span className="market-open"><span className="dot" /> Market open</span><button className="avatar" aria-label="Open account menu">AK</button></div>
      </header>

      <div className="dashboard-shell">
        <section className="page-heading"><div><p className="eyebrow">MONDAY, 10 NOV 2026 <span>•</span> NSE</p><h1>Good morning, Abdul</h1><p className="muted">Here&apos;s your market overview for today.</p></div><button className="outline-button">+ Add to watchlist</button></section>
        <section className="stat-grid" aria-label="Portfolio overview"><div className="stat-card"><span>Portfolio value</span><strong>₹ 8,42,650.00</strong><small className="positive">+₹ 12,840.50 <span>today</span></small></div><div className="stat-card"><span>Day&apos;s P&amp;L</span><strong className="positive">+₹ 6,248.25</strong><small className="positive">+0.74%</small></div><div className="stat-card"><span>Available margin</span><strong>₹ 2,18,400.00</strong><small className="muted">Used 38.2%</small></div><div className="stat-card"><span>Open positions</span><strong>12</strong><small className="muted">4 profitable</small></div></section>

        <div className="content-grid">
          <section className="panel chart-panel"><div className="panel-header"><div><h2>NIFTY 50</h2><p className="instrument-price">24,362.75 <span className="positive">+204.25 (+0.84%)</span></p></div><div className="time-tabs"><button>1D</button><button>1W</button><button className="selected">1M</button><button>3M</button><button>1Y</button></div></div><PriceChart /></section>
          <section className="panel watchlist-panel"><div className="panel-header"><h2>Watchlist</h2><button className="more-button" aria-label="More watchlist options">•••</button></div><div className="watchlist">{watchlist.map((item) => <div className="watch-row" key={item.symbol}><div><strong>{item.symbol}</strong><span>NSE · Equity</span></div><div className="watch-price"><strong>{item.price}</strong><span className={item.positive ? "positive" : "negative"}>{item.change}</span></div></div>)}</div><button className="view-all">View all instruments <span>→</span></button></section>
        </div>

        <section className="panel options-panel"><div className="panel-header"><div><h2>Options chain</h2><p className="muted">NIFTY 50 <span className="dot-separator">•</span> Expiry 27 Nov 2026</p></div><div className="chain-controls"><button className="selected">Calls</button><button>Puts</button><button className="strike-select">Strike: ATM⌄</button></div></div><div className="chain-table"><div className="chain-head"><span>OI</span><span>Volume</span><span>IV</span><span>Strike</span><span>IV</span><span>Volume</span><span>OI</span></div>{calls.map((row, index) => <div className={`chain-row ${index === 2 ? "atm" : ""}`} key={row[0]}>{row.map((value, cell) => <span key={`${row[0]}-${cell}`} className={cell === 3 ? "strike" : ""}>{value}</span>)}</div>)}</div></section>
      </div>
      {reconnecting && <div className="toast" role="status"><span className="spinner" /> Reconnecting to backend...</div>}
    </main>
  );
}
