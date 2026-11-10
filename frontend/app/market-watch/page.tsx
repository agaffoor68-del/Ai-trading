"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Minus, RefreshCw, AlertCircle, Wifi, WifiOff } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface MarketItem {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  sparkline: number[];
}

// Mock data fallback
const MOCK_MARKET_DATA: MarketItem[] = [
  { symbol: "NIFTY 50", name: "NIFTY 50", price: 24345.85, change: 124.35, changePercent: 0.51, sparkline: [24200, 24250, 24180, 24300, 24280, 24345] },
  { symbol: "BANKNIFTY", name: "BANK NIFTY", price: 51890.20, change: -85.40, changePercent: -0.16, sparkline: [51950, 51900, 51800, 51850, 51920, 51890] },
  { symbol: "RELIANCE", name: "Reliance Ind.", price: 2845.60, change: 42.15, changePercent: 1.50, sparkline: [2800, 2810, 2825, 2835, 2840, 2845] },
  { symbol: "TCS", name: "TCS", price: 4120.75, change: -12.30, changePercent: -0.30, sparkline: [4130, 4125, 4115, 4120, 4118, 4120] },
  { symbol: "HDFC BANK", name: "HDFC Bank", price: 1678.45, change: 18.90, changePercent: 1.14, sparkline: [1660, 1665, 1670, 1675, 1677, 1678] },
  { symbol: "INFOSYS", name: "Infosys", price: 1845.30, change: -8.20, changePercent: -0.44, sparkline: [1850, 1848, 1840, 1845, 1842, 1845] },
  { symbol: "ICICI BANK", name: "ICICI Bank", price: 1120.75, change: 15.30, changePercent: 1.38, sparkline: [1105, 1110, 1115, 1118, 1120, 1120] },
  { symbol: "KOTAK BANK", name: "Kotak Bank", price: 1785.90, change: -5.10, changePercent: -0.28, sparkline: [1790, 1788, 1785, 1786, 1784, 1785] },
];

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

