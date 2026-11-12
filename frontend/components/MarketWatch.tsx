"use client";

import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface MarketItem {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  sparkline: number[];
}

const mockMarketData: MarketItem[] = [
  { symbol: "NIFTY 50", name: "NIFTY 50", price: 24345.85, change: 124.35, changePercent: 0.51, sparkline: [24200, 24250, 24180, 24300, 24280, 24345] },
  { symbol: "BANKNIFTY", name: "BANK NIFTY", price: 51890.20, change: -85.40, changePercent: -0.16, sparkline: [51950, 51900, 51800, 51850, 51920, 51890] },
  { symbol: "RELIANCE", name: "Reliance Ind.", price: 2845.60, change: 42.15, changePercent: 1.50, sparkline: [2800, 2810, 2825, 2835, 2840, 2845] },
  { symbol: "TCS", name: "TCS", price: 4120.75, change: -12.30, changePercent: -0.30, sparkline: [4130, 4125, 4115, 4120, 4118, 4120] },
  { symbol: "HDFC BANK", name: "HDFC Bank", price: 1678.45, change: 18.90, changePercent: 1.14, sparkline: [1660, 1665, 1670, 1675, 1677, 1678] },
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

export function MarketWatch() {
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
        {mockMarketData.map((item, index) => {
          const isPositive = item.change >= 0;
          const Icon = isPositive ? TrendingUp : isPositive === false ? TrendingDown : Minus;
          const color = isPositive ? "neon-green" : "neon-red";
          
          return (
            <motion.div
              key={item.symbol}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4 + index * 0.08 }}
              className="flex items-center justify-between px-3 py-2 md:px-3 md:py-3 rounded-xl hover:bg-card-bg transition-colors group cursor-pointer"
            >
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <div>
                  <p className="font-medium text-white truncate">{item.symbol}</p>
                  <p className="text-[11px] text-text-muted truncate">{item.name}</p>
                </div>
                <SparklineChart data={item.sparkline} color={isPositive ? "#00FF66" : "#FF003C"} />
              </div>
              <div className="text-right ml-4 flex-shrink-0">
                <p className="font-mono font-semibold text-white whitespace-nowrap">₹{item.price.toLocaleString()}</p>
                <div className="flex items-center justify-end gap-1 mt-0.5">
                  <Icon className={`w-3 h-3 text-${color}`} strokeWidth={2.5} />
                  <span className={`text-xs font-medium text-${color}`}>
                    {isPositive ? "+" : ""}{item.changePercent.toFixed(2)}%
                  </span>
                  <span className={`text-[10px] text-${color}`}>
                    ({isPositive ? "+" : ""}₹{Math.abs(item.change).toFixed(2)})
                  </span>
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </motion.div>
  );
}