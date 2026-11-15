"use client";

import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import useSWR from "swr";
import { api, formatFyersSymbol } from "@/lib/api";

interface QuoteData {
  ltp: number | null;
  change: number | null;
  change_percent: number | null;
  source: string;
  updated_at: string | null;
}

interface QuotesResponse {
  quotes: Record<string, QuoteData>;
}

interface DisplayItem {
  symbol: string;
  name: string;
  price: number | null;
  change: number | null;
  changePercent: number | null;
  sparkline: number[];
  priceSource: "live" | "none";
}

// Default symbols to show on dashboard
const DEFAULT_SYMBOLS = ["NIFTY 50", "BANKNIFTY", "RELIANCE", "TCS", "HDFC BANK"];

function generateSparkline(basePrice: number): number[] {
  return Array(8).fill(0).map((_, i) => basePrice + (Math.random() - 0.5) * basePrice * 0.02);
}

function SparklineChart({ data, color }: { data: number[]; color: string }) {
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
      <circle cx={points.split(" ").slice(-1)[0].split(",")[0]} cy={points.split(" ").slice(-1)[0].split(",")[1]} r={2} fill={color} className="animate-pulse" />
    </svg>
  );
}

export function MarketWatch() {
  // Use SWR to fetch live quotes
  const { data: quotesData, isLoading, error } = useSWR<QuotesResponse>(
    ["dashboard-quotes", DEFAULT_SYMBOLS] as const,
    async ([, symbols]: readonly [string, readonly string[]]) => {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com"}/api/v1/market/quotes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbols }),
        signal: AbortSignal.timeout(8000),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      return { quotes: data.quotes || {} };
    },
    {
      refreshInterval: 5000,
      revalidateOnFocus: false,
      dedupingInterval: 2000,
      fallbackData: { quotes: {} }
    }
  );

  // Build display items
  const displayItems: DisplayItem[] = DEFAULT_SYMBOLS.map((symbol) => {
    const quote = quotesData?.quotes[formatFyersSymbol(symbol)] || quotesData?.quotes[symbol];
    
    if (quote && quote.ltp !== null && quote.ltp !== undefined) {
      return {
        symbol,
        name: symbol,
        price: quote.ltp,
        change: quote.change ?? 0,
        changePercent: quote.change_percent ?? 0,
        sparkline: generateSparkline(quote.ltp),
        priceSource: "live" as const,
      };
    }
    return {
      symbol,
      name: symbol,
      price: null,
      change: null,
      changePercent: null,
      sparkline: Array(8).fill(0),
      priceSource: "none" as const,
    };
  });

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
          <div className="flex items-center gap-3 text-text-secondary">
            <span className="animate-spin">⏳</span>
            <span>Loading live quotes...</span>
          </div>
        </div>
      </motion.div>
    );
  }

  if (error) {
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
          <div className="text-center text-text-secondary">
            <p className="mb-2">Failed to load market data</p>
            <p className="text-sm text-neon-red/80">{error.message}</p>
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
        <span className="text-xs text-text-muted flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-neon-green animate-pulse-glow" />
          LIVE
        </span>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-2">
        {displayItems.map((item, index) => {
          const hasPrice = item.price !== null && item.price !== undefined;
          const isPositive = hasPrice && (item.change ?? 0) >= 0;
          const Icon = isPositive ? TrendingUp : isPositive === false ? TrendingDown : Minus;
          const color = isPositive ? "neon-green" : "neon-red";
          
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
                <SparklineChart data={item.sparkline} color={isPositive ? "#00FF66" : "#FF003C"} />
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
    </motion.div>
  );
}
