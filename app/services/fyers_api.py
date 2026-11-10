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

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

FYERS_API_BASE = "https://api.fyers.in/api/v3"


class FyersAPIClient:
    """
    Fyers API v3 REST client for quotes, historical data, and profile.
    """
    
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers={
                    "Authorization": f"Bearer {self.access_token or settings.FYERS_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                }
            )
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Fetch live quotes for multiple symbols from Fyers API v3.
        
        Fyers Quotes API: GET /api/v3/quotes?symbols=NSE:NIFTY50-INDEX,NSE:SBIN-EQ
        Returns: { "d": [ { "v": { "symbol": "NSE:NIFTY50-INDEX", "ltp": 24345.85, "ch": 124.35, "chp": 0.51 } } ] }
        """
        session = await self._get_session()
        
        # Fyers quotes endpoint expects symbols as comma-separated string
        symbols_param = ",".join(symbols)
        url = f"{FYERS_API_BASE}/quotes"
        params = {"symbols": symbols_param}
        
        try:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    logger.error(f"Fyers quotes API error: HTTP {resp.status}")
                    return {}
                
                data = await resp.json()
                
                if data.get("code") != 200:
                    logger.error(f"Fyers quotes error code: {data.get('code')} - {data.get('message')}")
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


# Global client instance (uses FYERS_ACCESS_TOKEN from settings)
fyers_api_client = FyersAPIClient()