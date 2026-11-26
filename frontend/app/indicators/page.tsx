"use client";

import { useMemo, useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { useIndicatorLibrary, useIndicatorCalculation, type IndicatorDefinition } from "@/lib/hooks";
import {
  Search, Star, StarOff, SlidersHorizontal, Loader2, AlertCircle, RefreshCw,
  ChevronDown, ChevronRight, Sigma, Activity, LineChart,
} from "lucide-react";

const STATUS_LABEL: Record<string, { label: string; cls: string }> = {
  implemented_tested: { label: "Ready", cls: "bg-neon-green/20 text-neon-green border-neon-green/30" },
  implemented_awaiting_data: { label: "Needs feed", cls: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30" },
  unsupported_data: { label: "No feed", cls: "bg-neon-red/15 text-neon-red border-neon-red/30" },
  partial: { label: "Partial", cls: "bg-neon-cyan/15 text-neon-cyan border-neon-cyan/30" },
  not_implemented: { label: "Planned", cls: "bg-card-bg text-text-muted border-glow-border" },
};

const TIMEFRAMES = ["1m", "3m", "5m", "10m", "15m", "30m", "1h", "2h", "4h", "1d", "1wk", "1mo"];

function fmt(value: any): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "—";
    return Math.abs(value) >= 1000 ? value.toFixed(0) : value.toFixed(2);
  }
  if (typeof value === "object") return `${Array.isArray(value) ? value.length : Object.keys(value).length} pts`;
  return String(value);
}

function latest(series: any): any {
  if (!Array.isArray(series)) return null;
  for (let i = series.length - 1; i >= 0; i--) if (series[i] !== null && series[i] !== undefined) return series[i];
  return null;
}

