"""
Phase 1: Market Data Endpoints

Non-Negotiable Rule: Fyers API v3 is the ONLY data source.
Endpoints for symbol search, quotes, and historical data via Fyers.
"""

import logging
from fastapi import APIRouter, Query

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["market-data"])


@router.get("/search")
async def search_symbols(
    query: str = Query(..., min_length=1, description="Search query (symbol or name)"),
    exchange: str = Query(None, description="Filter by exchange e.g., NSE_CM, NSE_FO"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
):
    """
    Search symbols from the local PostgreSQL symbol master
    (parsed from Fyers Symbol Master CSVs).
    """
    try:
        from app.core.database import SessionLocal, Instrument

        db = SessionLocal()
        try:
            from sqlalchemy import or_

            filter_condition = or_(
                Instrument.symbol.ilike(f"%{query}%"),
                Instrument.name.ilike(f"%{query}%"),
            )
            if exchange:
                filter_condition = filter_condition & (Instrument.exchange == exchange)

            results = (
                db.query(Instrument)
                .filter(filter_condition)
                .filter(Instrument.is_active == 1)
                .limit(limit)
                .all()
            )

            return {
                "query": query,
                "exchange": exchange or "all",
                "results": [
                    {
                        "symbol": inst.symbol,
                        "exchange": inst.exchange,
                        "name": inst.name,
                        "fyers_token": inst.fyers_token,
                        "instrument_type": inst.instrument_type,
                        "lot_size": inst.lot_size,
                    }
                    for inst in results
                ],
                "total": len(results),
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Symbol search error: {str(e)}")
        return {"query": query, "results": [], "total": 0, "error": str(e)}


@router.get("/quote/{symbol}")
async def get_quote(symbol: str):
    """
    Get live quote for a symbol.
    Fyers API v3 is the ONLY data source.
    """
    try:
        # Check Redis cache first for latest tick
        from app.services.redis_ws import redis_tick_store

        cached = await redis_tick_store.get_tick(symbol)
        if cached:
            return {
                "symbol": symbol,
                "ltp": cached.get("ltp"),
                "source": "redis_cache",
                "updated_at": cached.get("updated_at"),
            }

        # Fallback: return not found (must use Fyers WebSocket for live data)
        return {
            "symbol": symbol,
            "ltp": None,
            "source": "fyers_api_v3",
            "message": "Subscribe via Fyers WebSocket for live quotes",
        }
    except Exception as e:
        logger.error(f"Quote error for {symbol}: {str(e)}")
        return {"symbol": symbol, "error": str(e)}
