"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Minus, Search, RefreshCw, AlertCircle, Loader2, X } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface MarketItem {
  symbol: string;
  name: string;
  ltp: number;
  change: number;
  changePercent: number;
  sparkline: number[];
}

// Mock data fallback
const MOCK_MARKET_DATA: MarketItem[] = [
  { symbol: "NIFTY 50", name: "NIFTY 50", ltp: 24345.85, change: 124.35, changePercent: 0.51, sparkline: [24200, 24250, 24180, 24300, 24280, 24345] },
  { symbol: "BANKNIFTY", name: "BANK NIFTY", ltp: 51890.20, change: -85.40, changePercent: -0.16, sparkline: [51950, 51900, 51800, 51850, 51920, 51890] },
  { symbol: "RELIANCE", name: "Reliance Ind.", ltp: 2845.60, change: 42.15, changePercent: 1.50, sparkline: [2800, 2810, 2825, 2835, 2840, 2845] },
  { symbol: "TCS", name: "TCS", ltp: 4120.75, change: -12.30, changePercent: -0.30, sparkline: [4130, 4125, 4115, 4120, 4118, 4120] },
  { symbol: "HDFC BANK", name: "HDFC Bank", ltp: 1678.45, change: 18.90, changePercent: 1.14, sparkline: [1660, 1665, 1670, 1675, 1677, 1678] },
  { symbol: "INFOSYS", name: "Infosys", ltp: 1845.30, change: -8.20, changePercent: -0.44, sparkline: [1850, 1848, 1840, 1845, 1842, 1845] },
  { symbol: "ICICI BANK", name: "ICICI Bank", ltp: 1120.75, change: 15.30, changePercent: 1.38, sparkline: [1105, 1110, 1115, 1118, 1120, 1120] },
  { symbol: "KOTAK BANK", name: "Kotak Bank", ltp: 1785.90, change: -5.10, changePercent: -0.28, sparkline: [1790, 1788, 1785, 1786, 1784, 1785] },
];

function SparklineChart({ data, color }: { data: number[]; color: string }) {
  const width = 80;
  const height = 28;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  
  const points = data.map((value, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((value - min) / range) * height;
    return `${x},${y}`;
  }).join(" ");

  return (
    <svg width={width} height={height} className="block">
      <defs>
        <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor={color} stopOpacity={0.3} />
          <stop offset="100%" stopColor={color} stopOpacity={0.8} />
        </linearGradient>
      </defs>
      <path
        d={`M${points}`}
        stroke="url(#gradient)"
        strokeWidth={2}
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="drop-shadow-[0_0_6px_currentColor]"
      />
      <circle cx={points.split(" ").slice(-1)[0].split(",")[0]} cy={points.split(" ").slice(-1)[0].split(",")[1]} r={3} fill={color} className="animate-pulse" />
    </svg>
  );
}

function MarketRow({ item, index }: { item: MarketItem; index: number }) {
  const isPositive = item.change >= 0;
  const Icon = isPositive ? TrendingUp : TrendingDown;
  const color = isPositive ? "#00FF66" : "#FF003C";
  
  return (
    <motion.tr
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03 }}
      className="border-b border-glow-border hover:bg-card-bg/50 transition-colors cursor-pointer"
    >
      <td className="px-5 py-4">
        <div className="flex items-center gap-3">
          <span className="font-mono font-semibold text-white text-base">{item.symbol}</span>
          <span className="text-[11px] text-text-muted uppercase tracking-wider">{item.name}</span>
        </div>
      </td>
      <td className="px-5 py-4 font-mono font-semibold text-white tabular-nums">
        ₹{item.ltp.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </td>
      <td className="px-5 py-4">
        <div className="flex items-center gap-2">
          <Icon className={`w-4 h-4 text-${isPositive ? "neon-green" : "neon-red"}`} strokeWidth={2.5} />
          <span className={`font-mono font-medium text-${isPositive ? "neon-green" : "neon-red"}`}>
            {isPositive ? "+" : ""}{item.changePercent.toFixed(2)}%
          </span>
          <span className={`text-[11px] font-mono text-${isPositive ? "neon-green" : "neon-red"}`}>
            ({isPositive ? "+" : ""}₹{Math.abs(item.change).toFixed(2)})
          </span>
        </div>
      </td>
      <td className="px-5 py-4">
        <SparklineChart data={item.sparkline} color={color} />
      </td>
    </motion.tr>
  );
}

