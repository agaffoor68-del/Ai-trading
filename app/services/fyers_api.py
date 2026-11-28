"""
Fyers API v3 Client for REST endpoints
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Optional, Dict, List, Any
from zoneinfo import ZoneInfo
from datetime import datetime

import aiohttp

from app.core.config import settings
from app.core.error_log import ErrorCategory, classify_fyers_message, log_error
from app.services.fyers_token import get_fyers_token
from app.core.symbol_map import to_fyers
from app.services.redis_ws import redis_tick_store

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")
_fallback_rate_lock = asyncio.Lock()
_fallback_next_request = 0.0

_RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local refill = tonumber(ARGV[3])
local state = redis.call('HMGET', key, 'tokens', 'updated')
local tokens = tonumber(state[1]) or capacity
local updated = tonumber(state[2]) or now
tokens = math.min(capacity, tokens + math.max(0, now - updated) * refill)
if tokens >= 1 then
  redis.call('HMSET', key, 'tokens', tokens - 1, 'updated', now)
  redis.call('EXPIRE', key, 10)
  return 0
end
local wait = (1 - tokens) / refill
redis.call('HMSET', key, 'tokens', tokens, 'updated', now)
redis.call('EXPIRE', key, 10)
return math.ceil(wait * 1000)
"""

async def _wait_for_fyers_slot() -> None:
    """Apply a shared Redis token bucket, falling back to a paced local limiter."""
    client = redis_tick_store._client if redis_tick_store.is_connected() else None
    if client is not None:
        try:
            while True:
                wait_ms = await client.eval(
                    _RATE_LIMIT_SCRIPT, 1, "fyers:api:rate-limit", time.time(), 3, 3
                )
                if wait_ms <= 0:
                    return
                await asyncio.sleep(wait_ms / 1000)
        except Exception as exc:
            logger.warning("Fyers Redis rate limiter unavailable; using local limiter: %s", exc)
    global _fallback_next_request
    async with _fallback_rate_lock:
        delay = _fallback_next_request - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        _fallback_next_request = time.monotonic() + 1 / 3

FYERS_API_BASE = "https://api-t1.fyers.in/api"
FYERS_DATA_BASE = "https://api-t1.fyers.in/data"

INDEX_MAP = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "NIFTY 50": "NSE:NIFTY50-INDEX",
    "NIFTY50": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
    "SENSEX": "BSE:SENSEX-INDEX",
}

# Resolutions accepted by the FYERS v3 ``/data/history`` endpoint.  Anything
# else (for example the UI's "1D"/"1W" labels) is translated before the call.
VALID_RESOLUTIONS = frozenset(
    {"1", "2", "3", "5", "10", "15", "20", "25", "30", "45", "60",
     "120", "240", "D", "W", "MN"}
)

# UI interval label -> FYERS resolution.
RESOLUTION_ALIASES = {
    "1": "1", "1m": "1", "2": "2", "2m": "2", "3": "3", "3m": "3",
    "5": "5", "5m": "5", "10": "10", "10m": "10", "15": "15", "15m": "15",
    "20": "20", "20m": "20", "25": "25", "25m": "25", "30": "30", "30m": "30",
    "45": "45", "45m": "45", "60": "60", "1h": "60", "60m": "60",
    "120": "120", "2h": "120", "240": "240", "4h": "240",
    "d": "D", "1d": "D", "day": "D", "1D": "D",
    "w": "W", "1w": "W", "1wk": "W", "week": "W", "1W": "W",
    "mn": "MN", "1M": "MN", "1mo": "MN", "month": "MN",
}

# How many times a retryable history failure is attempted, and the base delay.
HISTORY_MAX_ATTEMPTS = 3
HISTORY_RETRY_BACKOFF = 0.5

# Exchanges the data API serves.  Anything else cannot be a valid ticker.
KNOWN_EXCHANGES = frozenset(
    {"NSE", "NSE_FO", "NSE_CM", "BSE", "BSE_CM", "MCX", "NFO", "CDS"}
)


