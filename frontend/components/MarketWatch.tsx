"use client";

import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Minus, Wifi, AlertCircle } from "lucide-react";
import useSWR from "swr";
import { useMarketQuotes, formatFyersSymbol } from "@/lib/hooks";

interface DisplayItem {
  symbol: string;
  name: string;
  price: number | null;
  change: number | null;
  changePercent: number | null;
  sparkline: number[] | null;
  priceSource: "live" | "stale" | "none";
  isLoading: boolean;
}

const DEFAULT_SYMBOLS = ["NIFTY 50", "BANKNIFTY", "RELIANCE", "TCS", "HDFC BANK"];

function SparklineChart({ data, color }: { data: number[] | null; color: string }) {
  if (!data || data.length === 0) return null;
  
  const width = 60;
  const height = 24;
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
      <path
        d={`M${points}`}
        stroke={color}
        strokeWidth={1.5}
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="drop-shadow-[0_0_4px_currentColor]"
      />
      <circle 
        cx={parseFloat(points.split(" ").slice(-1)[0].split(",")[0])} 
        cy={parseFloat(points.split(" ").slice(-1)[0].split(",")[1])} 
        r={2} 
        fill={color} 
        className="animate-pulse" 
      />
    </svg>
  );
}

export function MarketWatch() {
  // Use SWR to fetch live quotes
  const { quotes, isLoading, isError, error, errorCode, isFyersNotConnected, isFyersError, isFyersUnreachable, mutate } = useMarketQuotes(DEFAULT_SYMBOLS);

  // Build display items
  const displayItems: DisplayItem[] = DEFAULT_SYMBOLS.map((symbol) => {
    const fyersSymbol = formatFyersSymbol(symbol);
    const quote = quotes[fyersSymbol] || quotes[symbol];
    
    if (quote && quote.ltp !== null && quote.ltp !== undefined) {
      // Check if data is stale (older than 60 seconds)
      const isStale = quote.updated_at ? (Date.now() - new Date(quote.updated_at).getTime()) > 60000 : false;
      
      // Generate sparkline from real data if we have multiple points
      // For now, show null - real sparklines would need historical data
      return {
        symbol,
        name: symbol,
        price: quote.ltp,
        change: quote.change ?? 0,
        changePercent: quote.change_percent ?? 0,
        sparkline: null, // No fake sparklines
        priceSource: isStale ? "stale" : "live",
        isLoading: false,
      };
    }
    return {
      symbol,
      name: symbol,
      price: null,
      change: null,
      changePercent: null,
      sparkline: null,
      priceSource: "none",
      isLoading: isLoading,
    };
  });

  // Loading state
  if (isLoading) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.4 }}
        className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[400px] flex flex-col"
      >
        <div className="flex items-center justify-between px-3 md:px-5 py-3 md:py-4 border-b border-glow-border">
          <h3 className="font-semibold text-white flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-neon-cyan" strokeWidth={2.5} />
            Market Watch
          </h3>
          <span className="text-xs text-text-muted flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-neon-orange animate-pulse-glow" />
            LOADING
          </span>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3 text-text-secondary">
            <span className="animate-spin text-2xl">⏳</span>
            <span>Loading live quotes...</span>
          </div>
        </div>
      </motion.div>
    );
  }

  // Error state
  if (isError) {
    const showConnectCard = isFyersNotConnected || isFyersError || isFyersUnreachable;
    
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.4 }}
        className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[400px] flex flex-col"
      >
        <div className="flex items-center justify-between px-3 md:px-5 py-3 md:py-4 border-b border-glow-border">
          <h3 className="font-semibold text-white flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-neon-cyan" strokeWidth={2.5} />
            Market Watch
          </h3>
          <span className="text-xs text-text-muted flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-neon-red" />
            ERROR
          </span>
        </div>
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-center text-text-secondary max-w-md">
            <p className="mb-2">Failed to load market data</p>
            <p className="text-sm text-neon-red/80 mb-4">{error}</p>
            {showConnectCard && (
              <motion.a
                href="/settings"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black font-bold transition-all duration-300 shadow-glow-cyan hover:opacity-90"
              >
                <Wifi className="w-4 h-4" strokeWidth={2.5} />
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
      transition={{ duration: 0.5, delay: 0.4 }}
      className="glass rounded-2xl border border-glow-border overflow-hidden h-full min-h-[400px] flex flex-col"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 md:px-5 py-3 md:py-4 border-b border-glow-border">
        <h3 className="font-semibold text-white flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-neon-cyan" strokeWidth={2.5} />
          Market Watch
        </h3>
        <motion.button
          onClick={() => mutate()}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-text-secondary hover:text-white hover:bg-card-bg rounded-lg transition-colors"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-neon-green animate-pulse-glow" />
          LIVE
        </motion.button>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-2">
        {displayItems.map((item, index) => {
          const hasPrice = item.price !== null && item.price !== undefined;
          const isPositive = hasPrice && (item.change ?? 0) >= 0;
          const Icon = isPositive ? TrendingUp : isPositive === false ? TrendingDown : Minus;
          const color = isPositive ? "neon-green" : "neon-red";
          const priceColor = isPositive ? "#00FF66" : "#FF003C";
          
          return (
            <motion.div
              key={item.symbol}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4 + index * 0.08 }}
              className={`flex items-center justify-between px-3 py-2 md:px-3 md:py-3 rounded-xl hover:bg-card-bg transition-colors cursor-pointer`}
            >
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <div>
                  <p className="font-medium text-white truncate">{item.symbol}</p>
                  <p className="text-[11px] text-text-muted truncate">{item.name}</p>
                </div>
                {item.sparkline && <SparklineChart data={item.sparkline} color={priceColor} />}
              </div>
              <div className="text-right ml-4 flex-shrink-0">
                {hasPrice ? (
                  <>
                    <p className="font-mono font-semibold text-white whitespace-nowrap">₹{item.price!.toLocaleString()}</p>
                    <div className="flex items-center justify-end gap-1 mt-0.5">
                      <Icon className={`w-3 h-3 text-${color}`} strokeWidth={2.5} />
                      <span className={`text-xs font-medium text-${color}`}>
                        {isPositive ? "+" : ""}{item.changePercent!.toFixed(2)}%
                      </span>
                      <span className={`text-[10px] text-${color}`}>
                        ({isPositive ? "+" : ""}₹{Math.abs(item.change!).toFixed(2)})
                      </span>
                      {item.priceSource === "stale" && (
                        <span className="text-[9px] text-neon-orange ml-1">STALE</span>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="text-text-muted text-sm">No live data</div>
                )}
              </div>
            </motion.div>
          );
        })}
      </div>
      
      {/* Empty state when no Fyers connection */}
      {displayItems.every(item => item.priceSource === "none") && !isLoading && !isError && (
        <div className="flex-1 flex items-center justify-center p-8">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center text-text-secondary max-w-sm"
          >
            <AlertCircle className="w-12 h-12 mx-auto mb-3 text-neon-orange/50" strokeWidth={2} />
            <p className="font-medium text-white mb-1">No live market data</p>
            <p className="text-sm">Connect Fyers to see real-time quotes</p>
            <motion.a
              href="/settings"
              className="mt-4 inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black font-bold transition-all duration-300 shadow-glow-cyan hover:opacity-90"
            >
              <Wifi className="w-4 h-4" strokeWidth={2.5} />
              Connect Fyers
            </motion.a>
          </motion.div>
        </div>
      )}
    </motion.div>
  );
}