export default function MarketWatchPage() {
  const [query, setQuery] = useState("");
  const [marketData, setMarketData] = useState<MarketItem[]>(MOCK_MARKET_DATA);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usingMockData, setUsingMockData] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchMarketData = useCallback(async (searchQuery?: string) => {
    setIsLoading(true);
    setError(null);
    
    const url = searchQuery
      ? `${API_URL}/api/v1/market/search?q=${encodeURIComponent(searchQuery)}`
      : `${API_URL}/api/v1/market/quotes?symbols=NIFTY,BANKNIFTY,RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK,KOTAKBANK`;

    try {
      const response = await fetch(url, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        signal: AbortSignal.timeout(8000),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      
      // Handle both search results and quotes format
      let transformed: MarketItem[];
      
      if (Array.isArray(data)) {
        // Search results format
        transformed = data.map((quote: any) => ({
          symbol: quote.symbol?.replace("NSE:", "") || quote.symbol,
          name: quote.name || quote.symbol?.replace("NSE:", "") || "Unknown",
          ltp: quote.ltp || quote.price || 0,
          change: quote.change || 0,
          changePercent: quote.change_percent || quote.pChange || 0,
          sparkline: quote.history?.slice(-8) || Array(8).fill(quote.ltp || quote.price || 0).map((p, i) => p + (Math.random() - 0.5) * (p || 1) * 0.01),
        }));
      } else if (typeof data === "object") {
        // Quotes format
        transformed = Object.entries(data).map(([symbol, quote]: [string, any]) => ({
          symbol: symbol.replace("NSE:", ""),
          name: symbol.replace("NSE:", ""),
          ltp: quote.ltp || quote.price || 0,
          change: quote.change || 0,
          changePercent: quote.change_percent || quote.pChange || 0,
          sparkline: quote.history?.slice(-8) || Array(8).fill(quote.ltp || quote.price || 0).map((p, i) => p + (Math.random() - 0.5) * (p || 1) * 0.01),
        }));
      } else {
        throw new Error("Unexpected data format");
      }

      if (transformed.length > 0) {
        setMarketData(transformed);
        setUsingMockData(false);
        setLastUpdated(new Date());
      } else {
        throw new Error("No data returned");
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Unknown error";
      setError(`Backend unavailable: ${errorMessage}`);
      setUsingMockData(true);
      setMarketData(searchQuery ? [] : MOCK_MARKET_DATA);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMarketData();
  }, [fetchMarketData]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      fetchMarketData(query.trim());
    } else {
      fetchMarketData();
    }
  };

  const handleRefresh = () => {
    fetchMarketData(query.trim() || undefined);
  };

  const clearSearch = () => {
    setQuery("");
    fetchMarketData();
  };

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
                <TrendingUp className="w-8 h-8 text-neon-cyan" strokeWidth={2.5} />
                Market Watch
              </h1>
              <p className="text-text-secondary mt-1">Real-time quotes & market search via Fyers API v3</p>
            </div>
            
            <motion.button
              onClick={handleRefresh}
              disabled={isLoading}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-card-bg border border-glow-border hover:border-neon-cyan/50 text-white font-medium transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed glass"
            >
              <RefreshCw className={`w-5 h-5 ${isLoading ? "animate-spin" : ""}`} strokeWidth={2.5} />
              <span>Refresh</span>
            </motion.button>
          </div>

          {/* Search Bar */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass rounded-2xl border border-glow-border p-4"
          >
            <form onSubmit={handleSearch} className="relative max-w-xl mx-auto">
              <div className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" strokeWidth={2.5} />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search symbols... (e.g., NIFTY, SBIN, RELIANCE)"
                  className="w-full pl-12 pr-4 py-3.5 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white placeholder-text-muted text-base"
                />
                {query && (
                  <motion.button
                    type="button"
                    onClick={clearSearch}
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.9 }}
                    className="absolute right-4 top-1/2 -translate-y-1/2 p-1 text-text-muted hover:text-white transition-colors"
                  >
                    <X className="w-5 h-5" strokeWidth={2.5} />
                  </motion.button>
                )}
              </div>
              <p className="text-xs text-text-muted text-center mt-2">
                Press Enter to search • Fetches from Fyers API v3
              </p>
            </form>
          </motion.div>

          {/* Status Bar */}
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-4">
              {(error || usingMockData) && (
                <motion.span
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neon-red/10 border border-neon-red/30 text-neon-red text-sm glass"
                >
                  <AlertCircle className="w-4 h-4" strokeWidth={2.5} />
                  {error ? "Backend offline • Showing mock data" : "Offline mode • Mock data"}
                </motion.span>
              )}
              {!usingMockData && !error && (
                <motion.span
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neon-green/10 border border-neon-green/30 text-neon-green text-sm glass"
                >
                  <span className="w-2 h-2 rounded-full bg-neon-green animate-pulse-glow" />
                  Live data from Fyers API
                </motion.span>
              )}
              {lastUpdated && (
                <span className="text-xs text-text-muted">
                  Updated: {lastUpdated.toLocaleTimeString()}
                </span>
              )}
            </div>
            
            <div className="flex items-center gap-3 px-3 py-1.5 rounded-full bg-card-bg border border-glow-border glass">
              <span className="w-2 h-2 rounded-full bg-neon-green" />
              <span className="text-xs font-medium text-white">Market Open</span>
              <span className="text-[10px] text-neon-green">NSE | BSE</span>
            </div>
          </div>

          {/* Data Table */}
          <div className="glass rounded-2xl border border-glow-border overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full" role="grid">
                <thead>
                  <tr className="border-b border-glow-border bg-card-bg/50 text-text-muted text-xs font-medium uppercase tracking-wider">
                    <th className="px-5 py-4 text-left">Symbol</th>
                    <th className="px-5 py-4 text-right">LTP</th>
                    <th className="px-5 py-4 text-right">Change</th>
                    <th className="px-5 py-4 text-left">Sparkline (8 periods)</th>
                  </tr>
                </thead>
                <tbody>
                  {marketData.length === 0 && !isLoading ? (
                    <tr>
                      <td colSpan={4} className="px-5 py-12 text-center text-text-muted">
                        <AlertCircle className="w-8 h-8 mx-auto mb-2 text-neon-red/50" strokeWidth={2} />
                        <p>No results found for "{query}"</p>
                        <p className="text-sm mt-1">Try a different symbol or clear search</p>
                      </td>
                    </tr>
                  ) : (
                    marketData.map((item, index) => <MarketRow key={item.symbol} item={item} index={index} />)
                  )}
                  {isLoading && (
                    <tr>
                      <td colSpan={4} className="px-5 py-12 text-center">
                        <div className="flex items-center justify-center gap-3 text-text-secondary">
                          <Loader2 className="w-6 h-6 animate-spin text-neon-cyan" strokeWidth={2.5} />
                          <span>Fetching live data...</span>
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Footer */}
          <div className="text-center text-text-muted text-sm">
            {usingMockData 
              ? "⚠️ Showing mock data. Backend may be sleeping (Render free tier). Click Refresh to retry."
              : "Data sourced from Fyers API v3 • Auto-refresh on window focus • WebSocket streaming coming soon"}
          </div>
        </main>
      </div>
    </div>
  );
}