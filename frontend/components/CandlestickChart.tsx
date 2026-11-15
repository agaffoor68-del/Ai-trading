"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  ColorType,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";
const UP = "#00FF66";
const DOWN = "#FF003C";

interface Props {
  symbol: string;
  height?: number;
  /** Optional live WebSocket URL. Expected messages: {symbol, ltp|price, volume?} */
  wsUrl?: string;
}

interface Candle {
  time: UTCTimestamp;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// Accepts array of objects, or array of [t,o,h,l,c,v] rows, optionally wrapped in {candles|data}
function normalize(raw: any): Candle[] {
  const rows: any[] = Array.isArray(raw) ? raw : raw?.candles ?? raw?.data ?? [];
  const out: Candle[] = rows
    .map((r) => {
      const a = Array.isArray(r)
        ? { time: r[0], open: r[1], high: r[2], low: r[3], close: r[4], volume: r[5] }
        : r;
      let t = a.time ?? a.timestamp ?? a.t ?? a.datetime;
      if (typeof t === "string") t = Date.parse(t) / 1000;
      if (t > 1e12) t = Math.floor(t / 1000); // ms -> s
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
  // dedupe timestamps (lightweight-charts requires strictly ascending)
  return out.filter((c, i) => i === 0 || c.time !== out[i - 1].time);
}

export function CandlestickChart({ symbol, height = 300, wsUrl }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const lastRef = useRef<Candle | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error" | "empty">("loading");

  // Create chart once
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "#000000" }, textColor: "#9CA3AF" },
      grid: { vertLines: { color: "rgba(255,255,255,0.04)" }, horzLines: { color: "rgba(255,255,255,0.04)" } },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
      timeScale: { borderColor: "rgba(255,255,255,0.1)", timeVisible: true, secondsVisible: false },
    });
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: UP,
      downColor: DOWN,
      borderUpColor: UP,
      borderDownColor: DOWN,
      wickUpColor: UP,
      wickDownColor: DOWN,
    });
    candles.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.25 } });
    const volume = chart.addSeries(HistogramSeries, {
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

  // Load data whenever symbol changes
  useEffect(() => {
    const ctrl = new AbortController();
    setStatus("loading");
    lastRef.current = null;
    candleRef.current?.setData([]);
    volumeRef.current?.setData([]);

    fetch(`${API_URL}/api/v1/market/candles?symbol=${encodeURIComponent(symbol)}&interval=5m`, {
      signal: ctrl.signal,
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((json) => {
        const data = normalize(json);
        if (!data.length) return setStatus("empty");
        candleRef.current?.setData(data.map(({ time, open, high, low, close }) => ({ time, open, high, low, close })));
        volumeRef.current?.setData(
          data.map((c) => ({ time: c.time, value: c.volume, color: c.close >= c.open ? "rgba(0,255,102,0.4)" : "rgba(255,0,60,0.4)" }))
        );
        lastRef.current = data[data.length - 1];
        chartRef.current?.timeScale().fitContent();
        setStatus("ready");
      })
      .catch((e) => {
        if (e.name !== "AbortError") setStatus("error");
      });
    return () => ctrl.abort();
  }, [symbol]);

  // Live ticks: update/extend the last 5m candle
  useEffect(() => {
    if (!wsUrl) return;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data);
        if (m.symbol && m.symbol !== symbol) return;
        const price = Number(m.ltp ?? m.price ?? m.last_price);
        const last = lastRef.current;
        if (!Number.isFinite(price) || !last) return;
        const bucket = (Math.floor(Date.now() / 1000 / 300) * 300) as UTCTimestamp;
        const vol = Number(m.volume ?? 0) || 0;
        const next: Candle =
          bucket > last.time
            ? { time: bucket, open: price, high: price, low: price, close: price, volume: vol }
            : { ...last, high: Math.max(last.high, price), low: Math.min(last.low, price), close: price, volume: last.volume + vol };
        lastRef.current = next;
        candleRef.current?.update({ time: next.time, open: next.open, high: next.high, low: next.low, close: next.close });
        volumeRef.current?.update({ time: next.time, value: next.volume, color: next.close >= next.open ? "rgba(0,255,102,0.4)" : "rgba(255,0,60,0.4)" });
      } catch {}
    };
    return () => ws.close();
  }, [wsUrl, symbol]);

  return (
    <div className="relative w-full bg-black rounded-2xl border border-glow-border overflow-hidden" style={{ height }}>
      <div className="absolute top-2 left-3 z-10 text-xs font-mono text-white/80 pointer-events-none">
        {symbol} · 5m
      </div>
      <div ref={containerRef} className="absolute inset-0" />
      {status !== "ready" && (
        <div className="absolute inset-0 z-10 flex items-center justify-center text-sm text-white/60 bg-black/60 pointer-events-none">
          {status === "loading" && "Loading candles..."}
          {status === "empty" && "No candle data"}
          {status === "error" && "Failed to load candles"}
        </div>
      )}
    </div>
  );
}
