"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
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
  Maximize2,
  Wifi,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { useOptionChain, useExpiries, SERVER_WAKING_MESSAGE } from "@/lib/hooks";

interface OptionStrike {
  strike: number;
  isATM: boolean;
  callITM: boolean;
  putITM: boolean;
  ceSymbol: string | null;
  ceLtp: number;
  ceChange: number;
  ceOI: number;
  ceOIChange: number;
  ceVolume: number;
  ceBid: number;
  ceAsk: number;
  peSymbol: string | null;
  peLtp: number;
  peChange: number;
  peOI: number;
  peOIChange: number;
  peVolume: number;
  peBid: number;
  peAsk: number;
}

interface IndexInfo {
  label: string;
  value: string;
}

const INDEXES: IndexInfo[] = [
  { label: "NIFTY", value: "NIFTY" },
  { label: "BANKNIFTY", value: "BANKNIFTY" },
  { label: "FINNIFTY", value: "FINNIFTY" },
  { label: "MIDCPNIFTY", value: "MIDCPNIFTY" },
  { label: "SENSEX", value: "SENSEX" },
];

export default function OptionChainPage() {
  const [selectedIndex, setSelectedIndex] = useState<IndexInfo>(INDEXES[0]);
  const [selectedExpiry, setSelectedExpiry] = useState("");
  const [strikes, setStrikes] = useState(10);
  const [searchQuery, setSearchQuery] = useState("");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [expiryList, setExpiryList] = useState<string[]>([]);

  // Fetch expiries for the selected symbol
  const { expiries, isLoading: expiriesLoading, mutate: mutateExpiries } = useExpiries(selectedIndex.value);

  // Auto-select first expiry when expiries load
  useEffect(() => {
    if (expiries.length > 0 && !selectedExpiry) {
      setSelectedExpiry(expiries[0]);
      setExpiryList(expiries);
    }
  }, [expiries, selectedExpiry]);

  // Fetch option chain
  const { 
    chainData, 
    isLoading, 
    isError, 
    error, 
    isFyersNotConnected,
    isFyersConnected,
    isServerWakingUp: wakingUp,
    mutate 
  } = useOptionChain(selectedIndex.value, selectedExpiry, strikes);

  // Transform data
  const transformedStrikes = useMemo(() => {
    if (!chainData?.option_chain) return [];
    
    return chainData.option_chain.map((strike) => ({
      strike: strike.strike,
      isATM: strike.is_atm,
      callITM: strike.call_itm,
      putITM: strike.put_itm,
      ceSymbol: strike.call?.symbol,
      ceLtp: strike.call?.ltp ?? 0,
      ceChange: strike.call?.oi_change_pct ?? 0,
      ceOI: strike.call?.oi ?? 0,
      ceOIChange: strike.call?.oi_change_pct ?? 0,
      ceVolume: strike.call?.volume ?? 0,
      ceBid: strike.call?.bid ?? 0,
      ceAsk: strike.call?.ask ?? 0,
      peSymbol: strike.put?.symbol,
      peLtp: strike.put?.ltp ?? 0,
      peChange: strike.put?.oi_change_pct ?? 0,
      peOI: strike.put?.oi ?? 0,
      peOIChange: strike.put?.oi_change_pct ?? 0,
      peVolume: strike.put?.volume ?? 0,
      peBid: strike.put?.bid ?? 0,
      peAsk: strike.put?.ask ?? 0,
    }));
  }, [chainData]);

  const formatNumber = (n: number) => n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const formatOI = (n: number) => n.toLocaleString();

  // Filter strikes based on search
  const filteredStrikes = useMemo(() => {
    if (!transformedStrikes.length) return [];
    if (!searchQuery.trim()) return transformedStrikes;
    return transformedStrikes.filter((s) => s.strike.toString().includes(searchQuery.trim()));
  }, [transformedStrikes, searchQuery]);

  // Calculate ATM strike index for auto-scroll
  const atmIndex = transformedStrikes.findIndex(s => s.isATM);

  // Loading state
  if (isLoading) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[350px] flex flex-col"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-glow-border bg-card-bg/50">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-white">Options Chain</h3>
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-cyan/20 text-neon-cyan font-medium">{selectedIndex.label}</span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-orange/20 text-neon-orange font-medium">{selectedExpiry || "LOADING..."}</span>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3 text-text-secondary">
            <span className="animate-spin">⏳</span>
            <span>Loading option chain...</span>
          </div>
        </div>
      </motion.div>
    );
  }

  // Error state
  if (isError) {
    const showConnectCard = isFyersNotConnected && !isFyersConnected;
    
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[350px] flex flex-col"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-glow-border bg-card-bg/50">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-white">Options Chain</h3>
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-cyan/20 text-neon-cyan font-medium">{selectedIndex.label}</span>
            <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${wakingUp ? "bg-neon-orange/20 text-neon-orange" : "bg-neon-red/20 text-neon-red"}`}>
              {wakingUp ? "CONNECTING" : "ERROR"}
            </span>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-center text-text-secondary max-w-md">
            {wakingUp ? (
              <>
                <Loader2 className="w-7 h-7 mx-auto mb-3 text-neon-cyan animate-spin" strokeWidth={2.5} />
                <p className="font-medium text-white mb-1">{SERVER_WAKING_MESSAGE}</p>
                <p className="text-sm text-text-muted">The backend is spinning up. This can take a few seconds.</p>
              </>
            ) : (
              <>
                <p className="mb-2">{showConnectCard ? "Fyers is not connected" : "Failed to load option chain"}</p>
                <p className={`text-sm mb-4 ${showConnectCard ? "text-neon-orange/90" : "text-neon-red/80"}`}>
                  {showConnectCard ? "Connect your Fyers account to load the option chain." : error}
                </p>
                {showConnectCard && (
                  <motion.a
                    href="/settings"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black font-bold transition-all duration-300 shadow-glow-cyan hover:opacity-90"
                  >
                    <Wifi className="w-4 h-4" strokeWidth={2.5} />
                    Connect Fyers
                  </motion.a>
                )}
              </>
            )}
          </div>
        </div>
      </motion.div>
    );
  }

  // Empty state
  if (!chainData || !transformedStrikes.length) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[350px] flex flex-col"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-glow-border bg-card-bg/50">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-white">Options Chain</h3>
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-cyan/20 text-neon-cyan font-medium">{selectedIndex.label}</span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-orange/20 text-neon-orange font-medium">{selectedExpiry || "NO DATA"}</span>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-text-muted">
            <p>{isFyersConnected ? (selectedExpiry ? "No data for this expiry." : "No option expiries are currently available.") : "Option chain data is unavailable."}</p>
            {!isFyersConnected && isFyersNotConnected && (
              <motion.a
                href="/settings"
                className="mt-4 inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black font-bold transition-all duration-300 shadow-glow-cyan hover:opacity-90"
              >
                Connect Fyers
              </motion.a>
            )}
          </div>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.5 }}
      className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[350px] flex flex-col"
    >
      {/* Header with controls */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-glow-border bg-card-bg/50 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-white">Options Chain</h3>
          <span className="text-[10px] px-2 py-0.5 rounded bg-neon-cyan/20 text-neon-cyan font-medium">{selectedIndex.label}</span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-neon-orange/20 text-neon-orange font-medium">{chainData.expiry}</span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-neon-purple/20 text-neon-purple font-medium">ATM: {chainData.atm_strike.toLocaleString()}</span>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Symbol selector */}
          <select
            value={selectedIndex.value}
            onChange={(e) => {
              const idx = INDEXES.find(i => i.value === e.target.value) || INDEXES[0];
              setSelectedIndex(idx);
              setSelectedExpiry(""); // Will auto-select first expiry
            }}
            className="px-2 py-1.5 bg-card-bg border border-glow-border rounded-lg text-white text-sm focus:border-neon-cyan focus:outline-none"
          >
            {INDEXES.map((idx) => (
              <option key={idx.value} value={idx.value}>
                {idx.label}
              </option>
            ))}
          </select>
          
          {/* Expiry selector */}
          <select
            value={selectedExpiry}
            onChange={(e) => setSelectedExpiry(e.target.value)}
            disabled={expiriesLoading || expiryList.length === 0}
            className="px-2 py-1.5 bg-card-bg border border-glow-border rounded-lg text-white text-sm focus:border-neon-cyan focus:outline-none"
          >
            {expiryList.map((exp) => (
              <option key={exp} value={exp}>{exp}</option>
            ))}
            {expiryList.length === 0 && <option value="">Loading...</option>}
          </select>
          
          {/* Strikes selector */}
          <select
            value={strikes}
            onChange={(e) => setStrikes(parseInt(e.target.value))}
            className="px-2 py-1.5 bg-card-bg border border-glow-border rounded-lg text-white text-sm focus:border-neon-cyan focus:outline-none"
          >
            <option value={5}>5 ITM/OTM</option>
            <option value={10}>10 ITM/OTM</option>
            <option value={15}>15 ITM/OTM</option>
            <option value={20}>20 ITM/OTM</option>
          </select>
          
          {/* Search */}
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search strike..."
            className="px-2 py-1.5 bg-card-bg border border-glow-border rounded-lg text-white text-sm focus:border-neon-cyan focus:outline-none w-32"
          />
          
          <motion.button
            onClick={() => mutate()}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="p-1.5 rounded-lg bg-card-bg border border-glow-border hover:border-neon-cyan/50 transition-colors" 
            title="Refresh"
          >
            <Maximize2 className="w-4 h-4 text-text-secondary" strokeWidth={2} />
          </motion.button>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-x-auto overflow-y-auto p-2" ref={(el) => {
        // Auto-scroll to ATM row on mount
        if (el && atmIndex >= 0) {
          const rows = el.querySelectorAll('tbody tr');
          if (rows[atmIndex]) {
            rows[atmIndex].scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        }
      }}>
        <table className="w-full text-sm min-w-[800px]" role="grid">
          <thead>
            <tr className="border-b border-glow-border text-text-muted sticky top-0 bg-card-bg/80 backdrop-blur-sm">
              <th className="px-2 py-2 text-right font-medium">Call LTP</th>
              <th className="px-2 py-2 text-right font-medium">Call OI</th>
              <th className="px-2 py-2 text-right font-medium">Δ OI %</th>
              <th className="px-2 py-2 text-center font-medium w-24">STRIKE</th>
              <th className="px-2 py-2 text-right font-medium">Δ OI %</th>
              <th className="px-2 py-2 text-right font-medium">Put OI</th>
              <th className="px-2 py-2 text-right font-medium">Put LTP</th>
            </tr>
          </thead>
          <tbody>
            {filteredStrikes.map((row, index) => (
              <motion.tr
                key={row.strike}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 + index * 0.02 }}
                className={`transition-colors ${
                  row.isATM 
                    ? "bg-gradient-to-r from-neon-cyan/8 via-neon-yellow/8 to-transparent border border-neon-cyan/20" 
                    : "hover:bg-card-bg/50"
                }`}
                style={row.isATM ? { boxShadow: "inset 0 0 0 1px rgba(0, 240, 255, 0.1)" } : undefined}
              >
                <td className="px-2 py-1.5 font-mono font-medium text-neon-green">{formatNumber(row.ceLtp)}</td>
                <td className="px-2 py-1.5 text-right font-mono text-text-secondary">{formatOI(row.ceOI)}</td>
                <td className={`px-2 py-1.5 text-right font-mono text-xs ${row.ceOIChange >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                  {row.ceOIChange >= 0 ? "+" : ""}{row.ceOIChange.toFixed(1)}%
                </td>
                <td className={`px-2 py-1.5 text-center font-mono font-bold ${row.isATM ? "text-neon-cyan text-glow-cyan" : "text-white"}`}>
                  {row.strike.toLocaleString()}
                  {row.isATM && <span className="ml-1 text-[10px] bg-neon-cyan/20 text-neon-cyan px-1 rounded">ATM</span>}
                  {row.callITM && <span className="ml-1 text-[9px] bg-neon-green/20 text-neon-green px-1 rounded">ITM</span>}
                </td>
                <td className={`px-2 py-1.5 text-right font-mono text-xs ${row.peOIChange >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                  {row.peOIChange >= 0 ? "+" : ""}{row.peOIChange.toFixed(1)}%
                </td>
                <td className="px-2 py-1.5 text-right font-mono text-text-secondary">{formatOI(row.peOI)}</td>
                <td className="px-2 py-1.5 font-mono font-medium text-neon-red">{formatNumber(row.peLtp)}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}

function formatNumber(n: number) {
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatOI(n: number) {
  return n.toLocaleString();
}
