import type { SWRConfiguration } from "swr";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "https://ai-trading-9qoa.onrender.com";

export interface BrokerStatus {
  fyers: {
    connected: boolean;
    tokenExpiresAt: string | null;
  };
  kotak: {
    connected: boolean;
    tokenExpiresAt: string | null;
  };
}

export interface FyersLoginResponse {
  authorization_url: string;
  state: string;
  client_id: string;
  message: string;
}

export interface QuoteRequest {
  symbols: string[];
}

export interface QuoteData {
  ltp: number | null;
  change: number | null;
  change_percent: number | null;
  source: string;
  updated_at: string | null;
}

export interface QuotesResponse {
  quotes: Record<string, QuoteData>;
}

export interface OptionChainRequest {
  symbol: string;
  expiry: string;
}

export interface OptionStrike {
  strike: number;
  isATM: boolean;
  ceLtp: number;
  ceChange: number;
  ceOI: number;
  ceOIChange: number;
  peLtp: number;
  peChange: number;
  peOI: number;
  peOIChange: number;
}

export interface OptionChainData {
  symbol: string;
  expiry: string;
  spot: number;
  atmStrike: number;
  strikes: OptionStrike[];
}

export interface AISignal {
  symbol: string;
  name: string;
  action: "BUY CE" | "BUY PE" | "WAIT";
  confidence: number;
  reasoning: string;
  entry: number;
  target: number;
  stopLoss: number;
  expiry: string;
  timestamp: string;
}

export interface AISignalsResponse {
  signals: AISignal[];
  timestamp: string;
}

export interface OrderRequest {
  symbol: string;
  quantity: number;
  orderType: "MARKET" | "LIMIT";
  tradeType: "BUY" | "SELL";
  optionType: "CE" | "PE";
  strike: number;
  expiry: string;
  price?: number;
  stopLoss?: number;
  target?: number;
  mode: "PAPER" | "LIVE";
}

export interface OrderResponse {
  orderId: string;
  status: "SUCCESS" | "FAILED" | "PENDING";
  message: string;
  timestamp: string;
}

export interface Position {
  symbol: string;
  quantity: number;
  avgPrice: number;
  ltp: number;
  pnl: number;
  pnlPercent: number;
  side: "LONG" | "SHORT";
  productType: string;
}

export interface PositionsResponse {
  positions: Position[];
}

export interface AdminUser {
  id: string;
  email: string;
  name: string;
  plan: string;
  createdAt: string;
  isActive: boolean;
}

export interface AdminUsersResponse {
  users: AdminUser[];
}

async function fetcher<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: "Unknown error" }));
    throw new Error(error.message || `HTTP ${response.status}`);
  }

  return response.json();
}

export const api = {
  getBrokerStatus: () =>
    fetcher<BrokerStatus>(`${API_BASE_URL}/api/v1/auth/broker-status`),

  getFyersLoginUrl: () =>
    fetcher<FyersLoginResponse>(`${API_BASE_URL}/api/v1/fyers/login`),

  searchSymbols: (query: string) =>
    fetcher<any>(`${API_BASE_URL}/api/v1/market/search?query=${encodeURIComponent(query)}`),

  getMarketQuotes: (symbols: string[]) =>
    fetcher<QuotesResponse>(`${API_BASE_URL}/api/v1/market/quotes`, {
      method: "POST",
      body: JSON.stringify({ symbols }),
    }),

  getOptionChain: (symbol: string, expiry: string) =>
    fetcher<OptionChainData>(`${API_BASE_URL}/api/v1/market/option-chain?symbol=${encodeURIComponent(symbol)}&expiry=${encodeURIComponent(expiry)}`),

  getAISignals: () =>
    fetcher<AISignalsResponse>(`${API_BASE_URL}/api/v1/ai/live-analysis`),

  placeOrder: (orderData: OrderRequest) =>
    fetcher<OrderResponse>(`${API_BASE_URL}/api/v1/execution/order`, {
      method: "POST",
      body: JSON.stringify(orderData),
    }),

  getPositions: () =>
    fetcher<PositionsResponse>(`${API_BASE_URL}/api/v1/execution/positions`),

  getAdminUsers: (token: string) =>
    fetcher<AdminUsersResponse>(`${API_BASE_URL}/api/v1/admin/users`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }),
};

export const swrConfig: SWRConfiguration = {
  revalidateOnFocus: true,
  revalidateOnReconnect: true,
  refreshInterval: 5000,
  dedupingInterval: 2000,
  onError: (error) => {
    console.error("SWR Error:", error.message);
  },
};

export function formatFyersSymbol(symbol: string, exchange = "NSE"): string {
  return `${exchange}:${symbol}`;
}

export function formatFyersOptionSymbol(
  symbol: string,
  expiry: string,
  strike: number,
  optionType: "CE" | "PE",
  exchange = "NSE"
): string {
  return `${exchange}:${symbol}${expiry}${strike}${optionType}`;
}