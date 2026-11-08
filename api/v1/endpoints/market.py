"""
Fyers Live Data & Market Endpoints Module 2

Provides FastAPI endpoints for:
- Fyers WebSocket live ticks
- Historical candles
- Symbol search from DB
"""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.database import get_db, Instrument
from ...services.fyers_websocket import (
    FyersWebSocket,
    fetch_historical_candles,
    search_symbols_db,
    IST,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/market", tags=["market-data"])


# Global WebSocket instance (will be initialized per connection or via dependency)
fws: FyersWebSocket | None = None


def get_fyers_ws() -> FyersWebSocket:
    """Dependency to get Fyers WebSocket instance."""
    global fws
    if fws is None:
        # In production, this would use a valid access token
        # For now, create with placeholder - actual token set via /login flow
        raise HTTPException(status_code=503, detail="Fyers WS not initialized")
    return fws


@router.get("/candles")
async def get_candles(
    symbol: str = Query(..., description="Fyers symbol e.g., NSE:NIFTY50"),
    timeframe: str = Query("1min", description="Candle timeframe: 1min, 5min, 15min, 60min, 1D"),
    date_from: str | None = Query(None, description="Start date YYYY-MM-DD"),
    date_to: str | None = Query(None, description="End date YYYY-MM-DD"),
    db: Session = Depends(get_db),
    ws: FyersWebSocket = Depends(get_fyers_ws),
):
    """
    Fetch historical candles for a symbol.
    
    - Tries DB first, falls back to Fyers API
    - All timestamps converted to IST (Asia/Kolkata)
    """
    try:
        # Check if symbol exists in instruments table
        inst = db.query(Instrument).filter(Instrument.symbol == symbol.split(":")[-1] if ":" in symbol else symbol).first()
        
        # Try to fetch from Fyers
        end_date = date_to or datetime.now(IST).strftime("%Y-%m-%d")
        start_date = date_from or (datetime.now(IST) - timedelta(days=30)).strftime("%Y-%m-%d")
        
        df = await asyncio.get_event_loop().run_in(
            None,
            lambda: fetch_historical_candles(
                access_token="",  # Will be set from auth
                symbol=symbol,
                timeframe=timeframe,
                date_from=start_date,
                date_to=end_date,
                session=aiohttp.ClientSession(),
            ),
        )
        
        if df is not None and not df.empty:
            # Convert to list of dicts for JSON response
            candles = df.to_dict(orient="records")
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "exchange": "NSE",
                "candles": candles,
                "count": len(candles),
                "timezone": "IST (Asia/Kolkata)",
            }
        
        # Fallback: return empty result from DB query
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "exchange": "NSE",
            "candles": [],
            "count": 0,
            "note": "No data available - symbol may not be in master or token invalid",
        }
        
    except Exception as e:
        logger.error(f"Candles endpoint error for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal error fetching candles")


@router.get("/search")
async def search_symbols(
    query: str = Query(..., min_length=1, description="Search query"),
    exchange: str | None = Query(None, description="Filter by exchange e.g., NSE_CM, NSE_FO"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    db: Session = Depends(get_db),
):
    """
    Search symbols from local PostgreSQL instruments table.
    
    Searches both symbol and name fields using case-insensitive matching.
    """
    try:
        results = await asyncio.get_event_loop().run_in(
            None,
            lambda: search_symbols_db(query=query, db_session=db, exchange=exchange),
        )
        
        return {
            "query": query,
            "exchange": exchange or "all",
            "results": results,
            "total": len(results),
        }
    except Exception as e:
        logger.error(f"Symbol search error for '{query}': {str(e)}")
        raise HTTPException(status_code=500, detail="Internal error searching symbols")


@router.post("/ws/subscribe")
async def ws_subscribe(
    symbols: list[str] = Body([...], description="List of Fyers symbols to subscribe to"),
    ws: FyersWebSocket = Depends(get_fyers_ws),
):
    """
    Subscribe to live WebSocket ticks for specified symbols.
    
    Returns subscription confirmation.
    """
    try:
        success = await ws.subscribe(symbols)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to subscribe")
        
        return {
            "status": "subscribed",
            "symbols": symbols,
            "message": f"Subscribed to {len(symbols)} symbols for live ticks",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WS subscribe error: {str(e)}")
        raise HTTPException(status_code=500, detail="WebSocket subscription error")


@router.get("/ws/status")
async def ws_status():
    """Check Fyers WebSocket connection status."""
    global fws
    if fws is None:
        return {"connected": False, "message": "Fyers WS not initialized"}
    
    return {
        "connected": fws.is_connected,
        "subscribed_symbols": fws.symbols if fws.symbols else [],
        "message": "WebSocket connection active" if fws.is_connected else "WebSocket disconnected",
    }