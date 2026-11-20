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
        name_alias = " ".join(name.upper().split())
        if exchange.upper() in {"NSE_FO", "NSE_CM", "BSE_CM"} and name_alias in INDEX_MAP:
            return INDEX_MAP[name_alias]
        return stripped

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
        self, symbol: str, resolution: str, range_from: int, range_to: int
    ) -> Dict[str, Any]:
        """
        Fetch historical candles from Fyers API v3.

        GET https://api-t1.fyers.in/data/history
        Returns {"candles": [[epoch, o, h, l, c, v], ...]} or {"error": str, "status": int}.
        """
        auth_header = self._get_auth_header()
        if not auth_header:
            return {"error": "Fyers not authenticated. Please login via /api/v1/fyers/login", "status": 401}

        symbol = normalize_symbol(symbol)
        session = await self._get_session()
        params = {
            "symbol": symbol,
            "resolution": resolution,
            "date_format": "0",  # epoch seconds
            "range_from": str(range_from),
            "range_to": str(range_to),
            "cont_flag": "1",
        }
        try:
            await _wait_for_fyers_slot()
            async with session.get(
                FYERS_DATA_BASE + "/history", params=params, headers={"Authorization": auth_header}, timeout=self.FYERS_TIMEOUT
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = {}
                if resp.status == 401 or data.get("code") in (401, -16, -15):
                    return {"error": "Fyers token expired or invalid. Please re-login.", "status": 401}
                if resp.status != 200 or data.get("s") != "ok":
                    msg = data.get("message") or f"HTTP {resp.status}"
                    logger.error(f"Fyers history error for {symbol}: {msg}")
                    return {"error": msg, "status": 400 if resp.status in (200, 400) else 502}
                return {"candles": data.get("candles", [])}
        except asyncio.TimeoutError:
            return {"error": "Fyers history request timed out", "status": 504}
        except aiohttp.ClientError as e:
            logger.error(f"Fyers history network error: {e}")
            return {"error": "Fyers history request failed", "status": 502}

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
                        ltp = v.get("lp") or v.get("ltp") or item.get("lp") or item.get("ltp")
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
