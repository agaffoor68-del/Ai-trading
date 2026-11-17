"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import useSWR from "swr";
import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Search, RefreshCw, Loader2, X, AlertCircle, Sparkles, Wifi } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { useMarketQuotes, useExpiries, formatFyersSymbol, isServerWakingUp, SERVER_WAKING_MESSAGE } from "@/lib/hooks";
import { fetchWithTimeout } from "@/lib/api-client";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

interface SearchResult {
  symbol: string;
  exchange: string;
  name: string;
  fyers_token: string;
  instrument_type: string;
  lot_size: number | null;
}

interface DisplayItem extends SearchResult {
  ltp: number | null;
  change: number | null;
  changePercent: number | null;
  priceSource: "live" | "stale" | "none";
  isLoading: boolean;
}

const fetcher = async (url: string) => {
  const response = await fetchWithTimeout(url, {
    credentials: "same-origin",
  });
  if (!response.ok) {
    if (response.status === 422) {
      throw new Error("Invalid search format. Please try again.");
    }
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  return response.json();
};

export default function MarketWatchPage() {
  const [query, setQuery] = useState("NIFTY");
  const [results, setResults] = useState<DisplayItem[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  // SWR for search - fetches on query change
  const { data: searchData, error: searchError, isLoading: isSearchLoading, mutate: mutateSearch } = useSWR(
    query.trim() ? `/api/v1/market/search?query=${encodeURIComponent(query.trim())}` : null,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 2000,
    }
  );

  // SWR for quotes - auto-refreshes
  const topSymbols = searchData?.results?.slice(0, 10) || [];
  const fyersSymbols = topSymbols.map((s: SearchResult) => s.symbol);

  const { quotes, isLoading: isQuotesLoading, isFyersNotConnected } = useMarketQuotes(fyersSymbols);

  // Combine search results with quotes
  useEffect(() => {
    if (searchData?.results) {
      const initialItems: DisplayItem[] = searchData.results.map((item: SearchResult, idx: number) => {
        const quote = quotes[fyersSymbols[idx]] || quotes[item.symbol] || quotes[item.fyers_token];
        
        if (quote && quote.ltp !== null && quote.ltp !== undefined) {
          const isStale = quote.updated_at ? (Date.now() - new Date(quote.updated_at).getTime()) > 60000 : false;
          return {
            ...item,
            ltp: quote.ltp,
            change: quote.change ?? 0,
            changePercent: quote.change_percent ?? 0,
            priceSource: isStale ? "stale" : "live",
            isLoading: false,
          };
        } else {
          return {
            ...item,
            ltp: null,
            change: null,
            changePercent: null,
            priceSource: "none",
            isLoading: isQuotesLoading,
          };
        }
      });
      
      setResults(initialItems);
      setLastUpdated(new Date());
      setHasSearched(true);
    }
  }, [searchData, quotes, fyersSymbols]);

  useEffect(() => {
    if (searchError) {
      setError(searchError.message);
      setResults([]);
      setHasSearched(true);
    } else {
      setError(null);
    }
  }, [searchError]);

  const [error, setError] = useState<string | null>(null);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      mutateSearch();
    }
  };

  const handleRefresh = () => {
    mutateSearch();
  };

  const clearSearch = () => {
    setQuery("NIFTY");
  };

  const showConnectCard = isFyersNotConnected;
  const wakingUp = isServerWakingUp(searchError);

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="w-full lg:ml-64 min-h-screen flex flex-col">
        <Header />
        
        <main className="flex-1 p-4 md:p-8 lg:p-10 pt-20 lg:pt-24 space-y-6">
          {/* Page Header */}
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight flex items-center gap-3">
                <TrendingUp className="w-8 h-8 text-neon-cyan" strokeWidth={2.5} />
                Market Watch
              </h1>
              <p className="text-text-secondary mt-1">Search & track symbols via Fyers API v3</p>
            </div>
            
            <motion.button
              onClick={handleRefresh}
              disabled={isSearchLoading || isQuotesLoading}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-card-bg border border-glow-border hover:border-neon-cyan/50 text-white font-medium transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed glass"
            >
              <RefreshCw className={`w-5 h-5 ${(isSearchLoading || isQuotesLoading) ? "animate-spin" : ""}`} strokeWidth={2.5} />
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
                  placeholder="Search symbols... (e.g., NIFTY 50, BANKNIFTY, RELIANCE)"
                  className="w-full pl-12 pr-4 py-3.5 bg-card-bg border border-glow-border focus:border-neon-cyan focus:outline-none rounded-xl text-white placeholder-text-muted text-base"
                />
                {query && query !== "NIFTY" && (
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
            <div className="flex items-center gap-4 flex-wrap">
              {error && hasSearched && (
                <motion.span
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neon-red/10 border border-neon-red/30 text-neon-red text-sm glass"
                >
                  <AlertCircle className="w-4 h-4" strokeWidth={2.5} />
                  {wakingUp ? SERVER_WAKING_MESSAGE : error}
                </motion.span>
              )}
              {showConnectCard && !error && (
                <motion.span
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neon-orange/10 border border-neon-orange/30 text-neon-orange text-sm glass"
                >
                  <Wifi className="w-4 h-4" strokeWidth={2.5} />
                  Fyers not connected - quotes unavailable
                  <motion.a
                    href="/settings"
                    whileHover={{ scale: 1.03 }}
                    whileTap={{ scale: 0.97 }}
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black font-bold ml-1"
                  >
                    <Wifi className="w-3.5 h-3.5" strokeWidth={2.5} />
                    Connect Fyers
                  </motion.a>
                </motion.span>
              )}
              {!error && hasSearched && !showConnectCard && (
                <motion.span
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neon-green/10 border border-neon-green/30 text-neon-green text-sm glass"
                >
                  <span className="w-2 h-2 rounded-full bg-neon-green animate-pulse-glow" />
                  {results.length} result{results.length !== 1 ? "s" : ""} found
                </motion.span>
              )}
              {(isSearchLoading || isQuotesLoading) && (
                <motion.span
                  className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neon-orange/10 border border-neon-orange/30 text-neon-orange text-sm glass"
                >
                  <Loader2 className="w-4 h-4 animate-spin" strokeWidth={2.5} />
                  {isSearchLoading ? "Searching..." : "Fetching quotes..."}
                </motion.span>
              )}
              {lastUpdated && !isSearchLoading && !isQuotesLoading && (
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
              <table className="min-w-[700px] w-full" role="grid">
                <thead>
                  <tr className="border-b border-glow-border bg-card-bg/50 text-text-muted text-xs font-medium uppercase tracking-wider">
                    <th className="px-3 md:px-5 py-3 md:py-4 text-left">Symbol</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-right">LTP</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-right">Change</th>
                    <th className="px-3 md:px-5 py-3 md:py-4 text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {isSearchLoading ? (
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
                        <p>No results found for "{query}"</p>
                        <p className="text-sm mt-1">Try a different symbol (e.g., NIFTY 50, RELIANCE, SBIN, TCS)</p>
                      </td>
                    </tr>
                  ) : (
                    results.map((item, index) => (
                      <motion.tr
                        key={item.symbol}
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
                            {item.priceSource === "stale" && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-neon-orange/20 text-neon-orange font-medium">
                                STALE
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-5 py-4 font-mono tabular-nums">
                          {item.ltp !== null ? (
                            <span className="text-white">₹{item.ltp.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                          ) : (
                            <span className="text-text-muted">—</span>
                          )}
                        </td>
                        <td className="px-5 py-4">
                          {item.ltp !== null ? (
                            <div className="flex items-center gap-2">
                              {item.changePercent !== null ? (
                                <>
                                  <TrendingUp className={`w-4 h-4 text-${item.changePercent >= 0 ? "neon-green" : "neon-red"}`} strokeWidth={2.5} />
                                  <span className={`font-mono font-medium text-${item.changePercent >= 0 ? "neon-green" : "neon-red"}`}>
                                    {item.changePercent >= 0 ? "+" : ""}{item.changePercent.toFixed(2)}%
                                  </span>
                                  <span className={`text-[11px] font-mono text-${item.changePercent >= 0 ? "neon-green" : "neon-red"}`}>
                                    ({item.changePercent >= 0 ? "+" : ""}₹{Math.abs(item.change || 0).toFixed(2)})
                                  </span>
                                </>
                              ) : (
                                <span className="text-text-muted text-sm">—</span>
                              )}
                            </div>
                          ) : (
                            <span className="text-text-muted text-sm">No live data</span>
                          )}
                        </td>
                        <td className="px-5 py-4">
                          {item.priceSource === "live" ? (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-green/20 text-neon-green font-medium flex items-center gap-1">
                              <Wifi className="w-3 h-3" strokeWidth={2.5} />
                              LIVE
                            </span>
                          ) : item.priceSource === "stale" ? (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-neon-orange/20 text-neon-orange font-medium">
                              STALE
                            </span>
                          ) : (
                            <span className="text-text-muted text-sm">No data</span>
                          )}
                        </td>
                      </motion.tr>
                    ))
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
