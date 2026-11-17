"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import {
  createChart,
  ColorType,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
  type Time,
} from "lightweight-charts";
import { motion } from "framer-motion";
import { ChevronDown, Maximize2, AlertCircle, Wifi } from "lucide-react";
import { useCandles, useMarketQuotes, formatFyersSymbol } from "@/lib/hooks";

const UP = "#00FF66";
const DOWN = "#FF003C";

interface Props {
  symbol?: string;
  height?: number;
}

const INTERVALS = [
  { value: "1m", label: "1m", days: 1 },
  { value: "5m", label: "5m", days: 3 },
  { value: "15m", label: "15m", days: 5 },
  { value: "1h", label: "1h", days: 30 },
  { value: "1D", label: "1D", days: 100 },
] as const;

interface Candle {
  time: UTCTimestamp;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

function normalize(raw: any[]): Candle[] {
  const out: Candle[] = raw
    .map((r) => {
      const a = Array.isArray(r)
        ? { time: r[0], open: r[1], high: r[2], low: r[3], close: r[4], volume: r[5] }
        : r;
      let t = a.time ?? a.timestamp ?? a.t ?? a.datetime;
      if (typeof t === "string") t = Date.parse(t) / 1000;
      if (t > 1e12) t = Math.floor(t / 1000); // ms -> s
      // Convert to IST (add 19800 seconds)
      t = t + 19800;
      return {
        time: t as UTCTimestamp,
        open: Number(a.open ?? a.o),
        high: Number(a.high ?? a.h),
        low: Number(a.low ?? a.l),
        close: Number(a.close ?? a.c),
        volume: Number(a.volume ?? a.v ?? 0),
      };
    })
    .filter((c) => c.time && [c.open, c.high, c.low, c.close].every(Number.isFinite))
    .sort((a, b) => a.time - b.time);
  // dedupe timestamps
  return out.filter((c, i) => i === 0 || c.time !== out[i - 1].time);
}

function formatISTTime(timestamp: UTCTimestamp): string {
  const date = new Date((timestamp - 19800) * 1000);
  return date.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata" });
}

export function CandlestickChart({ symbol: initialSymbol = "NIFTY 50", height = 400 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const lastRef = useRef<Candle | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error" | "empty">("loading");
  const [selectedInterval, setSelectedInterval] = useState<typeof INTERVALS[number]["value"]>(INTERVALS[1].value); // 5m default
  const [selectedSymbol, setSelectedSymbol] = useState(initialSymbol);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  
  // Fetch quotes for live LTP updates
  const { quotes, isError: quotesError, mutate: mutateQuotes } = useMarketQuotes([selectedSymbol]);
  
  // Fetch candles
  const intervalConfig = INTERVALS.find(i => i.value === selectedInterval) || INTERVALS[1];
  const { candles, isLoading, isError, error, errorCode, isFyersNotConnected, isFyersError, isFyersUnreachable, mutate } = useCandles(
    formatFyersSymbol(selectedSymbol), 
    selectedInterval, 
    intervalConfig.days
  );

  // Create chart once
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "#000000" }, textColor: "#9CA3AF" },
      grid: { vertLines: { color: "rgba(255,255,255,0.04)" }, horzLines: { color: "rgba(255,255,255,0.04)" } },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
      timeScale: { 
        borderColor: "rgba(255,255,255,0.1)", 
        timeVisible: true, 
        secondsVisible: false,
        tickMarkFormatter: (time: UTCTimestamp) => formatISTTime(time),
      },
    });
    const candles = chart.addCandlestickSeries({
      upColor: UP,
      downColor: DOWN,
      borderUpColor: UP,
      borderDownColor: DOWN,
      wickUpColor: UP,
      wickDownColor: DOWN,
    });
    candles.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.25 } });
    const volume = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

    chartRef.current = chart;
    candleRef.current = candles;
    volumeRef.current = volume;
    return () => {
      chart.remove();
      chartRef.current = candleRef.current = volumeRef.current = null;
    };
  }, []);

  // Load data whenever symbol or interval changes
  useEffect(() => {
    if (!candles || candles.length === 0) {
      setStatus(isLoading ? "loading" : isError ? "error" : "empty");
      return;
    }
    
    const data = normalize(candles);
    if (!data.length) {
      setStatus("empty");
      return;
    }
    
    candleRef.current?.setData(data.map(({ time, open, high, low, close }) => ({ time, open, high, low, close })));
    volumeRef.current?.setData(
      data.map((c) => ({ 
        time: c.time, 
        value: c.volume, 
        color: c.close >= c.open ? "rgba(0,255,102,0.4)" : "rgba(255,0,60,0.4)" 
      }))
    );
    lastRef.current = data[data.length - 1];
    chartRef.current?.timeScale().fitContent();
    setStatus("ready");
    setErrorMessage(null);
  }, [candles, isLoading, isError, error]);

  // Handle quotes for live LTP update of last candle
  useEffect(() => {
    if (!quotes || !lastRef.current) return;
    
    const fyersSymbol = formatFyersSymbol(selectedSymbol);
    const quote = quotes[fyersSymbol] || quotes[selectedSymbol];
    if (!quote || quote.ltp === null) return;
    
    const last = lastRef.current;
    const bucket = (Math.floor(Date.now() / 1000 / 300) * 300) + 19800; // IST bucket
    const price = Number(quote.ltp);
    
    if (!Number.isFinite(price)) return;
    
    const next: Candle = bucket > last.time
      ? { time: bucket as UTCTimestamp, open: price, high: price, low: price, close: price, volume: 0 }
      : { ...last, high: Math.max(last.high, price), low: Math.min(last.low, price), close: price };
    
    lastRef.current = next;
    candleRef.current?.update({ time: next.time, open: next.open, high: next.high, low: next.low, close: next.close });
  }, [quotes, selectedSymbol]);

  // Handle resize
  useEffect(() => {
    const handleResize = () => chartRef.current?.resize(window.innerWidth, window.innerHeight);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const showConnectCard = isFyersNotConnected || isFyersError || isFyersUnreachable;
  const showError = isError && !isLoading;

  const handleSymbolChange = (newSymbol: string) => {
    setSelectedSymbol(newSymbol);
  };

  return (
    <div className="relative w-full bg-black rounded-2xl border border-glow-border overflow-hidden" style={{ height }}>
      {/* Header with controls */}
      <div className="absolute top-2 left-3 right-3 z-10 flex items-center justify-between gap-2 px-2 pointer-events-none">
        <div className="pointer-events-auto flex items-center gap-2">
          <span className="text-xs font-mono text-white/80">
            {selectedSymbol} · {INTERVALS.find(i => i.value === selectedInterval)?.label || selectedInterval}
          </span>
          {status === "ready" && lastRef.current && (
            <span className="text-xs font-mono text-neon-green/80">
              LTP: ₹{lastRef.current.close.toFixed(2)}
            </span>
          )}
        </div>
        
        <div className="pointer-events-auto flex items-center gap-1">
          {/* Symbol selector */}
          <select
            value={selectedSymbol}
            onChange={(e) => handleSymbolChange(e.target.value)}
            className="px-2 py-1 bg-card-bg border border-glow-border rounded-lg text-white text-xs focus:border-neon-cyan focus:outline-none pointer-events-auto"
          >
            <option value="NIFTY 50">NIFTY 50</option>
            <option value="BANKNIFTY">BANKNIFTY</option>
            <option value="FINNIFTY">FINNIFTY</option>
            <option value="MIDCPNIFTY">MIDCPNIFTY</option>
            <option value="SENSEX">SENSEX</option>
            <option value="RELIANCE">RELIANCE</option>
            <option value="TCS">TCS</option>
            <option value="HDFC BANK">HDFC BANK</option>
            <option value="ICICI BANK">ICICI BANK</option>
            <option value="SBIN">SBIN</option>
            <option value="INFY">INFY</option>
          </select>
          
          {/* Timeframe selector */}
          <select
            value={selectedInterval}
            onChange={(e) => setSelectedInterval(e.target.value as "5m" | "15m" | "1h" | "1D" | "1m")}
            className="px-2 py-1 bg-card-bg border border-glow-border rounded-lg text-white text-xs focus:border-neon-cyan focus:outline-none pointer-events-auto"
          >
            {INTERVALS.map((i) => (
              <option key={i.value} value={i.value}>{i.label}</option>
            ))}
          </select>
          
          <motion.button
            onClick={() => mutate()}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="p-1.5 rounded-lg bg-card-bg border border-glow-border hover:border-neon-cyan/50 transition-colors pointer-events-auto"
            title="Refresh"
          >
            <Maximize2 className="w-4 h-4 text-text-secondary" strokeWidth={2} />
          </motion.button>
        </div>
      </div>

      <div ref={containerRef} className="absolute inset-0" />
      
      {status !== "ready" && (
        <div className="absolute inset-0 z-10 flex items-center justify-center text-sm text-white/60 bg-black/60 pointer-events-none flex-col gap-2 p-4">
          {status === "loading" && (
            <>
              <span className="animate-spin text-xl">⏳</span>
              <span>Loading candles...</span>
            </>
          )}
          {status === "empty" && (
            <>
              <AlertCircle className="w-8 h-8 text-neon-orange/50" strokeWidth={2} />
              <span>No candle data for this symbol/interval</span>
            </>
          )}
          {showError && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center max-w-md"
            >
              <AlertCircle className="w-8 h-8 mx-auto mb-2 text-neon-red/80" strokeWidth={2} />
              <p className="font-medium text-white mb-1">Failed to load candles</p>
              <p className="text-sm text-neon-red/80 mb-3">{errorMessage || error}</p>
              {showConnectCard && (
                <motion.a
                  href="/broker-connect"
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-purple text-true-black font-bold transition-all duration-300 shadow-glow-cyan hover:opacity-90"
                >
                  <Wifi className="w-4 h-4" strokeWidth={2.5} />
                  Connect Fyers
                </motion.a>
              )}
            </motion.div>
          )}
        </div>
      )}
    </div>
  );
}