def normalize_resolution(resolution: Any) -> str:
    """Translate a UI interval or raw resolution into a FYERS resolution."""
    if resolution is None:
        return ""
    raw = str(resolution).strip()
    if not raw:
        return ""
    if raw in VALID_RESOLUTIONS:
        return raw
    return RESOLUTION_ALIASES.get(raw, RESOLUTION_ALIASES.get(raw.upper(), raw))


def validate_fyers_symbol(symbol: str) -> Optional[str]:
    """Return a human-readable reason when ``symbol`` cannot be a Fyers ticker.

    ``None`` means the symbol is structurally valid; it does not guarantee the
    instrument exists, which only the provider can confirm.
    """
    if not symbol or not str(symbol).strip():
        return "Symbol is empty"
    text = str(symbol).strip()
    if ":" not in text:
        return (
            f"Symbol '{text}' is not exchange-qualified. "
            "Use a Fyers ticker such as NSE:NIFTY50-INDEX or NSE:SBIN-EQ."
        )
    exchange, _, name = text.partition(":")
    exchange = exchange.strip().upper()
    name = name.strip()
    if exchange not in KNOWN_EXCHANGES:
        return f"Unknown exchange '{exchange}' in symbol '{text}'"
    if not name:
        return f"Symbol '{text}' has no instrument name"
    if any(ch.isspace() for ch in name):
        return f"Symbol '{text}' contains whitespace in the instrument name"
    return None


def normalize_symbol(symbol: str) -> str:
    """Map index aliases and legacy segment-prefixed indices to Fyers tickers."""
    if not symbol:
        return symbol

    stripped = symbol.strip()
    alias = " ".join(stripped.upper().split())
    if alias in INDEX_MAP:
        return INDEX_MAP[alias]

    if ":" in stripped:
        exchange, name = stripped.split(":", 1)
        exchange_upper = exchange.strip().upper()
        name_alias = " ".join(name.upper().split())
        # Legacy / segment-qualified index names (NSE_FO:NIFTY, BSE_CM:SENSEX)
        # must collapse to the canonical index ticker, otherwise the data API
        # answers "Invalid input".
        if name_alias in INDEX_MAP:
            canonical = INDEX_MAP[name_alias]
            if exchange_upper in {"NSE_FO", "NSE_CM", "BSE_CM"}:
                return canonical
            # A bare exchange prefix on an index name is still the index.
            if exchange_upper in KNOWN_EXCHANGES:
                return canonical
        return stripped

        # A bare name that already carries an instrument suffix ("NIFTY50-INDEX",
        # "SBIN-EQ") must keep that suffix.  Re-adding "-EQ" unconditionally
        # turned NIFTY50-INDEX into the non-existent NSE:NIFTY50-EQ, which is
        # exactly what made Fyers answer "Invalid input".
        upper = stripped.upper()
        for suffix in ("-INDEX", "-EQ"):
            if upper.endswith(suffix):
                base = upper[: -len(suffix)]
                if base:
                    return f"NSE:{base}{suffix}"

        return to_fyers(stripped)


