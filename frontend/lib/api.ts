import type { SWRConfiguration } from "swr";
import { fetchWithTimeout, parseApiError } from "@/lib/api-client";

// All API calls go through the Next.js same-origin proxy at /api/v1.
// The proxy (frontend/app/api/v1/...) forwards the httpOnly access_token
// cookie as an Authorization: Bearer header to the backend, so browser
// requests stay same-origin (no CORS) and always authenticated.
const API_BASE_URL = "/api/v1";

// Error types from backend
export interface ApiError {
  code: string;
  message: string;
}

export interface BrokerStatus {
  fyers: {
    connected: boolean;
    valid: boolean;
    message: string;
    token_expires_at: string | null;
    profile: {
      name: string;
      email: string;
      client_id: string;
      pan: string;
    } | null;
  };
  kotak: {
    configured: boolean;
    connected: boolean;
    message: string;
  };
  market: {
    is_open: boolean;
    is_trading_day: boolean;
    next_open: string | null;
    next_close: string | null;
    time_to_close_minutes: number;
    timezone: string;
  };
}

export interface FyersConnectResponse {
  authorization_url: string;
  state?: string;
}

export interface QuoteData {
  symbol: string;
  ltp: number | null;
  change: number | null;
  change_percent: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  source: string;
  updated_at: string | null;
  error?: string;
}

export interface QuotesResponse {
  quotes: Record<string, QuoteData>;
  total: number;
}

export interface CandleData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface OptionChainOption {
  symbol: string | null;
  ltp: number | null;
  oi: number | null;
  oi_change: number | null;
  oi_change_pct: number | null;
  volume: number | null;
  bid: number | null;
  ask: number | null;
}

export interface OptionChainStrike {
  strike: number;
  is_atm: boolean;
  call_itm: boolean;
  put_itm: boolean;
  call: OptionChainOption | null;
  put: OptionChainOption | null;
}

export interface OptionChainResponse {
  symbol: string;
  expiry: string;
  spot_price: number;
  atm_strike: number;
  strike_interval: number;
  option_chain: OptionChainStrike[];
  expiries: string[];
  timestamp: string;
  debug?: {
    all_quotes: Record<string, QuoteData>;
    strike_to_symbols: Record<number, { ce: string | null; pe: string | null }>;
  };
}

export interface AISignal {
  symbol: string;
  signal: "BUY" | "SELL" | "HOLD";
  confidence: number;
  rsi: number;
  ema_trend: "BULLISH" | "BEARISH" | "NEUTRAL";
  price: number;
  timestamp: string;
}

export interface AISignalsResponse {
  signals: AISignal[];
  timestamp: string;
}

export interface OrderRequest {
  symbol: string;
  quantity: number;
  order_type: "MARKET" | "LIMIT";
  trade_type: "BUY" | "SELL";
  option_type: "CE" | "PE";
  strike: number;
  expiry: string;
  price?: number;
  stop_loss?: number;
  target?: number;
  mode: "PAPER" | "LIVE";
}

export interface OrderResponse {
  order_id: string;
  status: "SUCCESS" | "FAILED" | "PENDING";
  message: string;
  timestamp: string;
}

export interface Position {
  symbol: string;
  quantity: number;
  avg_price: number;
  ltp: number;
  pnl: number;
  pnl_percent: number;
  side: "LONG" | "SHORT";
  product_type: string;
}

export interface PositionsResponse {
  positions: Position[];
}

export interface AdminUser {
  id: number;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  subscription: {
    plan_type: string;
    start_date: string | null;
    end_date: string | null;
    is_active: boolean;
  } | null;
}

export interface AdminUsersResponse {
  users: AdminUser[];
  total: number;
}

export interface MarketStatusResponse {
  is_open: boolean;
  is_trading_day: boolean;
  next_open: string | null;
  next_close: string | null;
  time_to_close_minutes: number;
  timezone: string;
}

export interface ExpiriesResponse {
  expiries: string[];
}

export interface InstrumentInfoResponse {
  symbol: string;
  lot_size: number | null;
  tick_size: number | null;
  expiry_dates: string[];
}

async function fetcher<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetchWithTimeout(url, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = parseApiError(await response.json().catch(() => null), response.status);
    throw error;
  }

  return response.json();
}

