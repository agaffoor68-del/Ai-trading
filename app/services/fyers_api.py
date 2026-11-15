"""
Fyers API v3 Client for REST endpoints
"""

import asyncio
import logging
from typing import Optional, Dict, List, Any
from zoneinfo import ZoneInfo
from datetime import datetime

import aiohttp

from app.core.config import settings
from app.services.fyers_token import get_fyers_token

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

FYERS_API_BASE = "https://api.fyers.in/api/v3"
FYERS_DATA_BASE = "https://api-t1.fyers.in/data"

# Common display names -> exact Fyers tickers
SYMBOL_ALIASES = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "NIFTY50": "NSE:NIFTY50-INDEX",
    "NIFTY 50": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
    "BANK NIFTY": "NSE:NIFTYBANK-INDEX",
    "NIFTY BANK": "NSE:NIFTYBANK-INDEX",
    "NIFTYBANK": "NSE:NIFTYBANK-INDEX",
    "FINNIFTY": "NSE:FINNIFTY-INDEX",
    "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
    "SENSEX": "BSE:SENSEX-INDEX",
    "BANKEX": "BSE:BANKEX-INDEX",
    "RELIANCE": "NSE:RELIANCE-EQ",
    "TCS": "NSE:TCS-EQ",
    "HDFC BANK": "NSE:HDFCBANK-EQ",
    "HDFCBANK": "NSE:HDFCBANK-EQ",
    "SBIN": "NSE:SBIN-EQ",
    "INFY": "NSE:INFY-EQ",
}


def normalize_symbol(symbol: str) -> str:
    """Map a display name (e.g. 'NIFTY 50') to a Fyers ticker. Exchange-prefixed symbols pass through."""
    s = (symbol or "").strip()
    if ":" in s:
        return s
    key = " ".join(s.upper().split())
    if key in SYMBOL_ALIASES:
        return SYMBOL_ALIASES[key]
    # Unknown bare name: assume NSE equity
    return f"NSE:{key.replace(' ', '')}-EQ" if key else s


class FyersAPIClient:
    """
    Fyers API v3 REST client for quotes, historical data, and profile.
    """
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
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
                timeout=aiohttp.ClientTimeout(total=15),
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
            async with session.get(
                FYERS_DATA_BASE + "/history", params=params, headers={"Authorization": auth_header}
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
        Returns: { "d": [ { "v": { "symbol": "NSE:NIFTY50-INDEX", "ltp": 24345.85, "ch": 124.35, "chp": 0.51 } } ] }
        """
        # Check if token is available
        auth_header = self._get_auth_header()
        if not auth_header:
            logger.error("Fyers authentication not configured")
            return {"error": "Fyers not authenticated. Please login via /api/v1/fyers/login"}
        
        session = await self._get_session()
        
        # Fyers quotes endpoint expects symbols as comma-separated string
        symbols_param = ",".join(normalize_symbol(x) for x in symbols)
        url = f"{FYERS_DATA_BASE}/quotes"
        params = {"symbols": symbols_param}
        
        try:
            async with session.get(url, params=params, headers={"Authorization": auth_header}) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Fyers quotes API error: HTTP {resp.status} - {error_text}")
                    if resp.status == 401:
                        return {"error": "Fyers token expired or invalid. Please re-login."}
                    return {}
                
                data = await resp.json()
                
                if data.get("code") != 200:
                    logger.error(f"Fyers quotes error code: {data.get('code')} - {data.get('message')}")
                    if data.get("code") == 401:
                        return {"error": "Fyers token expired or invalid. Please re-login."}
                    return {}
                
                result = {}
                for item in data.get("d", []):
                    v = item.get("v", {})
                    symbol = v.get("symbol")
                    if symbol:
                        result[symbol] = {
                            "symbol": symbol,
                            "ltp": v.get("ltp"),
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
                
                logger.info(f"Fetched quotes for {len(result)} symbols from Fyers API")
                return result
                
        except asyncio.TimeoutError:
            logger.error("Fyers quotes API timeout")
            return {}
        except Exception as e:
            logger.error(f"Fyers quotes API error: {str(e)}")
            return {}


# Global client instance
fyers_api_client = FyersAPIClient()