export default function IndicatorsPage() {
  const [category, setCategory] = useState<string>("");
  const [q, setQ] = useState("");
  const [sortAlpha, setSortAlpha] = useState(false);
  const [onlyFav, setOnlyFav] = useState(false);
  const [favorites, setFavorites] = useState<Record<string, boolean>>({});
  const [enabled, setEnabled] = useState<Record<string, boolean>>({});
  const [expanded, setExpanded] = useState<string | null>(null);
  const [symbol, setSymbol] = useState("NIFTY");
  const [interval, setInterval] = useState("15m");
  const [flatParams, setFlatParams] = useState<Record<string, any>>({});
  const [selected, setSelected] = useState<string[]>(["rsi", "macd", "supertrend"]);

  const { indicators, categories, total, libraryTotal, isLoading, isError, error, mutate } = useIndicatorLibrary({ category: category || undefined, q: q || undefined });
  const calc = useIndicatorCalculation(symbol, interval, selected, selected.length > 0, flatParams);

  const visible = useMemo(() => {
    let list = [...indicators];
    if (onlyFav) list = list.filter((i) => favorites[i.id]);
    if (sortAlpha) list.sort((a, b) => a.name.localeCompare(b.name));
    return list;
  }, [indicators, onlyFav, favorites, sortAlpha]);

  const toggle = (id: string, key: "favorites" | "enabled") => {
    if (key === "favorites") setFavorites((p) => ({ ...p, [id]: !p[id] }));
    else setEnabled((p) => ({ ...p, [id]: p[id] === false }));
  };
  const toggleSelect = (id: string) => setSelected((p) => p.includes(id) ? p.filter((x) => x !== id) : [...p, id].slice(-12));

  return (
    <div className="min-h-screen bg-true-black">
      <Sidebar />
      <div className="lg:pl-64">
        <Header />
        <main className="p-4 md:p-8 pt-20 max-w-[1600px] mx-auto space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold text-white">Indicator Library</h1>
              <p className="text-sm text-text-secondary">{libraryTotal} indicators across 8 categories · {total} shown</p>
            </div>
            <button onClick={() => mutate()} className="inline-flex items-center gap-2 text-sm px-3 py-2 rounded-lg border border-glow-border text-text-secondary hover:text-white">
              <RefreshCw className="w-4 h-4" /> Refresh
            </button>
          </div>

          {categories.length > 0 && (
            <div className="flex gap-2 overflow-x-auto pb-1">
              <button onClick={() => setCategory("")} className={`whitespace-nowrap px-3 py-1.5 rounded-lg text-xs border ${!category ? "bg-neon-cyan/20 text-neon-cyan border-neon-cyan/40" : "border-glow-border text-text-secondary"}`}>All ({libraryTotal})</button>
              {categories.map((c) => (
                <button key={c.id} onClick={() => setCategory(c.id)} className={`whitespace-nowrap px-3 py-1.5 rounded-lg text-xs border ${category === c.id ? "bg-neon-cyan/20 text-neon-cyan border-neon-cyan/40" : "border-glow-border text-text-secondary"}`}>
                  {c.label} ({c.count})
                </button>
              ))}
            </div>
          )}

          <div className="glass rounded-2xl border border-glow-border p-3 md:p-4 grid grid-cols-1 md:grid-cols-[1fr_auto_auto_auto] gap-3 items-end">
            <label className="relative">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-text-muted" />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search 169 indicators (e.g. RSI, Fibonacci, GEX)" className="w-full bg-card-bg/60 border border-glow-border rounded-lg pl-9 pr-3 py-2 text-sm text-white" />
            </label>
            <button onClick={() => setSortAlpha((s) => !s)} className={`px-3 py-2 rounded-lg text-xs border ${sortAlpha ? "bg-neon-cyan/20 text-neon-cyan border-neon-cyan/40" : "border-glow-border text-text-secondary"}`}>A-Z {sortAlpha ? "on" : "off"}</button>
            <button onClick={() => setOnlyFav((s) => !s)} className={`px-3 py-2 rounded-lg text-xs border ${onlyFav ? "bg-yellow-500/20 text-yellow-400 border-yellow-500/40" : "border-glow-border text-text-secondary"}`}>★ Favourites</button>
            <span className="text-xs text-text-muted inline-flex items-center gap-1"><SlidersHorizontal className="w-3.5 h-3.5" /> {Object.values(enabled).filter((v) => v !== false).length} enabled</span>
          </div>

          <div className="glass rounded-2xl border border-glow-border p-3 md:p-4 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <LineChart className="w-4 h-4 text-neon-cyan" />
              <span className="text-sm text-white font-medium">Live calculation</span>
              <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} className="bg-card-bg/60 border border-glow-border rounded-lg px-2 py-1.5 text-sm text-white w-32" />
              <select value={interval} onChange={(e) => setInterval(e.target.value)} className="bg-card-bg/60 border border-glow-border rounded-lg px-2 py-1.5 text-sm text-white">
                {TIMEFRAMES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <span className="text-xs text-text-muted">{calc.data?.candles ?? 0} candles{calc.data?.as_of ? ` · ${new Date(calc.data.as_of * 1000).toLocaleString("en-IN")}` : ""}</span>
              {calc.isLoading && <Loader2 className="w-4 h-4 animate-spin text-neon-cyan" />}
            </div>
            {selected.length === 0 ? <p className="text-xs text-text-muted">Select indicators below (checkbox) to calculate them on real candles.</p> : (
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
                {selected.map((id) => {
                  const r = calc.data?.results?.[id];
                  const s = r?.series || {};
                  const primary = Object.keys(s)[0];
                  const v = primary ? latest(s[primary]) : null;
                  const status = r?.status || (calc.isLoading ? "loading" : "—");
                  return (
                    <div key={id} className="bg-card-bg/50 border border-glow-border rounded-xl p-2.5">
                      <p className="text-[11px] text-text-muted truncate">{id}</p>
                      <p className="text-lg font-mono text-white">{fmt(v)}</p>
                      <p className="text-[10px] text-text-muted">{status === "data_available" || status === "implemented" ? primary : status.replace(/_/g, " ")}</p>
                    </div>
                  );
                })}
              </div>
            )}
            {calc.data?.message && <p className="text-xs text-yellow-400 inline-flex items-center gap-1"><AlertCircle className="w-3.5 h-3.5" /> {calc.data.message}</p>}
            {calc.isError && <p className="text-xs text-neon-red">{calc.error}</p>}
            {Object.keys(flatParams).length > 0 && <p className="text-[11px] text-text-muted">Custom params: {JSON.stringify(flatParams)}</p>}
          </div>

          {isLoading && <div className="flex items-center gap-2 text-text-secondary"><Loader2 className="w-4 h-4 animate-spin" /> Loading library…</div>}
          {isError && <div className="glass rounded-2xl border border-neon-red/30 p-4 text-sm text-neon-red">{error || "Failed to load the indicator library."}</div>}

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {visible.map((ind: IndicatorDefinition) => {
              const st = STATUS_LABEL[ind.status] || STATUS_LABEL.not_implemented;
              const open = expanded === ind.id;
              const isSel = selected.includes(ind.id);
              const isFav = !!favorites[ind.id];
              const isEnabled = enabled[ind.id] !== false;
              return (
                <div key={ind.id} className="glass rounded-2xl border border-glow-border p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="text-sm font-semibold text-white truncate">{ind.name}</h3>
                        <span className={`text-[10px] px-2 py-0.5 rounded border ${st.cls}`}>{st.label}</span>
                        {ind.repaint && <span className="text-[10px] px-2 py-0.5 rounded border bg-yellow-500/15 text-yellow-400 border-yellow-500/30">Repaints</span>}
                      </div>
                      <p className="text-[11px] text-text-muted mt-0.5">{ind.category_label} · {ind.chart === "overlay" ? "Chart overlay" : "Separate pane"} · {ind.required_data}</p>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <input type="checkbox" checked={isSel} onChange={() => toggleSelect(ind.id)} className="accent-cyan-400 w-4 h-4" aria-label={`Calculate ${ind.name}`} />
                      <button onClick={() => toggle(ind.id, "favorites")} aria-label="Toggle favourite" className="p-1 text-yellow-400">{isFav ? <Star className="w-4 h-4 fill-current" /> : <StarOff className="w-4 h-4 text-text-muted" />}</button>
                      <button onClick={() => toggle(ind.id, "enabled")} aria-label="Toggle enabled" className={`text-[10px] px-2 py-1 rounded border ${isEnabled ? "border-neon-green/40 text-neon-green" : "border-glow-border text-text-muted"}`}>{isEnabled ? "ON" : "OFF"}</button>
                    </div>
                  </div>
                  <p className="text-xs text-text-secondary mt-2">{ind.description}</p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {ind.params.length === 0 ? <span className="text-[10px] text-text-muted">No parameters</span> : ind.params.map((p) => (
                      <span key={p.name} className="text-[10px] px-2 py-0.5 rounded bg-card-bg/70 border border-glow-border text-text-secondary">{p.label}: {p.default}</span>
                    ))}
                  </div>
                  <button onClick={() => setExpanded(open ? null : ind.id)} className="mt-3 text-xs text-neon-cyan inline-flex items-center gap-1">
                    {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />} {open ? "Hide details" : "Formula, interpretation & limits"}
                  </button>
                  {open && (
                    <div className="mt-3 space-y-2.5 text-xs">
                      <div><p className="text-text-muted inline-flex items-center gap-1"><Sigma className="w-3.5 h-3.5" /> Formula</p><p className="font-mono text-[11px] text-white bg-true-black/60 rounded p-2 break-words">{ind.formula}</p></div>
                      <div><p className="text-text-muted">Parameters</p><div className="grid grid-cols-2 md:grid-cols-3 gap-1.5">{ind.params.map((p) => (
                        <label key={p.name} className="flex items-center justify-between gap-1 bg-card-bg/50 border border-glow-border rounded px-2 py-1">
                          <span className="text-[10px] text-text-secondary truncate">{p.label}</span>
                          <input type={p.type === "str" ? "text" : "number"} defaultValue={p.default} min={p.min} max={p.max} step={p.step ?? (p.type === "int" ? 1 : 0.1)}
                            onChange={(e) => setFlatParams((prev) => ({ ...prev, [p.name]: p.type === "str" ? e.target.value : Number(e.target.value) }))}
                            className="w-16 bg-transparent text-right text-[11px] text-white" />
                        </label>
                      ))}{ind.params.length === 0 && <span className="text-[10px] text-text-muted">—</span>}</div></div>
                      <div className="flex flex-wrap gap-2 text-[10px] text-text-muted"><span>Markets: {ind.markets.join(", ")}</span><span>TF: {ind.timeframes.join(" ")}</span></div>
                      <div><p className="text-text-muted inline-flex items-center gap-1"><Activity className="w-3.5 h-3.5" /> Interpretation</p><p className="text-text-secondary">{ind.interpretation}</p></div>
                      <div><p className="text-text-muted">Limitations</p><p className="text-yellow-400/90">{ind.limitations}{ind.note ? ` ${ind.note}` : ""}</p></div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {!isLoading && visible.length === 0 && <p className="text-center text-text-secondary py-10">No indicators match these filters.</p>}
        </main>
      </div>
    </div>
  );
}
