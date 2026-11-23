"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertCircle, Loader2, RefreshCw } from "lucide-react";
import { api } from "@/lib/api-client";

interface ChainRow {
  strike_price: number;
  call_ltp: number | null;
  call_symbol: string | null;
  put_ltp: number | null;
  put_symbol: string | null;
  is_atm: boolean;
}

const SYMBOLS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"];

export function OptionsChain() {
  const [symbol, setSymbol] = useState("NIFTY");
  const [expiry, setExpiry] = useState("");
  const [strikeCount, setStrikeCount] = useState(10);
  const [refreshKey, setRefreshKey] = useState(0);
  const [rows, setRows] = useState<ChainRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchChain() {
      setLoading(true);
      setError(null);

      try {
        const payload = await api.getOptionChain(symbol, expiry || undefined, strikeCount);
        if (!Array.isArray(payload)) {
          throw new Error("Options chain API returned an invalid response.");
        }
        if (!cancelled) setRows(payload as ChainRow[]);
      } catch (err) {
        if (!cancelled) {
          setRows([]);
          setError(err instanceof Error ? err.message : "Failed to load options chain.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void fetchChain();
    return () => { cancelled = true; };
  }, [symbol, expiry, strikeCount, refreshKey]);

  const formattedRows = useMemo(
    () => rows.map((row) => ({ ...row, strike_price: Number(row.strike_price) })),
    [rows],
  );

  const formatLtp = (ltp: number | null) =>
    ltp == null
      ? "—"
      : Number(ltp).toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });

  return (
    <section className="glass flex min-h-[350px] flex-col overflow-hidden rounded-2xl border border-glow-border">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-glow-border bg-card-bg/50 px-4 py-3">
        <h2 className="font-semibold text-white">Options Chain</h2>
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Underlying symbol"
            value={symbol}
            onChange={(event) => setSymbol(event.target.value)}
            className="rounded-lg border border-glow-border bg-card-bg px-2 py-1.5 text-sm text-white"
          >
            {SYMBOLS.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>

          <input
            type="date"
            aria-label="Expiry (optional; blank uses nearest expiry)"
            value={expiry}
            onChange={(event) => setExpiry(event.target.value)}
            className="rounded-lg border border-glow-border bg-card-bg px-2 py-1.5 text-sm text-white"
          />

          <select
            aria-label="Strikes on each side"
            value={strikeCount}
            onChange={(event) => setStrikeCount(Number(event.target.value))}
            className="rounded-lg border border-glow-border bg-card-bg px-2 py-1.5 text-sm text-white"
          >
            {[5, 10, 15, 20].map((count) => (
              <option key={count} value={count}>{count} strikes each side</option>
            ))}
          </select>

          <button
            type="button"
            onClick={() => setRefreshKey((key) => key + 1)}
            aria-label="Refresh options chain"
            className="rounded-lg border border-glow-border bg-card-bg p-2 text-text-secondary"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </header>

      {loading ? (
        <div aria-busy="true" aria-label="Loading options chain" className="flex flex-1 items-center justify-center gap-2 text-text-secondary">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading options chain…
        </div>
      ) : error ? (
        <div role="alert" className="flex flex-1 items-center justify-center gap-2 p-6 text-center text-neon-red">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span>Could not load options chain: {error}</span>
        </div>
      ) : rows.length === 0 ? (
        <div className="flex flex-1 items-center justify-center p-6 text-center text-text-muted">
          No option data available for this symbol and expiry
        </div>
      ) : (
        <div className="flex-1 overflow-auto p-2">
          <table className="w-full min-w-[600px] text-sm">
            <thead className="sticky top-0 bg-card-bg/90 text-text-muted">
              <tr>
                <th className="px-3 py-2 text-right">Call</th>
                <th className="px-3 py-2 text-center">Strike</th>
                <th className="px-3 py-2 text-left">Put</th>
              </tr>
            </thead>
            <tbody>
              {formattedRows.map((row) => (
                <tr
                  key={row.strike_price}
                  className={`border-t border-glow-border/40 ${row.is_atm ? "bg-neon-cyan/10" : "hover:bg-card-bg/50"}`}
                >
                  <td className="px-3 py-2 text-right font-mono text-neon-green">
                    {formatLtp(row.call_ltp)}
                    {row.call_symbol && <span className="ml-2 text-xs text-text-secondary">{row.call_symbol}</span>}
                  </td>
                  <td className="px-3 py-2 text-center font-mono font-bold text-white">
                    {row.strike_price.toLocaleString()}
                    {row.is_atm && <span className="ml-1 text-[10px] text-neon-cyan">ATM</span>}
                  </td>
                  <td className="px-3 py-2 text-left font-mono text-neon-red">
                    {formatLtp(row.put_ltp)}
                    {row.put_symbol && <span className="ml-2 text-xs text-text-secondary">{row.put_symbol}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
