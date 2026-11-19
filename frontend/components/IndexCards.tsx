"use client";

import useSWR from "swr";
import { fetchWithTimeout } from "@/lib/api-client";

const INDEX_SYMBOLS = [
  { symbol: "NIFTY 50", ticker: "NSE:NIFTY50-INDEX" },
  { symbol: "BANKNIFTY", ticker: "NSE:NIFTYBANK-INDEX" },
  { symbol: "SENSEX", ticker: "BSE:SENSEX-INDEX" },
] as const;

type Quote = {
  symbol?: string;
  ltp?: number | string | null;
  change?: number | string | null;
  change_percent?: number | string | null;
  updated_at?: string;
};

type QuotesPayload = {
  quotes?: Record<string, Quote> | Quote[];
  data?: Quote[];
};

async function fetchIndexQuotes(): Promise<Record<string, Quote>> {
  const response = await fetchWithTimeout("/api/v1/market/quotes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbols: INDEX_SYMBOLS.map(({ ticker }) => ticker) }),
    credentials: "same-origin",
  });
  if (!response.ok) throw new Error(`Market quotes request failed (HTTP ${response.status})`);

  const payload = (await response.json()) as QuotesPayload;
  const rows = Array.isArray(payload.data)
    ? payload.data
    : Array.isArray(payload.quotes)
      ? payload.quotes
      : null;
  if (rows) return Object.fromEntries(rows.filter((quote) => quote?.symbol).map((quote) => [quote.symbol!, quote]));
  return payload.quotes && typeof payload.quotes === "object" ? payload.quotes as Record<string, Quote> : {};
}

export function IndexCards() {
  const { data: quotes = {}, error } = useSWR("/api/v1/market/quotes:index-cards", fetchIndexQuotes, {
    refreshInterval: 3000,
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    dedupingInterval: 1000,
    shouldRetryOnError: true,
  });

  return (
    <section aria-label="Live index prices" className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {INDEX_SYMBOLS.map(({ symbol, ticker }) => {
        const quote = quotes[ticker] ?? Object.values(quotes).find((item) => item.symbol === ticker);
        const price = Number(quote?.ltp);
        const changePercent = Number(quote?.change_percent ?? quote?.["changePercent"]);
        const hasPrice = Number.isFinite(price) && price > 0;
        return (
          <article key={ticker} className="glass rounded-2xl border border-glow-border p-4" aria-live="polite">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-text-secondary">{symbol}</h2>
              <span className={`h-2 w-2 rounded-full ${hasPrice ? "animate-pulse bg-neon-green" : "bg-text-muted"}`} aria-label={hasPrice ? "Live quote" : "Waiting for quote"} />
            </div>
            <p className="mt-2 font-mono text-2xl font-bold tabular-nums text-white">
              {hasPrice ? `₹${price.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : error ? "Unavailable" : "Loading…"}
            </p>
            {hasPrice && Number.isFinite(changePercent) && (
              <p className={`mt-1 text-sm font-mono ${changePercent >= 0 ? "text-neon-green" : "text-neon-red"}`}>
                {changePercent >= 0 ? "+" : ""}{changePercent.toFixed(2)}%
              </p>
            )}
          </article>
        );
      })}
    </section>
  );
}
