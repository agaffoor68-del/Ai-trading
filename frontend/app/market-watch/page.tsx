"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Search, RefreshCw, Loader2, X, AlertCircle, Sparkles, Wifi } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Search result type from backend
interface SearchResult {
  symbol: string;
  exchange: string;
  name: string;
  fyers_token: string;
  instrument_type: string;
  lot_size: number | null;
}

// Quote response from backend
interface QuoteData {
  ltp: number | null;
  change: number | null;
  change_percent: number | null;
  source: string;
  updated_at: string | null;
}

// Extended type for table display
interface DisplayItem extends SearchResult {
  ltp: number | null;
  change: number | null;
  changePercent: number | null;
  sparkline: number[];
  priceSource: "live" | "fetching";
}

// Mock price data for fallback
const MOCK_PRICES: Record<string, { ltp: number; change: number; changePercent: number }> = {
  "NIFTY": { ltp: 24345.85, change: 124.35, changePercent: 0.51 },
  "NIFTY 50": { ltp: 24345.85, change: 124.35, changePercent: 0.51 },
  "BANKNIFTY": { ltp: 51890.20, change: -85.40, changePercent: -0.16 },
  "RELIANCE": { ltp: 2845.60, change: 42.15, changePercent: 1.50 },
  "TCS": { ltp: 4120.75, change: -12.30, changePercent: -0.30 },
  "HDFC BANK": { ltp: 1678.45, change: 18.90, changePercent: 1.14 },
  "INFOSYS": { ltp: 1845.30, change: -8.20, changePercent: -0.44 },
  "ICICI BANK": { ltp: 1120.75, change: 15.30, changePercent: 1.38 },
  "KOTAK BANK": { ltp: 1785.90, change: -5.10, changePercent: -0.28 },
  "SBIN": { ltp: 785.40, change: 12.30, changePercent: 1.59 },
  "ITC": { ltp: 485.20, change: -2.10, changePercent: -0.43 },
  "AXIS BANK": { ltp: 1150.75, change: 8.90, changePercent: 0.78 },
};

function generateSparkline(basePrice: number): number[] {
  return Array(8).fill(0).map((_, i) => basePrice + (Math.random() - 0.5) * basePrice * 0.02);
}

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

function MarketRow({ item, index }: { item: DisplayItem; index: number }) {
  const hasPrice = item.ltp !== null && item.ltp !== undefined;
  const isPositive = hasPrice && (item.change ?? 0) >= 0;
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
          {item.instrument_type && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-neon-purple/20 text-neon-purple font-medium">
              {item.instrument_type === "13" ? "INDEX" : item.instrument_type === "11" ? "FUT" : item.instrument_type === "12" ? "OPT" : item.instrument_type}
            </span>
          )}
          {item.priceSource === "live" && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-neon-green/20 text-neon-green font-medium flex items-center gap-1">
              <Wifi className="w-3 h-3" strokeWidth={2.5} />
              LIVE
            </span>
          )}
          {item.priceSource === "fetching" && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-neon-orange/20 text-neon-orange font-medium animate-pulse flex items-center gap-1">
              <Loader2 className="w-3 h-3 animate-spin" strokeWidth={2.5} />
              Fetching...
            </span>
          )}
        </div>
      </td>
      <td className="px-5 py-4 font-mono tabular-nums">
        {hasPrice ? (
          <span className="text-white">₹{item.ltp!.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        ) : (
          <span className="text-text-muted">—</span>
        )}
      </td>
      <td className="px-5 py-4">
        {hasPrice ? (
          <div className="flex items-center gap-2">
            <Icon className={`w-4 h-4 text-${isPositive ? "neon-green" : "neon-red"}`} strokeWidth={2.5} />
            <span className={`font-mono font-medium text-${isPositive ? "neon-green" : "neon-red"}`}>
              {isPositive ? "+" : ""}{item.changePercent!.toFixed(2)}%
            </span>
            <span className={`text-[11px] font-mono text-${isPositive ? "neon-green" : "neon-red"}`}>
              ({isPositive ? "+" : ""}₹{Math.abs(item.change!).toFixed(2)})
            </span>
          </div>
        ) : (
          <span className="text-text-muted text-sm">No live data</span>
        )}
      </td>
      <td className="px-5 py-4">
        {hasPrice ? (
          <SparklineChart data={item.sparkline} color={color} />
        ) : (
          <span className="text-text-muted text-sm">—</span>
        )}
      </td>
    </motion.tr>
  );
}