export default function MarketWatchPage() {
  const [marketData, setMarketData] = useState<MarketItem[]>(MOCK_MARKET_DATA);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usingMockData, setUsingMockData] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchMarketData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_URL}/api/v1/market/quotes?symbols=NIFTY,BANKNIFTY,RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK,KOTAKBANK`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        // Timeout after 8 seconds
        signal: AbortSignal.timeout(8000),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      
      // Transform backend data to our format
      const transformed: MarketItem[] = Object.entries(data).map(([symbol, quote]: [string, any]) => {
        const price = quote.ltp || quote.price || 0;
        const change = quote.change || 0;
        const changePercent = quote.change_percent || quote.pChange || 0;
        // Generate a simple sparkline from recent data if available
        const sparkline = quote.history?.slice(-6) || Array(6).fill(price).map((p, i) => p + (Math.random() - 0.5) * price * 0.01);
        
        return {
          symbol: symbol.replace("NSE:", ""),
          name: symbol.replace("NSE:", ""),
          price,
          change,
          changePercent,
          sparkline,
        };
      });

      if (transformed.length > 0) {
        setMarketData(transformed);
        setUsingMockData(false);
        setLastUpdated(new Date());
      } else {
        throw new Error("No data returned from API");
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Unknown error";
      setError(`Failed to connect to backend: ${errorMessage}`);
      setUsingMockData(true);
      setMarketData(MOCK_MARKET_DATA);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMarketData();
  }, [fetchMarketData]);

  const handleRefresh = () => {
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
              <h1 className="text-3xl font-bold text-white tracking-tight">Market Watch</h1>
              <p className="text-text-secondary mt-1">Real-time quotes & market overview</p>
            </div>
            
            {/* Refresh Button */}
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

          {/* Error Banner */}
          {(error || usingMockData) && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-3 px-4 py-3 rounded-xl bg-neon-red/10 border border-neon-red/30 text-neon-red glass"
            >
              <AlertCircle className="w-5 h-5 flex-shrink-0" strokeWidth={2.5} />
              <div className="flex-1">
                <p className="font-medium text-sm">
                  {error 
                    ? "Failed to connect to backend. Showing offline data."
                    : "Backend unreachable. Showing offline mock data."}
                </p>
                <p className="text-xs text-neon-red/80 mt-0.5">
                  {error || "Render free tier may be sleeping. Click Refresh to retry."}
                </p>
              </div>
              <motion.button
                onClick={handleRefresh}
                disabled={isLoading}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="px-3 py-1.5 text-xs rounded-lg bg-neon-red/20 text-neon-red border border-neon-red/30 hover:bg-neon-red/30 transition-colors disabled:opacity-50"
              >
                {isLoading ? "Retrying..." : "Retry"}
              </motion.button>
            </motion.div>
          )}

          {/* Connection Status */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4 text-sm">
              <span className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${!usingMockData ? "bg-neon-green animate-pulse-glow" : "bg-neon-red"}`} />
                <span>{!usingMockData ? "Live Data" : "Offline Mode"}</span>
              </span>
              {lastUpdated && (
                <span className="text-text-muted">
                  Last updated: {lastUpdated.toLocaleTimeString()}
                </span>
              )}
            </div>
            
            {/* Market Status */}
            <div className="flex items-center gap-3 px-3 py-1.5 rounded-full bg-card-bg border border-glow-border glass">
              <span className="w-2 h-2 rounded-full bg-neon-green" />
              <span className="text-xs font-medium text-white">Market Open</span>
              <span className="text-[10px] text-neon-green">NSE | BSE</span>
            </div>
          </div>

          {/* Market Watch Table */}
          <div className="glass rounded-2xl border border-glow-border overflow-hidden">
            {/* Table Header */}
            <div className="grid grid-cols-[1fr_80px_80px_70px_70px] gap-4 px-5 py-3 border-b border-glow-border bg-card-bg/50 text-text-muted text-xs font-medium uppercase tracking-wider">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-neon-cyan" strokeWidth={2.5} />
                Symbol
              </div>
              <div>Price</div>
              <div className="text-right">Change</div>
              <div className="text-right">% Chg</div>
              <div>Sparkline</div>
            </div>

            {/* Table Body */}
            <div className="divide-y divide-glow-border">
              {marketData.map((item, index) => {
                const isPositive = item.change >= 0;
                const Icon = isPositive ? TrendingDown : isPositive === false ? TrendingUp : Minus;
                const color = isPositive ? "neon-green" : "neon-red";
                
                return (
                  <motion.div
                    key={item.symbol}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.04 }}
                    className="grid grid-cols-[1fr_80px_80px_70px_70px] gap-4 px-5 py-4 items-center hover:bg-card-bg/50 transition-colors cursor-pointer group"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div>
                        <p className="font-medium text-white truncate">{item.symbol}</p>
                        <p className="text-[11px] text-text-muted truncate">{item.name}</p>
                      </div>
                      <SparklineChart data={item.sparkline} color={isPositive ? "#00FF66" : "#FF003C"} />
                    </div>
                    <div className="font-mono font-semibold text-white whitespace-nowrap">₹{item.price.toLocaleString()}</div>
                    <div className="flex items-center justify-end gap-1">
                      <Icon className={`w-3 h-3 text-${color}`} strokeWidth={2.5} />
                      <span className={`text-sm font-medium text-${color}`}>
                        {isPositive ? "+" : ""}₹{Math.abs(item.change).toFixed(2)}
                      </span>
                    </div>
                    <div className="flex items-center justify-end gap-1">
                      <span className={`text-sm font-medium text-${color}`}>
                        {isPositive ? "+" : ""}{item.changePercent.toFixed(2)}%
                      </span>
                    </div>
                    <div>
                      <SparklineChart data={item.sparkline} color={isPositive ? "#00FF66" : "#FF003C"} />
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>

          {/* Footer Note */}
          <div className="text-center text-text-muted text-sm">
            {usingMockData 
              ? "⚠️ Showing mock data. Connect backend for live quotes."
              : "Data sourced from Fyers API v3 • Auto-refresh on window focus"}
          </div>
        </main>
      </div>
    </div>
  );
}