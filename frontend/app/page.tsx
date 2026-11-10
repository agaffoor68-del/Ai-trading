'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Activity, Bell, ChevronDown, CircleDollarSign, Command, Cpu, Gauge, LockKeyhole, Search, Settings2, ShieldCheck, Sparkles, TrendingDown, TrendingUp, Wifi } from 'lucide-react'

const ticker = [
  ['NIFTY 50', '23,145.50', '+0.84%', 'up'],
  ['BANKNIFTY', '49,280.10', '-0.36%', 'down'],
  ['SENSEX', '76,810.20', '+0.62%', 'up'],
  ['FINNIFTY', '22,345.80', '+1.12%', 'up'],
]
const watchlist: [string, string, string, 'up' | 'down', number[]][] = [
  ['NIFTY 50', '23,145.50', '+0.84%', 'up', [12, 16, 14, 22, 19, 27, 24, 32]],
  ['BANKNIFTY', '49,280.10', '-0.36%', 'down', [30, 24, 29, 19, 25, 18, 22, 16]],
  ['RELIANCE', '2,876.40', '+1.48%', 'up', [11, 15, 12, 20, 18, 24, 27, 31]],
  ['HDFCBANK', '1,642.75', '+0.22%', 'up', [19, 16, 18, 15, 21, 20, 23, 25]],
  ['INFY', '1,489.30', '-0.78%', 'down', [28, 23, 25, 19, 21, 17, 19, 14]],
  ['TCS', '3,921.80', '+0.56%', 'up', [14, 18, 16, 21, 20, 25, 23, 28]],
]
const options = [
  ['23000', '182.40', '+12.4%', '68.20', '-8.2%'], ['23050', '148.75', '+9.1%', '92.10', '-4.6%'],
  ['23100', '116.30', '+6.8%', '120.45', '-2.1%'], ['23150', '88.55', '+3.2%', '156.80', '+1.8%'],
  ['23200', '64.20', '-2.6%', '201.35', '+6.4%'], ['23250', '45.10', '-6.9%', '249.70', '+11.2%'],
]

function Sparkline({ points, down }: { points: number[]; down?: boolean }) {
  const max = Math.max(...points), min = Math.min(...points)
  const path = points.map((p, i) => `${(i / (points.length - 1)) * 72},${30 - ((p - min) / (max - min || 1)) * 25}`).join(' ')
  return <svg viewBox="0 0 72 32" className="spark" aria-hidden="true"><polyline points={path} fill="none" stroke={down ? '#ff003c' : '#00ff66'} strokeWidth="1.7" /></svg>
}

function Chart() {
  return <div className="chart-wrap">
    <div className="chart-grid" />
    <svg viewBox="0 0 760 280" preserveAspectRatio="none" className="price-chart" aria-label="NIFTY price chart">
      <defs><linearGradient id="fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#00f0ff" stopOpacity=".18" /><stop offset="1" stopColor="#00f0ff" stopOpacity="0" /></linearGradient></defs>
      <path d="M0 220 C45 212 55 180 92 195 S145 158 180 174 S226 133 262 145 S309 112 340 127 S380 90 420 115 S462 92 495 100 S535 62 570 84 S620 52 650 67 S705 30 760 46 L760 280 L0 280Z" fill="url(#fill)" />
      <path d="M0 220 C45 212 55 180 92 195 S145 158 180 174 S226 133 262 145 S309 112 340 127 S380 90 420 115 S462 92 495 100 S535 62 570 84 S620 52 650 67 S705 30 760 46" fill="none" stroke="#00f0ff" strokeWidth="2.5" />
      <line x1="0" y1="106" x2="760" y2="106" stroke="#ffcc00" strokeDasharray="6 5" opacity=".5" />
      <circle cx="705" cy="52" r="4" fill="#00f0ff" /><circle cx="705" cy="52" r="10" fill="#00f0ff" opacity=".16" />
    </svg>
    <div className="chart-labels"><span>23,400</span><span>23,300</span><span className="atm-label">23,145.50 ATM</span><span>23,000</span></div>
    <div className="chart-time">09:15 <span>10:00</span><span>11:00</span><span>12:00</span><span>13:00</span><span>14:30</span></div>
  </div>
}

