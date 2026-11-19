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
from app.core.symbol_map import to_fyers

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

FYERS_API_BASE = "https://api-t1.fyers.in/api"
FYERS_DATA_BASE = "https://api-t1.fyers.in/data"


def normalize_symbol(symbol: str) -> str:
    """Map a display name (e.g. 'NIFTY 50') to a Fyers ticker. Exchange-prefixed symbols pass through."""
    return to_fyers(symbol)


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

        Fyers commonly returns {"s":"ok","d":[{"n":"NSE:...","v":{"lp":123.4}}]}.
        Normalize both that shape and the older code/symbol/ltp shape into
        {symbol: {"symbol": symbol, "ltp": price, ...}} for callers.
        """
        auth_header = self._get_auth_header()
        if not auth_header:
            logger.error("Fyers authentication not configured")
            return {"error": "Fyers not authenticated. Please login via /api/v1/fyers/connect"}

        session = await self._get_session()
        fyers_symbols = [normalize_symbol(s) for s in symbols]
        all_results: Dict[str, Any] = {}
        batch_size = 50

        for i in range(0, len(fyers_symbols), batch_size):
            batch = fyers_symbols[i:i + batch_size]
            url = f"{FYERS_DATA_BASE}/quotes"
            params = {"symbols": ",".join(batch)}

            try:
                async with session.get(
                    url,
                    params=params,
                    headers={"Authorization": auth_header, "Content-Type": "application/json"},
                    timeout=self.FYERS_TIMEOUT,
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error("Fyers quotes API error: HTTP %s - %s", resp.status, error_text)
                        if resp.status == 401:
                            return {"error": "Fyers token expired or invalid. Please re-login."}
                        continue

                    try:
                        response = await resp.json(content_type=None)
                    except Exception:
                        response = {}
                    logger.info("Raw Fyers Quote Response: %s", response)

                    # Fyers v3 may return s="ok" instead of code=200.
                    if not isinstance(response, dict) or (
                        response.get("code") != 200 and str(response.get("s", "")).lower() != "ok"
                    ):
                        logger.error(
                            "Fyers quotes error: code=%s status=%s message=%s",
                            response.get("code") if isinstance(response, dict) else None,
                            response.get("s") if isinstance(response, dict) else None,
                            response.get("message") if isinstance(response, dict) else "invalid response",
                        )
                        if isinstance(response, dict) and response.get("code") == 401:
                            return {"error": "Fyers token expired or invalid. Please re-login."}
                        continue

                    for item in response.get("d", []):
                        if not isinstance(item, dict):
                            continue
                        values = item.get("v") or {}
                        if not isinstance(values, dict):
                            continue
                        symbol = values.get("symbol") or item.get("n")
                        if not symbol and len(batch) == 1:
                            symbol = batch[0]
                        if not symbol:
                            continue

                        # Fyers v3 uses lp (last price); retain aliases for older responses.
                        ltp = values.get("lp", values.get("ltp"))
                        if ltp is None:
                            ltp = item.get("lp", item.get("ltp"))
                        all_results[symbol] = {
                            "symbol": symbol,
                            "ltp": ltp,
                            "change": values.get("ch", values.get("change")),
                            "change_percent": values.get("chp", values.get("change_percent")),
                            "open": values.get("open"),
                            "high": values.get("high"),
                            "low": values.get("low"),
                            "close": values.get("close"),
                            "volume": values.get("volume", values.get("vol")),
                            "source": "fyers_api_v3",
                            "updated_at": datetime.now(IST).isoformat(),
                        }

                    logger.info("Fetched quotes for %d symbols from Fyers API", len(batch))

            except asyncio.TimeoutError:
                logger.error("Fyers quotes API timeout")
                continue
            except aiohttp.ClientError as e:
                logger.error("Fyers quotes network error: %s", e)
                continue
            except Exception as e:
                logger.error("Fyers quotes API error: %s", str(e))
                continue

        if not all_results and fyers_symbols:
            return {"error": "Failed to fetch quotes from Fyers"}
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
        
        session = await self._get_session()
        url = f"{settings.FYERS_API_BASE}/v3/profile"
        
        try:
            async with session.get(
                url,
                headers={"Authorization": auth_header, "Content-Type": "application/json"},
                timeout=self.FYERS_TIMEOUT
            ) as resp:
                if resp.status != 200:
                    logger.warning("Fyers profile API returned %s", resp.status)
                    return {}
                data = await resp.json()
                if data.get("code") == 200 and data.get("data"):
                    return data["data"]
                return {}
        except Exception as e:
            logger.error("Fyers profile API error: %s", str(e))
            return {}


# Global client instance
fyers_api_client = FyersAPIClient()