export const api = {
  // Broker status (auth/session routes stay same-origin via the Next.js proxy;
  // backend data endpoints go straight to API_BASE_URL)
  getFyersStatus: () =>
    fetcher<BrokerStatus["fyers"]>(`${API_BASE_URL}/fyers/status`),

  getFullStatus: () =>
    fetcher<BrokerStatus>(`${API_BASE_URL}/fyers/status`),

  // Fyers auth
  connectFyers: (clientId: string, secretKey: string) =>
    fetcher<FyersConnectResponse>(`${API_BASE_URL}/fyers/connect`, {
      method: "POST",
      body: JSON.stringify({ client_id: clientId, client_secret: secretKey }),
    }),

  // Market data
  getMarketStatus: () =>
    fetcher<MarketStatusResponse>(`${API_BASE_URL}/market/status`),

  searchSymbols: (query: string) =>
    fetcher<any>(`${API_BASE_URL}/market/search?query=${encodeURIComponent(query)}`),

  getMarketQuotes: (symbols: string[]) =>
    fetcher<QuotesResponse>(`${API_BASE_URL}/market/quotes`, {
      method: "POST",
      body: JSON.stringify({ symbols }),
    }),

  getCandles: (symbol: string, interval: string, days: number) =>
    fetcher<CandleData[]>(`${API_BASE_URL}/market/candles?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&days=${days}`),

  getOptionChain: (symbol: string, expiry: string, strikes?: number, raw?: boolean) =>
    fetcher<OptionChainResponse>(`${API_BASE_URL}/market/option-chain?symbol=${encodeURIComponent(symbol)}&expiry=${encodeURIComponent(expiry)}${strikes ? `&strikes=${strikes}` : ""}${raw ? `&raw=true` : ""}`),

  getExpiries: (symbol: string) =>
    fetcher<ExpiriesResponse>(`${API_BASE_URL}/market/expiries?symbol=${encodeURIComponent(symbol)}`),

  getInstrumentInfo: (symbol: string) =>
    fetcher<InstrumentInfoResponse>(`${API_BASE_URL}/market/instrument-info?symbol=${encodeURIComponent(symbol)}`),

  // AI signals
  getAISignals: (symbols: string[]) =>
    fetcher<AISignalsResponse>(`${API_BASE_URL}/market/ai/signals?symbols=${symbols.join(",")}`),

  // Execution (via backend)
  placeOrder: (orderData: OrderRequest) =>
    fetcher<OrderResponse>(`${API_BASE_URL}/execution/order`, {
      method: "POST",
      body: JSON.stringify(orderData),
    }),

  getPositions: () =>
    fetcher<PositionsResponse>(`${API_BASE_URL}/execution/positions`),

  // Admin
  getAdminUsers: () =>
    fetcher<AdminUsersResponse>(`${API_BASE_URL}/admin/users`),

  grantAccess: (data: { email: string; plan: string; days: number }) =>
    fetcher<any>(`${API_BASE_URL}/admin/subscribe`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  revokeAccess: (userId: number) =>
    fetcher<any>(`${API_BASE_URL}/admin/revoke/${userId}`, {
      method: "DELETE",
    }),
};

export const swrConfig: SWRConfiguration = {
  revalidateOnFocus: true,
  revalidateOnReconnect: true,
  refreshInterval: 15000,
  dedupingInterval: 2000,
  onError: (error) => {
    console.error("SWR Error:", error.message);
  },
};

export function formatFyersSymbol(symbol: string): string {
  // If already a Fyers ticker (contains colon), return as-is
  if (symbol.includes(":")) {
    return symbol;
  }
  
  // Backend will handle the mapping, so just return the user-friendly symbol
  return symbol;
}

export function formatFyersOptionSymbol(
  symbol: string,
  expiry: string,
  strike: number,
  optionType: "CE" | "PE"
): string {
  // Backend handles this, return user-friendly format for display
  return `${symbol} ${expiry} ${strike} ${optionType}`;
}

// Check if error is a 401 FYERS_NOT_CONNECTED
export function isFyersNotConnected(error: unknown): boolean {
  if (error instanceof Error && "code" in error) {
    return (error as any).code === "FYERS_NOT_CONNECTED";
  }
  return false;
}

// Check if error is a 502 FYERS_ERROR
export function isFyersError(error: unknown): boolean {
  if (error instanceof Error && "code" in error) {
    return (error as any).code === "FYERS_ERROR";
  }
  if (error instanceof Error && "status" in error) {
    return (error as any).status === 502;
  }
  return false;
}

// Check if error is a 504 FYERS_UNREACHABLE
export function isFyersUnreachable(error: unknown): boolean {
  if (error instanceof Error && "code" in error) {
    return (error as any).code === "FYERS_UNREACHABLE";
  }
  if (error instanceof Error && "status" in error) {
    return (error as any).status === 504;
  }
  return false;
}

// Check if error is a user auth 401 (not Fyers-related)
export function isAuthError(error: unknown): boolean {
  if (error instanceof Error && "code" in error) {
    const code = (error as any).code;
    return code === "AUTH_REQUIRED" || code === "TOKEN_EXPIRED" || code === "TOKEN_INVALID";
  }
  if (error instanceof Error && "status" in error) {
    return (error as any).status === 401 && !isFyersNotConnected(error);
  }
  return false;
}