class FyersAPIClient:
    """
    Fyers API v3 REST client for quotes, historical data, and profile.
    """
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    # Strict timeout for all Fyers REST calls so a hung API never blocks
    # the event loop or the frontend ("signal timed out" errors).
    FYERS_TIMEOUT = aiohttp.ClientTimeout(total=5.0)

    def _get_auth_header(self) -> Optional[str]:
        """Get Authorization header value with current token."""
        # Priority: 1. Persistent storage, 2. Settings (in-memory)
        token = get_fyers_token() or settings.FYERS_ACCESS_TOKEN
        if not token:
            logger.warning("FYERS_ACCESS_TOKEN not available in storage or settings")
            return None
        # Fyers expects format: "client_id:access_token"
        client_id = settings.FYERS_CLIENT_ID
        if not client_id:
            logger.error("FYERS_CLIENT_ID not configured")
            return None
        return f"{client_id}:{token}"
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=self.FYERS_TIMEOUT,
            )
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_history(
        self,
        symbol: str,
        resolution: str,
        range_from: int = None,
        range_to: int = None,
        start_ts: int = None,
        end_ts: int = None,
    ) -> Dict[str, Any]:
        """
        Fetch historical candles from Fyers API v3.

        GET https://api-t1.fyers.in/data/history

        Required query parameters (FYERS v3 data API):
            symbol       exchange-qualified ticker, e.g. ``NSE:NIFTY50-INDEX``
            resolution   1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 120, 240, D, W, MN
            date_format  ``0`` = epoch seconds, ``1`` = ``YYYY-MM-DD``
            range_from   start of the window (epoch when date_format=0)
            range_to     end of the window (epoch when date_format=0)
            cont_flag    ``1`` returns the unadjusted (continuous) series

        ``start_ts``/``end_ts`` are accepted as aliases so older call sites keep
        working.  Returns ``{"candles": [[epoch, o, h, l, c, v], ...]}`` or
        ``{"error": str, "status": int}``.
        """
        auth_header = self._get_auth_header()
        if not auth_header:
            return {"error": "Fyers not authenticated. Please login via /api/v1/fyers/login", "status": 401}

        # Backwards-compatible aliases used by older call sites.
        if range_from is None:
            range_from = start_ts
        if range_to is None:
            range_to = end_ts
        if range_from is None or range_to is None:
            return {
                "error": "get_history requires range_from/range_to (epoch seconds)",
                "status": 400,
            }

        original_symbol = symbol
        symbol = normalize_symbol(symbol)
        resolution = normalize_resolution(resolution)

        # "Invalid input" is FYERS' generic 400 for a malformed request, and the
        # two usual causes are an unqualified symbol or a resolution the data API
        # does not accept.  Both are rejected locally so the provider is never
        # called with a request we already know is invalid.
        symbol_problem = validate_fyers_symbol(symbol)
        if symbol_problem:
            log_error(
                ErrorCategory.FYERS_SYMBOL,
                f"Fyers history rejected before request: {symbol_problem}",
                endpoint="/data/history",
                status_code=400,
                context={"symbol": symbol, "input": original_symbol},
            )
            return {"error": symbol_problem, "status": 400}

        if resolution not in VALID_RESOLUTIONS:
            log_error(
                ErrorCategory.FYERS_HISTORY,
                f"Unsupported resolution '{resolution}' for {symbol}",
                endpoint="/data/history",
                status_code=400,
                context={"symbol": symbol, "resolution": resolution},
            )
            return {"error": f"Unsupported resolution '{resolution}'", "status": 400}

        session = await self._get_session()
        params = {
            "symbol": symbol,
            "resolution": resolution,
            "date_format": "0",  # epoch seconds
            "range_from": str(int(range_from)),
            "range_to": str(int(range_to)),
            "cont_flag": "1",
        }

        # FYERS answers 429 when the app rate limit is hit; only that and 5xx
        # are worth retrying.  400/401/403 are deterministic and are returned
        # immediately with the provider's own message.
        last_error: Optional[Dict[str, Any]] = None
        for attempt in range(1, HISTORY_MAX_ATTEMPTS + 1):
            try:
                await _wait_for_fyers_slot()
                async with session.get(
                    FYERS_DATA_BASE + "/history",
                    params=params,
                    headers={"Authorization": auth_header, "Content-Type": "application/json"},
                    timeout=self.FYERS_TIMEOUT,
                ) as resp:
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:
                        data = {}
                    if not isinstance(data, dict):
                        data = {}

                    if resp.status == 401 or data.get("code") in (401, -16, -15):
                        log_error(
                            ErrorCategory.FYERS_AUTH,
                            f"Fyers history auth failure for {symbol}",
                            endpoint="/data/history",
                            status_code=resp.status,
                            context={
                                "symbol": symbol,
                                "provider_code": data.get("code"),
                                "provider_message": data.get("message"),
                            },
                        )
                        return {"error": "Fyers token expired or invalid. Please re-login.", "status": 401}

                    if resp.status != 200 or data.get("s") != "ok":
                        msg = data.get("message") or f"HTTP {resp.status}"
                        log_error(
                            classify_fyers_message(msg),
                            f"Fyers history error for {symbol}: {msg}",
                            endpoint="/data/history",
                            status_code=resp.status,
                            context={
                                "symbol": symbol,
                                "resolution": resolution,
                                "range_from": params["range_from"],
                                "range_to": params["range_to"],
                                "provider_code": data.get("code"),
                                "provider_message": data.get("message"),
                            },
                        )
                        last_error = {
                            "error": msg,
                            "status": 400 if resp.status in (200, 400) else 502,
                        }
                        if resp.status in (429, 500, 502, 503, 504) and attempt < HISTORY_MAX_ATTEMPTS:
                            await asyncio.sleep(HISTORY_RETRY_BACKOFF * attempt)
                            continue
                        return last_error

                    candles = data.get("candles") or []
                    if not isinstance(candles, list):
                        logger.error(
                            "Fyers history for %s returned a non-list candles payload: %s",
                            symbol, json.dumps(data, default=str)[:500],
                        )
                        return {"error": "Fyers returned an invalid candles payload", "status": 502}
                    return {"candles": candles}
            except asyncio.TimeoutError:
                log_error(
                    ErrorCategory.FYERS_HISTORY,
                    f"Fyers history request timed out for {symbol}",
                    endpoint="/data/history",
                    status_code=504,
                    context={"symbol": symbol, "attempt": attempt},
                )
                last_error = {"error": "Fyers history request timed out", "status": 504}
            except aiohttp.ClientError as exc:
                log_error(
                    ErrorCategory.FYERS_HISTORY,
                    f"Fyers history network error for {symbol}: {exc}",
                    endpoint="/data/history",
                    status_code=502,
                    context={"symbol": symbol, "attempt": attempt},
                    exc=exc,
                )
                last_error = {"error": "Fyers history request failed", "status": 502}
            if attempt < HISTORY_MAX_ATTEMPTS:
                await asyncio.sleep(HISTORY_RETRY_BACKOFF * attempt)
        return last_error or {"error": "Fyers history request failed", "status": 502}

    async def get_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Fetch live quotes for multiple symbols from Fyers API v3.
        
        Fyers Quotes API: GET /api/v3/quotes?symbols=NSE:NIFTY50-INDEX,NSE:SBIN-EQ
        Authorization: client_id:access_token
        Max 50 symbols per call.
        Returns: { "d": [ { "v": { "symbol": "NSE:NIFTY50-INDEX", "ltp": 24345.85, "ch": 124.35, "chp": 0.51 } } ] }
        """
        # Check if token is available
        auth_header = self._get_auth_header()
        if not auth_header:
            logger.error("Fyers authentication not configured")
            return {"error": "Fyers not authenticated. Please login via /api/v1/fyers/connect"}
        
        session = await self._get_session()
        
        # Normalize all symbols and use a stable key independent of input ordering.
        fyers_symbols = [normalize_symbol(s) for s in symbols]
        cache_key = "fyers:quotes:" + ",".join(sorted(fyers_symbols))
        redis_client = redis_tick_store._client if redis_tick_store.is_connected() else None
        if redis_client is not None:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as exc:
                logger.warning("Fyers quotes cache read failed: %s", exc)
        
        # Batch in chunks of 50
        all_results = {}
        batch_size = 50
        
        for i in range(0, len(fyers_symbols), batch_size):
            batch = fyers_symbols[i:i + batch_size]
            symbols_param = ",".join(batch)
            url = f"{FYERS_DATA_BASE}/quotes"
            params = {"symbols": symbols_param}
            
            try:
                await _wait_for_fyers_slot()
                async with session.get(
                    url, 
                    params=params, 
                    headers={"Authorization": auth_header, "Content-Type": "application/json"},
                    timeout=self.FYERS_TIMEOUT
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Fyers quotes API error: HTTP {resp.status} - {error_text}")
                        if resp.status == 401:
                            return {"error": "Fyers token expired or invalid. Please re-login."}
                        # Continue with other batches
                        continue
                    
                    response = await resp.json()
                    logger.info(f"Raw Fyers Response: {response}")
                    data = response
                    
                    if data.get("code") != 200:
                        logger.error(f"Fyers quotes error code: {data.get('code')} - {data.get('message')}")
                        if data.get("code") == 401:
                            return {"error": "Fyers token expired or invalid. Please re-login."}
                        # Continue with other batches
                        continue
                    
                    for item in data.get("d", []):
                        if not isinstance(item, dict):
                            continue
                        v = item.get("v") if isinstance(item.get("v"), dict) else {}
                        symbol = v.get("symbol") or item.get("symbol")
                        # Safely get LTP: check key existence instead of truthiness to
                        # preserve legitimate zero values (e.g. a stock trading at zero).
                        if "lp" in v and v["lp"] is not None:
                            ltp = v["lp"]
                        elif "ltp" in v and v["ltp"] is not None:
                            ltp = v["ltp"]
                        elif "lp" in item and item["lp"] is not None:
                            ltp = item["lp"]
                        elif "ltp" in item and item["ltp"] is not None:
                            ltp = item["ltp"]
                        else:
                            ltp = None
                        if symbol:
                            all_results[symbol] = {
                                "symbol": symbol,
                                "ltp": ltp,
                                "change": v.get("ch"),
                                "change_percent": v.get("chp"),
                                "open": v.get("open"),
                                "high": v.get("high"),
                                "low": v.get("low"),
                                "close": v.get("close"),
                                "volume": v.get("volume"),
                                # Options fields: passed through only when the
                                # broker actually sent them.  A missing value
                                # stays None so the options layer can mark it
                                # unavailable instead of guessing.
                                "oi": v.get("oi"),
                                "oi_change": v.get("oiflag"),
                                "prev_oi": v.get("prev_oi"),
                                "bid": v.get("bid"),
                                "ask": v.get("ask"),
                                "bid_size": v.get("bid_size"),
                                "ask_size": v.get("ask_size"),
                                "spread": v.get("spread"),
                                "source": "fyers_api_v3",
                                "updated_at": datetime.now(IST).isoformat(),
                            }
                    
                    logger.info(f"Fetched quotes for {len(batch)} symbols from Fyers API")
                    
            except asyncio.TimeoutError:
                logger.error("Fyers quotes API timeout")
                continue
            except aiohttp.ClientError as e:
                logger.error(f"Fyers quotes network error: {e}")
                continue
            except Exception as e:
                logger.error(f"Fyers quotes API error: {str(e)}")
                continue
        
        if not all_results and fyers_symbols:
            return {"error": "Failed to fetch quotes from Fyers"}
        
        if redis_client is not None and all_results:
            try:
                await redis_client.setex(cache_key, 5, json.dumps(all_results))
            except Exception as exc:
                logger.warning("Fyers quotes cache write failed: %s", exc)
        return all_results

    async def get_profile(self, access_token: str) -> dict:
        """
        Fetch user profile from Fyers API to validate token.
        GET https://api.fyers.in/api/v3/profile
        """
        auth_header = f"{settings.FYERS_CLIENT_ID}:{access_token}"
        if not settings.FYERS_CLIENT_ID:
            logger.warning("get_profile called without FYERS_CLIENT_ID configured")
            return {}

        redis_client = redis_tick_store._client if redis_tick_store.is_connected() else None
        token_fingerprint = hashlib.sha256(access_token.encode()).hexdigest()
        cache_key = f"fyers:profile:{settings.FYERS_CLIENT_ID}:{token_fingerprint}"
        if redis_client is not None:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as exc:
                logger.warning("Fyers profile cache read failed: %s", exc)
        
        session = await self._get_session()
        url = f"{settings.FYERS_API_BASE}/v3/profile"
        
        try:
            await _wait_for_fyers_slot()
            async with session.get(
                url, 
                headers={"Authorization": auth_header, "Content-Type": "application/json"},
                timeout=self.FYERS_TIMEOUT
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Fyers profile API returned {resp.status}")
                    return {}
                data = await resp.json()
                
                if data.get("code") == 200 and data.get("data"):
                    profile = data["data"]
                    if redis_client is not None:
                        try:
                            await redis_client.setex(cache_key, 300, json.dumps(profile))
                        except Exception as exc:
                            logger.warning("Fyers profile cache write failed: %s", exc)
                    return profile
                return {}
        except Exception as e:
            logger.error(f"Fyers profile API error: {str(e)}")
            return {}


# Global client instance
fyers_api_client = FyersAPIClient()
