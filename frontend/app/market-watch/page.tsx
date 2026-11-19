"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { motion } from "framer-motion";
import { AlertCircle, Loader2, Search, Wifi } from "lucide-react";
import { Header } from "@/components/Header";
import { Sidebar } from "@/components/Sidebar";
import { useMarketQuotes } from "@/lib/hooks";
import { fetchWithTimeout } from "@/lib/api-client";

interface SearchResult {
  symbol: string;
  exchange?: string;
  name?: string;
  fyers_token?: string;
  instrument_type?: string;
  lot_size?: number | null;
}

interface SearchResponse {
  results?: SearchResult[];
  data?: SearchResult[] | { results?: SearchResult[] };
}

function normalizeSearchResults(payload: unknown): SearchResult[] {
  if (Array.isArray(payload)) return payload as SearchResult[];
  if (!payload || typeof payload !== "object") return [];
  const response = payload as SearchResponse;
  if (Array.isArray(response.results)) return response.results;
  if (Array.isArray(response.data)) return response.data;
  if (response.data && typeof response.data === "object" && Array.isArray(response.data.results)) {
    return response.data.results;
  }
  return [];
}

async function searchSymbols(query: string): Promise<SearchResult[]> {
  const url = `/api/v1/market/search?query=${encodeURIComponent(query)}`;
  const response = await fetchWithTimeout(url, { credentials: "same-origin" });
  if (!response.ok) throw new Error(`Symbol search failed (HTTP ${response.status})`);
  return normalizeSearchResults(await response.json());
}

export default function MarketWatchPage() {
  const [query, setQuery] = useState("NIFTY 50");
  const normalizedQuery = query.trim();
  const { data: results = [], error, isLoading, mutate } = useSWR<SearchResult[]>(
    normalizedQuery ? ["/api/v1/market/search", normalizedQuery] : null,
    ([, searchQuery]) => searchSymbols(searchQuery),
    { revalidateOnFocus: false, dedupingInterval: 1000 },
  );
  const symbols = useMemo(() => results.slice(0, 10).map((result) => result.symbol).filter(Boolean), [results]);
  const { quotes, isLoading: quotesLoading, isFyersNotConnected } = useMarketQuotes(symbols);

  const items = results.map((item) => {
    const quote = quotes[item.symbol] ?? (item.fyers_token ? quotes[item.fyers_token] : undefined);
    const price = quote?.ltp;
    return {
      ...item,
      price: typeof price === "number" ? price : null,
      change: typeof quote?.change === "number" ? quote.change : 0,
      changePercent: typeof quote?.change_percent === "number" ? quote.change_percent : typeof quote?.changePercent === "number" ? quote.changePercent : 0,
      priceSource: quote?.updated_at && Date.now() - new Date(quote.updated_at).getTime() > 60000 ? "STALE" : quote?.ltp != null ? "LIVE" : "—",
    };
  });

  return (
    <div className="min-h-screen bg-true-black text-white">
      <Sidebar />
      <div className="w-full lg:ml-64 min-h-screen flex flex-col">
        <Header />
        <main className="flex-1 space-y-6 p-4 pt-20 md:p-8 lg:p-10 lg:pt-24">
          <div>
            <h1 className="text-2xl font-bold md:text-3xl">Market Watch</h1>
            <p className="mt-1 text-text-secondary">Search symbols and track live market data.</p>
          </div>
          <form onSubmit={(event) => { event.preventDefault(); void mutate(); }} className="glass flex max-w-2xl gap-3 rounded-2xl border border-glow-border p-4">
            <label className="flex flex-1 items-center gap-3">
              <Search className="h-5 w-5 shrink-0 text-text-muted" />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search symbols (e.g. NIFTY 50)" className="w-full bg-transparent text-white outline-none" />
            </label>
            <button type="submit" disabled={isLoading} className="rounded-lg bg-neon-cyan px-4 py-2 font-semibold text-true-black disabled:opacity-50">Search</button>
          </form>
          {isFyersNotConnected && <p className="flex items-center gap-2 text-sm text-neon-orange"><Wifi className="h-4 w-4" />Fyers is not connected; live quotes are unavailable.</p>}
          {error && <p role="alert" className="text-sm text-neon-red">{error.message}</p>}
          <div className="glass overflow-hidden rounded-2xl border border-glow-border">
            <div className="grid grid-cols-4 border-b border-glow-border bg-card-bg/50 px-4 py-3 text-xs uppercase text-text-muted"><span className="col-span-2">Symbol</span><span className="text-right">LTP</span><span className="text-right">Status</span></div>
            {isLoading ? <div className="flex items-center justify-center gap-2 p-10 text-text-secondary"><Loader2 className="h-5 w-5 animate-spin" />Searching symbols…</div> : items.length === 0 ? <div className="p-10 text-center text-text-muted"><AlertCircle className="mx-auto mb-2 h-7 w-7" />No results found for “{normalizedQuery}”.</div> : items.map((item, index) => (
              <motion.div key={`${item.exchange ?? ""}:${item.symbol}:${index}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="grid grid-cols-4 items-center border-b border-glow-border/50 px-4 py-4 last:border-0">
                <div className="col-span-2"><p className="font-medium text-white">{item.symbol}</p><p className="text-xs text-text-muted">{item.name ?? item.exchange ?? ""}</p></div>
                <p className="text-right font-mono">{item.price === null ? (quotesLoading ? "Loading…" : "—") : `₹${item.price.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}</p>
                <p className={`text-right text-xs ${item.priceSource === "LIVE" ? "text-neon-green" : item.priceSource === "STALE" ? "text-neon-orange" : "text-text-muted"}`}>{item.priceSource}</p>
              </motion.div>
            ))}
          </div>
        </main>
      </div>
    </div>
  );
}
