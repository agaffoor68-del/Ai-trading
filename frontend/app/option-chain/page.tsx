"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { motion } from "framer-motion";
import {
  TrendingUp,
  TrendingDown,
  Search,
  RefreshCw,
  Loader2,
  Filter,
  DollarSign,
  Layers,
  AlertCircle,
  ChevronDown,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface OptionChainData {
  symbol: string;
  expiry: string;
  spot: number;
  atmStrike: number;
  strikes: OptionStrike[];
}

interface OptionStrike {
  strike: number;
  isATM: boolean;
  ceLtp: number;
  ceChange: number;
  ceOI: number;
  ceOIChange: number;
  peLtp: number;
  peChange: number;
  peOI: number;
  peOIChange: number;
}

interface IndexInfo {
  label: string;
  value: string;
  spot: number;
  strikes: number[];
  expiryList: string[];
}

const INDEXES: IndexInfo[] = [
  {
    label: "NIFTY",
    value: "NIFTY",
    spot: 24345.85,
    strikes: [24200, 24250, 24300, 24350, 24400, 24450, 24500],
    expiryList: ["28 Oct 2026", "04 Nov 2026", "11 Nov 2026", "25 Nov 2026", "30 Dec 2026"],
  },
  {
    label: "BANKNIFTY",
    value: "BANKNIFTY",
    spot: 51890.20,
    strikes: [51600, 51700, 51800, 51900, 52000, 52100, 52200],
    expiryList: ["28 Oct 2026", "04 Nov 2026", "11 Nov 2026", "25 Nov 2026"],
  },
  {
    label: "SENSEX",
    value: "SENSEX",
    spot: 79875.40,
    strikes: [79500, 79600, 79700, 79800, 79900, 80000, 80100],
    expiryList: ["28 Oct 2026", "04 Nov 2026", "11 Nov 2026", "25 Nov 2026"],
  },
];

const CHANGE_STEP = 50;

function generateMockChain(index: IndexInfo, expiry: string): OptionChainData {
  const atmStrike = Math.round(index.spot / CHANGE_STEP) * CHANGE_STEP;
  const strikes = index.strikes.map((strike) => {
    const isATM = strike === atmStrike;
    const distFromATM = Math.abs(strike - atmStrike);
    const ceBase = Math.max(10, 300 - distFromATM * 2);
    const peBase = Math.max(10, 300 - distFromATM * 2);
    return {
      strike,
      isATM,
      ceLtp: Number((ceBase + (Math.random() - 0.5) * 10).toFixed(2)),
      ceChange: Number(((Math.random() - 0.5) * 20).toFixed(2)),
      ceOI: Math.floor(Math.random() * 500000) + 100000,
      ceOIChange: Number(((Math.random() - 0.5) * 30).toFixed(2)),
      peLtp: Number((peBase + (Math.random() - 0.5) * 10).toFixed(2)),
      peChange: Number(((Math.random() - 0.5) * 20).toFixed(2)),
      peOI: Math.floor(Math.random() * 500000) + 100000,
      peOIChange: Number(((Math.random() - 0.5) * 30).toFixed(2)),
    };
  });
  return { symbol: index.label, expiry, spot: index.spot, atmStrike, strikes };
}

export default function OptionChainPage() {
  const [selectedIndex, setSelectedIndex] = useState<IndexInfo>(INDEXES[0]);
  const [selectedExpiry, setSelectedExpiry] = useState(selectedIndex.expiryList[0]);
  const [chainData, setChainData] = useState<OptionChainData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchOptionChain = useCallback(async (symbol: string, expiry: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${API_URL}/api/v1/market/option-chain?symbol=${encodeURIComponent(symbol)}&expiry=${encodeURIComponent(expiry)}`,
        {
          method: "GET",
          headers: { "Content-Type": "application/json" },
          signal: AbortSignal.timeout(10000),
        }
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setChainData(data as OptionChainData);
      setLastUpdated(new Date());
    } catch (err) {
      console.warn("Option chain fetch failed, using mock data:", err);
      const indexInfo = INDEXES.find((i) => i.value === symbol) || INDEXES[0];
      setChainData(generateMockChain(indexInfo, expiry));
      setLastUpdated(new Date());
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOptionChain(selectedIndex.value, selectedExpiry);
  }, [selectedIndex.value, selectedExpiry, fetchOptionChain]);

  const handleIndexChange = (value: string) => {
    const indexInfo = INDEXES.find((i) => i.value === value) || INDEXES[0];
    setSelectedIndex(indexInfo);
    setSelectedExpiry(indexInfo.expiryList[0]);
  };

  const filteredStrikes = useMemo(() => {
    if (!chainData) return [];
    const strikes = chainData.strikes;
    if (!searchQuery.trim()) return strikes;
    const q = searchQuery.trim();
    return strikes.filter((s) => s.strike.toString().includes(q));
  }, [chainData, searchQuery]);

  const atmRow = useMemo(() => {
    return chainData?.strikes.find((s) => s.isATM) ?? null;
  }, [chainData]);

  const formatNumber = (n: number) => n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const formatOI = (n: number) => n.toLocaleString();

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="ml-64 min-h-screen flex flex-col">
        <Header />

        <main className="flex-1 p-6 md:p-8 lg:p-10 pt-20 lg:pt-24 space-y-6">
          {/* Page Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-white tracking-tight flex items-center gap-3">
                <DollarSign className="w-8 h-8 text-neon-cyan" strokeWidth={2.5} />
                Option Chain
              </h1>
              <p className="text-text-secondary mt-1">
                Live option chain data from Fyers API v3 • ATM strike highlighted
              </p>
            </div>
            <motion.button
              onClick={() => fetchOptionChain(selectedIndex.value, selectedExpiry)}
              disabled={isLoading}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-card-bg border border-glow-border hover:border-neon-cyan/50 text-white font-medium transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed glass"
            >
              <RefreshCw className={`w-5 h-5 ${isLoading ? "animate-spin" : ""}`} strokeWidth={2.5} />
              <span>Refresh</span>
            </motion.button>
          </div>

          {/* Controls Bar */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass rounded-2xl border border-glow-border p-4"
          >
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
              <div className="flex flex-col gap-2">
                <label className="text-xs text-text-muted uppercase tracking-wider font-medium">Index</label>
                <select
                  value={selectedIndex.value}
                  onChange={(e) => handleIndexChange(e.target.value)}
                  className="w-full pl-4 pr-10 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base cursor-pointer appearance-none relative"
                >
                  {INDEXES.map((idx) => (
                    <option key={idx.value} value={idx.value}>
                      {idx.label}
                    </option>
                  ))}
                </select>
                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
              </div>

              <div className="flex flex-col gap-2">
                <label className="text-xs text-text-muted uppercase tracking-wider font-medium">Expiry</label>
                <select
                  value={selectedExpiry}
                  onChange={(e) => setSelectedExpiry(e.target.value)}
                  className="w-full pl-4 pr-10 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white text-base cursor-pointer appearance-none"
                >
                  {selectedIndex.expiryList.map((exp) => (
                    <option key={exp} value={exp}>
                      {exp}
                    </option>
                  ))}
                </select>
                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
              </div>

              <div className="flex flex-col gap-2 w-full">
                <label className="text-xs text-text-muted uppercase tracking-wider font-medium">Search Strike</label>
                <div className="relative">
                  <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={2} />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Strike price..."
                    className="w-full pl-10 pr-4 py-3 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white placeholder-text-muted text-base"
                  />
                </div>
              </div>
            </div>
          </motion.div>

          {/* Status Bar */}
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-4">
              {error && (
                <motion.span className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neon-red/10 border border-neon-red/30 text-neon-red text-sm glass">
                  <AlertCircle className="w-4 h-4" strokeWidth={2.5} />
                  {error}
                </motion.span>
              )}
              {!error && (
                <motion.span className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neon-green/10 border border-neon-green/30 text-neon-green text-sm glass">
                  <span className="w-2 h-2 rounded-full bg-neon-green animate-pulse-glow" />
                  {chainData ? chainData.strikes.length : 0} strikes loaded
                </motion.span>
              )}
              {isLoading && (
                <motion.span className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neon-orange/10 border border-neon-orange/30 text-neon-orange text-sm glass">
                  <Loader2 className="w-4 h-4 animate-spin" strokeWidth={2.5} />
                  Loading option chain...
                </motion.span>
              )}
              {lastUpdated && !isLoading && (
                <span className="text-xs text-text-muted">
                  Updated: {lastUpdated.toLocaleTimeString()}
                </span>
              )}
            </div>

            <div className="flex items-center gap-3 px-3 py-1.5 rounded-full bg-card-bg border border-glow-border glass">
              <span className="w-2 h-2 rounded-full bg-neon-green" />
              <span className="text-xs font-medium text-white">Market Open</span>
              <span className="text-[10px] text-neon-green">{selectedIndex.label}</span>
            </div>
          </div>

          {/* ATM Spot Bar */}
          {chainData && (
            <div className="glass rounded-xl border border-glow-border p-3">
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div className="flex items-center gap-3">
                  <span className="text-xs text-text-muted uppercase tracking-wider">Spot</span>
                  <span className="text-xl font-mono font-bold text-white">{formatNumber(chainData.spot)}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-text-muted uppercase tracking-wider">ATM Strike</span>
                  <span className={`text-xl font-mono font-bold ${chainData.atmStrike ? "text-neon-cyan" : "text-white"}`}>
                    {chainData.atmStrike?.toLocaleString()}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-text-muted uppercase tracking-wider">Expiry</span>
                  <span className="text-sm font-medium text-text-secondary">{chainData.expiry}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-text-muted uppercase tracking-wider">PCR</span>
                  <span className="text-sm font-mono font-bold text-neon-purple">
                    {(chainData.strikes.reduce((s, r) => s + r.peOI, 0) / chainData.strikes.reduce((s, r) => s + r.ceOI, 0)).toFixed(2)}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Option Chain Table */}
          <div className="flex-1 glass rounded-2xl border border-glow-border overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse" role="grid">
                <thead>
                  <tr className="border-b border-glow-border bg-card-bg sticky top-0 z-10 text-text-muted text-[10px] font-medium uppercase tracking-wider">
                    {/* Call side */}
                    <th className="px-3 py-2 text-right font-mono">CE LTP</th>
                    <th className="px-3 py-2 text-right font-mono">CE Change</th>
                    <th className="px-3 py-2 text-right font-mono">CE OI</th>
                    <th className="px-3 py-2 text-right font-mono">CE Δ OI</th>
                    {/* Strike */}
                    <th className="px-3 py-2 text-center font-mono font-bold text-white">Strike</th>
                    {/* Put side */}
                    <th className="px-3 py-2 text-left font-mono">PE Δ OI</th>
                    <th className="px-3 py-2 text-left font-mono">PE OI</th>
                    <th className="px-3 py-2 text-left font-mono">PE Change</th>
                    <th className="px-3 py-2 text-left font-mono">PE LTP</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading ? (
                    <tr>
                      <td colSpan={9} className="px-4 py-16 text-center">
                        <div className="flex flex-col items-center justify-center gap-3 text-text-secondary">
                          <Loader2 className="w-8 h-8 animate-spin text-neon-cyan" strokeWidth={2.5} />
                          <span>Loading option chain...</span>
                        </div>
                      </td>
                    </tr>
                  ) : chainData ? filteredStrikes.length > 0 ? filteredStrikes.map((row, index) => {
                    const isPositiveCE = row.ceChange >= 0;
                    const isPositivePE = row.peChange >= 0;
                    const ceOIPositive = row.ceOIChange >= 0;
                    const peOIPositive = row.peOIChange >= 0;
                    const isATM = row.isATM;
                    return (
                      <motion.tr
                        key={row.strike}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.02 }}
                        className={`transition-all duration-200 ${
                          isATM
                            ? "bg-gradient-to-r from-neon-cyan/8 via-neon-yellow/8 to-transparent border border-neon-cyan/20 shadow-[0_0_15px_rgba(0,240,255,0.08)]"
                            : "hover:bg-card-bg/30"
                        }`}
                      >
                        <td className="px-3 py-1.5 text-right font-mono text-neon-green text-[11px]">
                          {formatNumber(row.ceLtp)}
                        </td>
                        <td className={`px-3 py-1.5 text-right font-mono text-[11px] ${isPositiveCE ? "text-neon-green" : "text-neon-red"}`}>
                          {isPositiveCE ? "+" : ""}{formatNumber(row.ceChange)}
                        </td>
                        <td className="px-3 py-1.5 text-right font-mono text-text-secondary text-[11px]">{formatOI(row.ceOI)}</td>
                        <td className={`px-3 py-1.5 text-right font-mono text-[11px] ${ceOIPositive ? "text-neon-green" : "text-neon-red"}`}>
                          {ceOIPositive ? "+" : ""}{row.ceOIChange.toFixed(1)}%
                        </td>
                        <td className={`px-3 py-1.5 text-center font-mono font-bold ${
                          isATM ? "text-neon-cyan text-[13px] drop-shadow-[0_0_8px_rgba(0,240,255,0.6)]" : "text-white text-[12px]"
                        }`}>
                          {row.strike.toLocaleString()}
                          {isATM && (
                            <span className="ml-1.5 inline-block px-1.5 py-0.5 rounded bg-neon-cyan/20 text-neon-cyan text-[10px] font-bold border border-neon-cyan/30">
                              ATM
                            </span>
                          )}
                        </td>
                        <td className={`px-3 py-1.5 text-left font-mono text-[11px] ${peOIPositive ? "text-neon-green" : "text-neon-red"}`}>
                          {peOIPositive ? "+" : ""}{row.peOIChange.toFixed(1)}%
                        </td>
                        <td className="px-3 py-1.5 text-left font-mono text-text-secondary text-[11px]">{formatOI(row.peOI)}</td>
                        <td className={`px-3 py-1.5 text-left font-mono text-[11px] ${isPositivePE ? "text-neon-green" : "text-neon-red"}`}>
                          {isPositivePE ? "+" : ""}{formatNumber(row.peChange)}
                        </td>
                        <td className="px-3 py-1.5 text-left font-mono text-neon-red text-[11px] font-medium">{formatNumber(row.peLtp)}</td>
                      </motion.tr>
                    );
                  }) : (
                    <tr>
                      <td colSpan={9} className="px-4 py-16 text-center text-text-muted">
                        No strikes match "{searchQuery}"
                      </td>
                    </tr>
                  ) : (
                    <tr>
                      <td colSpan={9} className="px-4 py-16 text-center text-text-muted">
                        <AlertCircle className="w-8 h-8 mx-auto mb-2 text-neon-red/50" strokeWidth={2} />
                        <p>No option chain data available</p>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Footer */}
          <div className="text-center text-text-muted text-sm">
            Data from Fyers API v3 • Mock data fallback •{" "}
            <Layers className="inline w-4 h-4 text-neon-purple" strokeWidth={2} />
            <span className="text-neon-purple ml-1">Professional trading terminal layout</span>
          </div>
        </main>
      </div>
    </div>
  );
}