export default function MarketWatchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<DisplayItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingQuotes, setIsLoadingQuotes] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const fetchQuotes = useCallback(async (symbols: SearchResult[]): Promise<DisplayItem[]> => {
    if (symbols.length === 0) return [];

    setIsLoadingQuotes(true);
    
    // Take top 10 results for quotes
    const topSymbols = symbols.slice(0, 10);
    
    // Build Fyers symbol format (NSE:SYMBOL-TYPE)
    const fyersSymbols = topSymbols.map(s => {
      const exchange = s.exchange === "NSE_FO" ? "NSE" : s.exchange === "NSE_CM" ? "NSE" : s.exchange;
      return `${exchange}:${s.symbol}`;
    });

    try {
      const response = await fetch(`${API_URL}/api/v1/market/quotes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbols: fyersSymbols }),
        signal: AbortSignal.timeout(8000),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      const quotes = data.quotes || {};

      // Merge quotes with search results
      return topSymbols.map((item, idx) => {
        const quote = quotes[fyersSymbols[idx]] || quotes[item.symbol] || quotes[item.fyers_token];
        
        if (quote && quote.ltp !== null && quote.ltp !== undefined) {
          // Live data from Redis/Fyers
          return {
            ...item,
            ltp: quote.ltp,
            change: quote.change ?? 0,
            changePercent: quote.change_percent ?? 0,
            sparkline: generateSparkline(quote.ltp),
            priceSource: "live" as const,
          };
        } else {
          // No live data yet - show fetching state
          return {
            ...item,
            ltp: null,
            change: null,
            changePercent: null,
            sparkline: Array(8).fill(0),
            priceSource: "fetching" as const,
          };
        }
      });
    } catch (err) {
      console.warn("Failed to fetch quotes:", err);
      // Return fetching state on error
      return topSymbols.map(item => ({
        ...item,
        ltp: null,
        change: null,
        changePercent: null,
        sparkline: Array(8).fill(0),
        priceSource: "fetching" as const,
      }));
    } finally {
      setIsLoadingQuotes(false);
    }
  }, []);

  const fetchSearch = useCallback(async (searchQuery: string) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(
        `${API_URL}/api/v1/market/search?query=${encodeURIComponent(searchQuery)}`,
        {
          method: "GET",
          headers: { "Content-Type": "application/json" },
          signal: AbortSignal.timeout(10000),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      const searchResults = data.results || [];

      // First, set results with mock/none prices immediately
      const initialItems: DisplayItem[] = searchResults.map((item: SearchResult) => {
        const mockPrice = MOCK_PRICES[item.symbol] || MOCK_PRICES[item.symbol.replace("NSE:", "")];
        
        if (mockPrice) {
          return {
            ...item,
            ltp: mockPrice.ltp,
            change: mockPrice.change,
            changePercent: mockPrice.changePercent,
            sparkline: generateSparkline(mockPrice.ltp),
            priceSource: "mock" as const,
          };
        } else {
          return {
            ...item,
            ltp: null,
            change: null,
            changePercent: null,
            sparkline: Array(8).fill(0),
            priceSource: "none" as const,
          };
        }
      });

      setResults(initialItems);
      setLastUpdated(new Date());
      setHasSearched(true);

      // Then fetch real quotes in background
      fetchQuotes(searchResults).then((liveItems: DisplayItem[]) => {
        setResults(liveItems);
        setLastUpdated(new Date());
      });

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Unknown error";
      setError(errorMessage);
      setResults([]);
      setHasSearched(true);
    } finally {
      setIsLoading(false);
    }
  }, [fetchQuotes]);

  // Load default popular symbols on initial load
  useEffect(() => {
    fetchSearch("NIFTY");
  }, [fetchSearch]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      fetchSearch(query.trim());
    }
  };

  const handleRefresh = () => {
    if (query.trim()) {
      fetchSearch(query.trim());
    } else {
      fetchSearch("NIFTY");
    }
  };

  const clearSearch = () => {
    setQuery("");
    fetchSearch("NIFTY");
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
              <p className="text-text-secondary mt-1">Search & track symbols via Fyers API v3</p>
            </div>
            
            <motion.button
              onClick={handleRefresh}
              disabled={isLoading || isLoadingQuotes}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-card-bg border border-glow-border hover:border-neon-cyan/50 text-white font-medium transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed glass"
            >
              <RefreshCw className={`w-5 h-5 ${(isLoading || isLoadingQuotes) ? "animate-spin" : ""}`} strokeWidth={2.5} />
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
                Press Enter to search • Powered by Fyers Symbol Master
              </p>
            </form>
          </motion.div>

          {/* Status Bar */}
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-4">
              {error && hasSearched && (
                <motion.span
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neon-red/10 border border-neon-red/30 text-neon-red text-sm glass"
                >
                  <AlertCircle className="w-4 h-4" strokeWidth={2.5} />
                  Error: {error}
                </motion.span>
              )}
              {!error && hasSearched && (
                <motion.span
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neon-green/10 border border-neon-green/30 text-neon-green text-sm glass"
                >
                  <span className="w-2 h-2 rounded-full bg-neon-green animate-pulse-glow" />
                  {results.length} result{results.length !== 1 ? "s" : ""} found
                </motion.span>
              )}
              {(isLoading || isLoadingQuotes) && (
                <motion.span
                  className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neon-orange/10 border border-neon-orange/30 text-neon-orange text-sm glass"
                >
                  <Loader2 className="w-4 h-4 animate-spin" strokeWidth={2.5} />
                  {isLoading ? "Searching..." : "Fetching quotes..."}
                </motion.span>
              )}
              {lastUpdated && !isLoading && !isLoadingQuotes && (
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
                    <th className="px-5 py-4 text-left">Sparkline</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading ? (
                    <tr>
                      <td colSpan={4} className="px-5 py-12 text-center">
                        <div className="flex items-center justify-center gap-3 text-text-secondary">
                          <Loader2 className="w-6 h-6 animate-spin text-neon-cyan" strokeWidth={2.5} />
                          <span>Searching symbol master...</span>
                        </div>
                      </td>
                    </tr>
                  ) : results.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-5 py-12 text-center text-text-muted">
                        <AlertCircle className="w-8 h-8 mx-auto mb-2 text-neon-red/50" strokeWidth={2} />
                        <p>No results found for "{query || "NIFTY"}"</p>
                        <p className="text-sm mt-1">Try a different symbol (e.g., RELIANCE, SBIN, TCS)</p>
                      </td>
                    </tr>
                  ) : (
                    results.map((item, index) => <MarketRow key={item.symbol} item={item} index={index} />)
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Footer */}
          <div className="text-center text-text-muted text-sm">
            Data from Fyers Symbol Master • LTP from Redis cache (WebSocket for live streaming) •{" "}
            <Sparkles className="inline w-4 h-4 text-neon-purple" strokeWidth={2} />
            <span className="text-neon-purple ml-1">Smart ranking: Index → F&O → Equity → ETFs</span>
          </div>
        </main>
      </div>
    </div>
  );
}