export default function Home() {
  const [selected, setSelected] = useState('NIFTY 50')
  const [timeframe, setTimeframe] = useState('5m')
  const [side, setSide] = useState('BUY')
  const [search, setSearch] = useState('')
  const [executed, setExecuted] = useState(false)
  return <main className="terminal-shell">
    <header className="topbar">
      <div className="brand"><div className="brand-mark"><Activity size={16} /></div><div><div className="brand-name">ALPHATRADE <span>PRO</span></div><div className="brand-sub"><i /> MARKETS // INSTITUTIONAL TERMINAL</div></div></div>
      <div className="search-box"><Search size={15} /><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search symbol, contract or strategy..." /><kbd>⌘ K</kbd></div>
      <div className="top-actions"><div className="connection"><Wifi size={14} /><span className="status-dot" /> BROKER CONNECTED</div><Bell size={17} className="muted-icon" /><Settings2 size={17} className="muted-icon" /><div className="avatar">AK</div><ChevronDown size={14} className="muted-icon" /></div>
    </header>
    <div className="ticker-tape"><div className="ticker-track">{[...ticker, ...ticker].map((item, i) => <div className="ticker-item" key={i}><span className="ticker-name">{item[0]}</span><strong>{item[1]}</strong><span className={item[3] === 'up' ? 'up' : 'down'}>{item[3] === 'up' ? '↗' : '↘'} {item[2]}</span></div>)}</div></div>
    <div className="workspace">
      <aside className="panel watch-panel"><div className="panel-heading"><span>WATCHLIST</span><button aria-label="Add watchlist item">+</button></div><div className="watch-tabs"><span className="active">FAVORITES <b>06</b></span><span>SECTORS</span></div>{watchlist.map(item => <button className={`watch-row ${selected === item[0] ? 'selected' : ''}`} onClick={() => setSelected(item[0])} key={item[0]}><div className="watch-main"><span className="symbol">{item[0]}</span><span className="price">{item[1]}</span></div><Sparkline points={item[4] as number[]} down={item[3] === 'down'} /><span className={item[3] === 'up' ? 'up' : 'down'}>{item[2]}</span></button>)}<div className="watch-footer"><span><span className="live-dot" /> MARKET OPEN</span><span>IST 14:32:08</span></div></aside>
      <section className="center-column"><div className="panel chart-panel"><div className="section-head"><div><div className="eyebrow"><span className="cyan-line" /> NSE // CASH MARKET</div><h1>{selected} <small>INDEX</small></h1></div><div className="quote"><strong>23,145.50</strong><span className="up">+193.20&nbsp; +0.84%</span></div></div><div className="chart-toolbar"><div className="timeframes">{['1m', '5m', '15m', '1H', '1D'].map(t => <button className={timeframe === t ? 'active' : ''} onClick={() => setTimeframe(t)} key={t}>{t}</button>)}</div><div className="chart-tools"><span><CircleDollarSign size={13} /> Indicators</span><span><Command size={13} /> Compare</span><span>⌁</span></div></div><Chart /></div>
        <div className="panel options-panel"><div className="section-head compact"><div><div className="eyebrow"><span className="pink-line" /> DERIVATIVES // OPTIONS CHAIN</div><h2>NIFTY 50 <small>EXPIRY 28 NOV 2024</small></h2></div><div className="chain-actions"><span className="mini-live"><i /> LIVE DATA</span><button>⌘</button><button>⋮</button></div></div><div className="chain-table"><div className="chain-header"><span>CALLS (CE)</span><span>STRIKE PRICE</span><span>PUTS (PE)</span></div>{options.map((row, i) => <div className={`chain-row ${i === 3 ? 'atm' : ''}`} key={row[0]}><div className="call-cell"><b>{row[1]}</b><span>{row[2]}</span><small>OI {['12.4L', '8.1L', '15.2L', '19.8L', '10.1L', '6.4L'][i]}</small></div><strong className="strike">{row[0]} {i === 3 && <em>ATM</em>}</strong><div className="put-cell"><b>{row[3]}</b><span className={i > 2 ? 'up' : 'down'}>{row[4]}</span><small>OI {['7.9L', '9.4L', '18.7L', '21.2L', '13.6L', '5.8L'][i]}</small></div></div>)}</div></div>
      </section>
      <aside className="right-column"><motion.div className="panel signal-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}><div className="signal-top"><span className="ai-chip"><Cpu size={13} /> GROK AI // SIGNAL</span><span className="signal-live"><i /> LIVE</span></div><div className="signal-title">AI Signal: <strong>BUY</strong><br /><span>NIFTY 23100 CE</span></div><div className="confidence"><div className="confidence-label"><span>CONFIDENCE SCORE</span><b>85.4%</b></div><div className="progress"><motion.i initial={{ width: 0 }} animate={{ width: '85.4%' }} /></div></div><div className="signal-stats"><div><span>BIAS</span><b className="up">BULLISH</b></div><div><span>HORIZON</span><b>15 MIN</b></div><div><span>RISK</span><b className="amber">MODERATE</b></div></div><button className="execute-btn" onClick={() => setExecuted(true)}>{executed ? 'ORDER QUEUED ✓' : 'EXECUTE TRADE'} <TrendingUp size={15} /></button></motion.div>
        <motion.div className="panel ticket-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0, transition: { delay: .08 } }}><div className="ticket-head"><div><div className="eyebrow"><span className="green-line" /> ORDER TICKET</div><h2>NIFTY 23100 CE</h2></div><ShieldCheck size={18} className="shield" /></div><div className="side-toggle"><button className={side === 'BUY' ? 'buy-active' : ''} onClick={() => setSide('BUY')}>BUY <TrendingUp size={14} /></button><button className={side === 'SELL' ? 'sell-active' : ''} onClick={() => setSide('SELL')}>SELL <TrendingDown size={14} /></button></div><div className="form-grid"><label>ORDER TYPE<select><option>MARKET</option><option>LIMIT</option></select></label><label>PRODUCT<select><option>INTRADAY</option><option>DELIVERY</option></select></label><label>PRICE<div className="input-wrap"><input defaultValue="116.30" /><span>₹</span></div></label><label>QUANTITY<div className="input-wrap"><input defaultValue="50" /><span>QTY</span></div></label><label>STOP LOSS<div className="input-wrap"><input defaultValue="98.00" /><span>₹</span></div></label><label>TARGET<div className="input-wrap"><input defaultValue="156.00" /><span>₹</span></div></label></div><div className="order-summary"><span>EST. MARGIN <b>₹ 5,815.00</b></span><span>RISK / REWARD <b className="up">1 : 2.8</b></span></div><button className={`place-btn ${side === 'SELL' ? 'sell-button' : ''}`} onClick={() => setExecuted(true)}><LockKeyhole size={14} /> PLACE {side} ORDER</button><div className="secure-note"><Sparkles size={12} /> Smart execution enabled · Slippage protected</div></motion.div></aside>
    </div><footer className="statusbar"><span><span className="live-dot" /> DATA FEED: NSE EQUITIES</span><span>LATENCY <b className="up">12ms</b></span><span>API STATUS <b className="up">OPERATIONAL</b></span><span className="footer-right">ALPHATRADE PRO v2.4.1 · ENCRYPTED SESSION</span></footer>
  </main>
}
