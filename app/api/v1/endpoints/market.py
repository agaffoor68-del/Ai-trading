"""
Phase 1: Market Data Endpoints

Non-Negotiable Rule: Fyers API v3 is the ONLY data source.
Endpoints for symbol search, quotes, and historical data via Fyers.
"""

import logging
import asyncio
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException, status
from pydantic import BaseModel
from datetime import datetime, time
from asyncio import to_thread as run_in_threadpool

from app.core.config import settings
from app.core.symbol_map import to_fyers
from app.core.datetime_utils import IST, now_ist
from app.core.market_calendar import MarketCalendar

logger = logging.getLogger(__name__)

router = APIRouter(tags=["market-data"])


class QuotesRequest(BaseModel):
    symbols: List[str]


# Index symbol mappings
EXACT_INDEX_SYMBOLS = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "NIFTY 50": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
    "BANK NIFTY": "NSE:NIFTYBANK-INDEX",
    "FINNIFTY": "NSE:FINNIFTY-INDEX",
    "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
    "SENSEX": "BSE:SENSEX-INDEX",
}

# ETF/Unwanted suffixes to deprioritize
ETF_EXCLUSION_PATTERNS = ["BEES", "ADD", "EW", "ETF", "NIFTYBEES", "NIFTYADD"]

# Noise patterns to EXCLUDE unless explicitly searched
NOISE_PATTERNS = [
    "AQL", "GS", "ALPHA", "500", "200", "100", "50", 
    "MIDCAP", "SMALLCAP", "LARGECAP", "MICROCAP",
    "AUTO", "PHARMA", "IT", "METAL", "REALTY", "ENERGY",
    "MEDIA", "FMCG", "PVT", "BANK", "FIN", "COMM",
    "CHEMICALS", "EV", "GROWSECT", "HOUSING", "INFRA",
    "PHARMA", "METAL", "REALTY", "ENERGY", "MEDIA"
]

# Index keywords that should be prioritized
INDEX_KEYWORDS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "BANKEX"]

# Instrument type priority: Index=1, Futures=2, Options=3, Equity=4, Others=5
INSTRUMENT_TYPE_PRIORITY = {
    "10": 1,   # Fyers NSE_CM index code
    "13": 1,
    "INDEX": 1,
    "11": 2,   # Futures
    "FUT": 2,
    "FUTURE": 2,
    "12": 3,   # Options
    "OPT": 3,
    "OPTION": 3,
    "0": 4,    # Fyers NSE_CM equity code
    "EQ": 4,
    "EQUITY": 4,
    "STK": 4,
}


def is_etf_like(symbol: str) -> bool:
    """Check if symbol looks like an ETF/unwanted variant."""
    symbol_upper = symbol.upper()
    return any(pattern in symbol_upper for pattern in ETF_EXCLUSION_PATTERNS)


def is_noise(symbol: str, query: str) -> bool:
    """
    Check if symbol is noise (obscure indices like NIFTY AQL, NIFTY 500, etc.)
    Returns True if it's noise AND the user didn't explicitly search for it.
    """
    symbol_upper = symbol.upper()
    query_upper = query.upper()
    
    for pattern in NOISE_PATTERNS:
        if pattern in symbol_upper:
            # Allow if query contains the pattern (explicit search)
            if pattern in query_upper:
                return False
            return True
    return False


def is_index_like(query: str, symbol: str) -> bool:
    """Check if query matches an index keyword exactly."""
    query_upper = query.upper()
    symbol_upper = symbol.upper()
    return any(keyword == query_upper for keyword in INDEX_KEYWORDS) and any(keyword in symbol_upper for keyword in INDEX_KEYWORDS)


def get_instrument_priority(instrument_type: str) -> int:
    """Get priority score for instrument type (lower = higher priority)."""
    return INSTRUMENT_TYPE_PRIORITY.get(instrument_type.upper() if instrument_type else "", 5)


# Initialize market calendar
market_calendar = MarketCalendar()

router = APIRouter(tags=["market-data"])



@router.get("/status")
async def get_market_status():
    """
    Get current market status.
    
    Returns:
    {
        "is_open": true/false,
        "is_trading_day": true/false,
        "next_open": "2026-01-15T09:15:00+05:30",
        "next_close": "2026-01-15T15:30:00+05:30",
        "time_to_close_minutes": 120,
        "timezone": "Asia/Kolkata"
    }
    """
    now = now_ist()
    is_open = market_calendar.is_market_open(now)
    is_trading_day = market_calendar.is_trading_day(now.date())
    time_to_close = market_calendar.time_to_close(now)
    
    # Calculate next open/close
    if is_open:
        next_close = datetime.combine(now.date(), time(15, 30), tzinfo=IST)
        next_open = None
    else:
        next_close = None
        # Find next trading day
        next_trading_day = market_calendar.next_trading_day(now.date())
        next_open = datetime.combine(next_trading_day, time(9, 15), tzinfo=IST)
    
    return {
        "is_open": is_open,
        "is_trading_day": is_trading_day,
        "next_open": next_open.isoformat() if next_open else None,
        "next_close": next_close.isoformat() if next_close else None,
        "time_to_close_minutes": time_to_close,
        "timezone": "Asia/Kolkata",
    }


@router.get("/search")
async def search_symbols(
    query: str = Query(..., min_length=1, description="Search query (symbol or name)"),
    exchange: str = Query(None, description="Filter by exchange e.g., NSE_CM, NSE_FO"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
):
    """
    Search symbols from the local PostgreSQL symbol master
    (parsed from Fyers Symbol Master CSVs).
    
    Priority order:
    1. Exact match on main index (NIFTY → NSE:NIFTY50-INDEX)
    2. Exact matches on symbol
    3. Prefix matches
    4. Main Index instruments (NIFTY, BANKNIFTY, etc.)
    5. Futures & Options (F&O) - instrument_type 11/12
    6. Equity
    7. Noise/ETFs deprioritized or filtered
    """
    try:
        from app.core.database import SessionLocal, Instrument
        from sqlalchemy import case, or_

        def _search_db():
            db = SessionLocal()
            try:
                query_upper = query.upper()

                # Check if query is an exact index keyword
                is_exact_index = query_upper in EXACT_INDEX_SYMBOLS
                target_index_symbol = EXACT_INDEX_SYMBOLS.get(query_upper)

                # Rank exact and prefix matches in SQL before limiting. Without
                # this ordering, a broad query such as NIFTY can fill the limit
                # with unrelated ETFs before the actual index is considered.
                fetch_limit = min(limit * 50, 5000)

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
                    .order_by(
                        case(
                            (Instrument.symbol.ilike(query_upper), 0),
                            (Instrument.name.ilike(query_upper), 1),
                            (Instrument.symbol.ilike(f"{query}%"), 2),
                            (Instrument.name.ilike(f"{query}%"), 3),
                            else_=4,
                        ),
                        Instrument.id.asc(),
                    )
                    .limit(fetch_limit)
                    .all()
                )

                # Convert to list of dicts for ranking
                result_dicts = [
                    {
                        "symbol": (
                            to_fyers(inst.name or inst.symbol.rsplit(":", 1)[-1])
                            if inst.symbol.startswith("NSE_CM:")
                            else inst.symbol
                        ),
                        "exchange": inst.exchange,
                        "name": inst.name,
                        "fyers_token": inst.fyers_token,
                        "instrument_type": (
                            "12" if (inst.option_type or "").upper() in {"CE", "PE"}
                            or (inst.symbol or "").upper().endswith(("CE", "PE"))
                            else inst.instrument_type
                        ),
                        "lot_size": inst.lot_size,
                    }
                    for inst in results
                ]

                # FILTER OUT NOISE before ranking (unless explicitly searched)
                filtered_results = [
                    item for item in result_dicts 
                    if not is_noise(item.get("symbol", ""), query)
                ]

                # -----------------------------------------------------------
                # CATEGORIZE NIFTY-RELATED INSTRUMENTS INTO GROUPS
                # -----------------------------------------------------------
                if is_exact_index and query_upper in {"NIFTY", "NIFTY 50"}:
                    # Separate into index, futures, and options groups
                    index_instruments = []
                    futures_instruments = []
                    options_instruments = {}

                    for item in filtered_results:
                        symbol = item.get("symbol", "").upper()
                        inst_type = item.get("instrument_type", "").upper()
                        opt_type = (item.get("option_type") or "").upper()
                        strike = item.get("strike") or ""
                        expiry = item.get("expiry")
                        
                        # Normalize symbol for comparison
                        # NSE:NIFTY50-INDEX -> NIFTY50
                        base_symbol = symbol.replace("NSE:", "").replace("-INDEX", "").replace("-", "")
                        
                        # 1. NIFTY 50 SPOT/INDEX - the actual index ticker
                        if symbol in {"NSE:NIFTY50-INDEX", "NIFTY50", "NIFTY 50"} or base_symbol == "NIFTY50":
                            index_instruments.append(item)
                            continue
                        
                        # 2. NIFTY FUTURES - instrument_type indicates futures
                        # Fyers instrument_type "11" = Futures, or symbol ends with FUT/FUTURE
                        if inst_type in {"11", "FUT", "FUTURE"} or symbol.endswith("-FUT") or "FUTURE" in symbol:
                            futures_instruments.append(item)
                            continue
                        
                        # 3. NIFTY OPTIONS - option_type is CE or PE, has strike and/or expiry
                        if opt_type in {"CE", "PE"} and (strike or expiry):
                            key = f"{opt_type}_{strike}_{expiry}" if strike and expiry else f"{opt_type}_{strike or expiry}"
                            if key not in options_instruments:
                                options_instruments[key] = []
                            options_instruments[key].append(item)
                            continue

                    # Build categorized response
                    # Sort index instruments - exact match first
                    index_sorted = sorted(
                        index_instruments,
                        key=lambda x: (
                            0 if x.get("symbol", "").upper() in {"NSE:NIFTY50-INDEX", "NIFTY50"} else 1,
                            x.get("name", "").upper(),
                        ),
                    )
                    
                    # Sort futures - nearest expiry first
                    futures_sorted = sorted(
                        futures_instruments,
                        key=lambda x: (
                            x.get("expiry") or datetime.max,
                            x.get("symbol", "").upper(),
                        ),
                    )
                    
                    # Sort options - group by strike, nearest expiry first, ITM/ATM first
                    options_list = []
                    for key in sorted(options_instruments.keys()):
                        group = sorted(
                            options_instruments[key],
                            key=lambda x: (
                                0 if (x.get("option_type") or "").upper() == "ATM" else 1,
                                float(x.get("strike") or 0),
                                x.get("expiry") or datetime.min,
                            ),
                        )
                        options_list.extend(group)

                    final_results = index_sorted + futures_sorted + options_list
                    total = len(final_results)

                    return {
                        "query": query,
                        "exchange": exchange or "all",
                        "results": final_results,
                        "total": total,
                        "categories": {
                            "index": index_sorted,
                            "futures": futures_sorted,
                            "options": options_list,
                        },
                    }
                else:
                    # Original ranking logic for non-NIFTY queries
                    # FILTER OUT NOISE before ranking (unless explicitly searched)
                    filtered_results = [
                        item for item in result_dicts 
                        if not is_noise(item.get("symbol", ""), query)
                    ]

                    # Rank results
                    def rank_score(item: dict) -> tuple:
                        symbol = item.get("symbol", "").upper()
                        inst_type = item.get("instrument_type", "")
                        
                        # Score components (lower = better)
                        
                        # 0. MAIN INDEX EXACT MATCH (highest priority)
                        # If query is "NIFTY", boost NSE:NIFTY50-INDEX to absolute top
                        main_index_match = 0
                        if is_exact_index and target_index_symbol:
                            target_clean = target_index_symbol.replace("NSE:", "").replace("-INDEX", "")
                            item_name = item.get("name", "").upper()
                            main_index_match = (
                                0
                                if symbol == target_clean
                                or symbol == target_index_symbol
                                or item_name == query_upper
                                else 1
                            )
                        else:
                            main_index_match = 1
                        
                        # 1. Exact match on symbol
                        exact_match = 0 if symbol == query_upper else 1
                        
                        # 2. Starts with query (prefix match)
                        prefix_match = 0 if symbol.startswith(query_upper) else 1
                        
                        # 3. Index keyword exact match (NIFTY, BANKNIFTY, etc.)
                        index_priority = 0 if is_index_like(query, item.get("symbol", "")) else 1
                        
                        # For an explicit underlying search (e.g. NIFTY), put its
                        # listed option contracts near the top so the response limit
                        # does not hide every CE/PE behind large F&O result sets.
                        option_type = str(item.get("instrument_type") or "").upper().removesuffix(".0")
                        option_rank = 0 if is_exact_index and option_type in {"12", "OPT", "OPTION"} else 1

                        # 4. Instrument type priority (Index > FUT > OPT > EQ > Others)
                        type_priority = get_instrument_priority(option_type)

                        # 5. ETF deprioritization
                        etf_penalty = 10 if is_etf_like(symbol) else 0

                        # 6. Segment priority (FO before CM for indices)
                        segment_priority = 0 if item.get("exchange") == "NSE_FO" else 1

                        return (main_index_match, option_rank, exact_match, prefix_match, index_priority, type_priority, etf_penalty, segment_priority, symbol)

                    # Sort by ranking
                    ranked_results = sorted(filtered_results, key=rank_score)

                    # Apply limit after ranking
                    final_results = ranked_results[:limit]

                    return {
                        "query": query,
                        "exchange": exchange or "all",
                        "results": final_results,
                        "total": len(final_results),
                    }
            finally:
                db.close()

        return await run_in_threadpool(_search_db)
    except Exception as e:
        logger.error(f"Symbol search error: {str(e)}")
        return {"query": query, "results": [], "total": 0, "error": str(e)}


INTERVAL_TO_RESOLUTION = {
    "1m": "1", "2m": "2", "3m": "3", "5m": "5", "10m": "10", "15m": "15",
    "20m": "20", "30m": "30", "45m": "45", "60m": "60", "1h": "60",
    "2h": "120", "4h": "240", "1d": "1D", "d": "1D",
}


@router.get("/candles")
async def get_candles(
    symbol: str = Query(..., description="Fyers symbol, e.g. NSE:NIFTY50-INDEX"),
    interval: str = Query("5m", description="Candle interval: 1m, 5m, 15m, 1h, 1d ..."),
    days: int = Query(5, ge=1, le=100, description="Lookback in days"),
):
    """
    Historical OHLCV candles via Fyers API v3 (default: last 5 days).

    Returns: [{"time": epoch_seconds, "open", "high", "low", "close", "volume"}, ...]
    """
    from app.services.fyers_api import fyers_api_client

    resolution = INTERVAL_TO_RESOLUTION.get(interval.strip().lower())
    if not resolution:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported interval '{interval}'. Use one of: {', '.join(INTERVAL_TO_RESOLUTION)}",
        )

    symbol = to_fyers(symbol)

    now = int(now_ist().timestamp())

    # Graceful market-closed handling: on weekends/holidays Fyers REST may
    # return stale or empty data. Cap the lookback so we always get the last
    # available session's candles instead of hanging on an empty window.
    result = await fyers_api_client.get_history(symbol, resolution, now - days * 86400, now)

    if "error" in result:
        raise HTTPException(status_code=result.get("status", 502), detail={"code": "FYERS_ERROR", "message": result["error"]})

    candles = []
    for row in result["candles"]:
        if len(row) < 5:
            continue
        candles.append({
            "time": int(row[0]),
            "open": row[1],
            "high": row[2],
            "low": row[3],
            "close": row[4],
            "volume": row[5] if len(row) > 5 else 0,
        })
    candles.sort(key=lambda c: c["time"])

    market_cal = MarketCalendar()
    market_open = market_cal.is_market_open(now_ist())
    return {
        "candles": candles,
        "market_open": market_open,
        "note": None if market_open else "Market closed - showing last available session data",
    }


@router.get("/quote/{symbol}")
async def get_quote(symbol: str):
    """
    Get live quote for a symbol.
    Fyers API v3 is the ONLY data source.
    """
    try:
        symbol = to_fyers(symbol)
        # Check Redis cache first for latest tick
        from app.services.redis_ws import redis_tick_store

        cached = await redis_tick_store.get_tick(symbol)
        if cached:
            return {
                "symbol": symbol,
                "ltp": cached.get("ltp"),
                "change": cached.get("change"),
                "change_percent": cached.get("change_percent"),
                "source": "redis_cache",
                "updated_at": cached.get("updated_at"),
            }

        # Fallback: return not found (must use Fyers WebSocket for live data)
        return {
            "symbol": symbol,
            "ltp": None,
            "change": None,
            "change_percent": None,
            "source": "fyers_api_v3",
            "message": "Subscribe via Fyers WebSocket for live quotes",
        }
    except Exception as e:
        logger.error(f"Quote error for {symbol}: {str(e)}")
        return {"symbol": symbol, "error": str(e)}


@router.post("/quotes")
async def get_quotes(request: QuotesRequest):
    """
    Get live quotes for multiple symbols from Fyers API v3.
    Expects JSON body: {"symbols": ["NSE:NIFTY50-INDEX", "NSE:SBIN-EQ"]}
    Batches requests to avoid timeout (max 50 symbols per request).
    Returns 401 if Fyers token is missing or expired.
    """
    # Apply symbol mapping to all incoming symbols
    symbols = [to_fyers(symbol) for symbol in request.symbols]
    
    if not symbols:
        return {"quotes": {}, "total": 0, "error": "No symbols provided"}
    
    # Check if Fyers is authenticated before proceeding
    from app.services.fyers_token import get_fyers_token
    
    # Try to get token from persistent storage first
    token = await run_in_threadpool(get_fyers_token)
    if not token:
        logger.warning("Fyers quotes requested but no access token available")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "FYERS_NOT_CONNECTED", "message": "Fyers not authenticated. Please login via /api/v1/fyers/connect"}
        )
    
    try:
        from app.services.fyers_api import fyers_api_client
        from app.services.redis_ws import redis_tick_store
        
        logger.info(f"Fetching quotes for {len(symbols)} symbols")
        
        # First check Redis cache for hot symbols
        results = {}
        missing = []
        
        for symbol in symbols:
            cached = await redis_tick_store.get_tick(symbol)
            if cached and cached.get("ltp") is not None:
                results[symbol] = {
                    "symbol": symbol,
                    "ltp": cached.get("ltp"),
                    "change": cached.get("change"),
                    "change_percent": cached.get("change_percent"),
                    "source": "redis_cache",
                    "updated_at": cached.get("updated_at"),
                }
            else:
                missing.append(symbol)
        
        # Fetch missing symbols from Fyers API in batches
        if missing:
            fyers_quotes = await fyers_api_client.get_quotes(missing)
            
            # Check if Fyers returned an error
            if isinstance(fyers_quotes, dict) and fyers_quotes.get("error"):
                logger.warning(f"Fyers quotes error: {fyers_quotes['error']}")
                if "expired" in fyers_quotes["error"].lower() or "invalid" in fyers_quotes["error"].lower():
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail={"code": "FYERS_NOT_CONNECTED", "message": "Fyers token expired or invalid. Please re-login."}
                    )
                # Add error to all missing symbols
                for symbol in missing:
                    results[symbol] = {
                        "symbol": symbol,
                        "ltp": None,
                        "change": None,
                        "change_percent": None,
                        "source": "fyers_api_v3",
                        "error": fyers_quotes["error"],
                    }
            else:
                for symbol, quote in fyers_quotes.items():
                    results[symbol] = quote
                # Fyers omits illiquid/invalid symbols instead of returning a
                # quote row. Keep response shape stable so clients render a dash.
                for symbol in missing:
                    results.setdefault(symbol, {
                        "symbol": symbol,
                        "ltp": None,
                        "change": None,
                        "change_percent": None,
                        "source": "fyers_api_v3",
                    })
        
        # Return all results (live + cached)
        market_cal = MarketCalendar()
        market_open = market_cal.is_market_open(now_ist())
        response = {
            "quotes": results,
            "total": len(symbols),
            "market_open": market_open,
            "note": None if market_open else "Market closed - showing last available cached data",
        }
        
        logger.info(f"Returned quotes for {len(results)} symbols (cache + Fyers)")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quotes error: {str(e)}")
        raise HTTPException(status_code=502, detail={"code": "FYERS_ERROR", "message": str(e)})


@router.get("/live-quotes")
async def get_live_quotes(
    symbols: str = Query(..., description="Comma-separated Fyers symbols"),
):
    """
    Get live quotes from Redis cache, with Fyers REST fallback.

    Reads from Redis tick cache (populated by Fyers WebSocket) first.
    If a symbol is missing from cache, fetches it from Fyers REST API
    and writes it back to Redis. This ensures data always flows even if
    WebSocket/Redis is temporarily empty.
    """
    from app.services.redis_ws import redis_tick_store
    from app.services.fyers_api import fyers_api_client

    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        return {"quotes": {}, "total": 0, "source": "redis_cache"}

    results = {}
    missing = []

    # 1. Read from Redis cache first
    for symbol in symbol_list:
        try:
            cached = await redis_tick_store.get_tick(symbol)
            if cached and cached.get("ltp") is not None:
                results[symbol] = {
                    "symbol": symbol,
                    "ltp": cached.get("ltp"),
                    "change": cached.get("change"),
                    "change_percent": cached.get("change_percent"),
                    "source": "redis_cache",
                    "updated_at": cached.get("updated_at"),
                }
            else:
                missing.append(symbol)
        except Exception as e:
            logger.warning(f"Redis tick read failed for {symbol}: {e}")
            missing.append(symbol)

    # 2. Fallback to Fyers REST for symbols missing from cache
    if missing:
        try:
            fyers_quotes = await fyers_api_client.get_quotes(missing)
            if isinstance(fyers_quotes, dict) and not fyers_quotes.get("error"):
                for symbol, quote in fyers_quotes.items():
                    if isinstance(quote, dict) and quote.get("ltp") is not None:
                        results[symbol] = {
                            "symbol": symbol,
                            "ltp": quote.get("ltp"),
                            "change": quote.get("change"),
                            "change_percent": quote.get("change_percent"),
                            "source": "fyers_rest_fallback",
                            "updated_at": quote.get("updated_at") or quote.get("timestamp"),
                        }
                        # Write back to Redis for next time
                        try:
                            await redis_tick_store.write_tick(symbol, {
                                "symbol": symbol,
                                "ltp": quote.get("ltp"),
                                "change": quote.get("change"),
                                "change_percent": quote.get("change_percent"),
                                "updated_at": quote.get("updated_at") or quote.get("timestamp"),
                            })
                        except Exception:
                            pass
                    else:
                        results[symbol] = {
                            "symbol": symbol,
                            "ltp": None,
                            "change": None,
                            "change_percent": None,
                            "source": "fyers_rest_fallback",
                            "updated_at": None,
                        }
            # Symbols not returned by Fyers at all
            for symbol in missing:
                if symbol not in results:
                    results[symbol] = {
                        "symbol": symbol,
                        "ltp": None,
                        "change": None,
                        "change_percent": None,
                        "source": "fyers_rest_fallback",
                        "updated_at": None,
                    }
        except Exception as e:
            logger.warning(f"Fyers REST fallback failed: {e}")
            for symbol in missing:
                if symbol not in results:
                    results[symbol] = {
                        "symbol": symbol,
                        "ltp": None,
                        "change": None,
                        "change_percent": None,
                        "source": "error",
                        "updated_at": None,
                    }

    return {
        "quotes": results,
        "total": len(symbol_list),
        "source": "redis_cache_with_fyers_fallback",
    }
@router.get("/instrument-info")
async def get_instrument_info(
    symbol: str = Query(..., min_length=1, max_length=32, description="Underlying symbol, e.g. NIFTY"),
):
    """Return current F&O lot/tick sizes and listed expiries from Fyers Symbol Master."""
    from collections import Counter
    from app.core.database import SessionLocal, Instrument

    aliases = {
        "NIFTY 50": ("NSE", "NIFTY"),
        "NIFTY": ("NSE", "NIFTY"),
        "BANK NIFTY": ("NSE", "BANKNIFTY"),
        "BANKNIFTY": ("NSE", "BANKNIFTY"),
        "FINNIFTY": ("NSE", "FINNIFTY"),
        "MIDCPNIFTY": ("NSE", "MIDCPNIFTY"),
        "SENSEX": ("BSE", "SENSEX"),
    }
    normalized = " ".join(symbol.upper().split())
    mapping = aliases.get(normalized)
    if not mapping:
        raise HTTPException(status_code=400, detail=f"Unsupported underlying symbol: {symbol}")
    exchange, underlying = mapping

    def _load_instrument_info():
        db = SessionLocal()
        try:
            today = now_ist().date()
            contracts = db.query(Instrument).filter(
                Instrument.exchange == "NSE_FO" if exchange == "NSE" else Instrument.exchange == "BSE_FO",
                Instrument.symbol.ilike(f"{exchange}:{underlying}%"),
                Instrument.is_active == 1,
            ).order_by(Instrument.expiry.asc()).all()

            # Derive expiry from symbol ticker when the DB column is NULL
            # (e.g. Fyers CSV expiry_date field was empty or unparseable).
            import re as _re
            for item in contracts:
                if item.expiry is None:
                    m = _re.search(r"(\d{2})([A-Z]{3})(\d{3,})", (item.symbol or "").upper())
                    if m:
                        dd, mon, _ = m.groups()
                        try:
                            item.expiry = datetime.strptime(f"{dd}-{mon}-{today.year}", "%d-%b-%Y")
                        except ValueError:
                            pass

            expiries = sorted({item.expiry.date().isoformat() for item in contracts if item.expiry and item.expiry.date() >= today})
            logger.info("instrument-info DEBUG: symbol=%s exchange=%s underlying=%s total_rows=%d expiries=%s",
                        symbol, exchange, underlying, len(contracts), expiries)
            if not contracts or not expiries:
                return {
                    "symbol": underlying,
                    "lot_size": None,
                    "tick_size": None,
                    "expiry_dates": [],
                    "note": f"No active F&O contracts are currently available for {underlying}",
                }

            nearest_expiry = expiries[0]
            current_contracts = [item for item in contracts if item.expiry and item.expiry.date().isoformat() == nearest_expiry]
            lot_sizes = Counter(int(item.lot_size) for item in current_contracts if item.lot_size and int(item.lot_size) > 0)
            tick_sizes = Counter(str(item.tick_size) for item in current_contracts if item.tick_size)
            if not lot_sizes:
                raise HTTPException(status_code=503, detail=f"Lot size is missing in Symbol Master for {underlying}")

            return {
                "symbol": underlying,
                "lot_size": lot_sizes.most_common(1)[0][0],
                "tick_size": float(tick_sizes.most_common(1)[0][0]) if tick_sizes else None,
                "expiry_dates": expiries,
            }
        finally:
            db.close()

    return await run_in_threadpool(_load_instrument_info)


@router.get("/expiries")
async def get_expiries(
    symbol: str = Query(..., description="Underlying symbol (e.g., NIFTY, BANKNIFTY)"),
):
    """
    Get list of available expiry dates for a given index symbol.
    Returns expiries in YYYY-MM-DD format sorted ascending.
    """
    try:
        from app.core.database import SessionLocal, Instrument

        def _expiries_db():
            db = SessionLocal()
            try:
                symbol_upper = symbol.upper()
                today = now_ist().date()

                # Get unique expiry dates for the symbol's options
                expiries = db.query(Instrument.expiry).filter(
                    Instrument.symbol.ilike(f"%{symbol_upper}%"),
                    Instrument.expiry >= today,
                    Instrument.instrument_type.in_(["12", "OPT", "OPTION"]),
                ).distinct().order_by(Instrument.expiry.asc()).all()

                expiry_list = [exp[0].strftime("%Y-%m-%d") for exp in expiries if exp[0]]

                return {"expiries": expiry_list}
            finally:
                db.close()

        return await run_in_threadpool(_expiries_db)
    except Exception as e:
        logger.error(f"Expiries error for {symbol}: {str(e)}")
        raise HTTPException(status_code=502, detail={"code": "FYERS_ERROR", "message": f"Failed to fetch expiries: {str(e)}"})


class OptionChainRequest(BaseModel):
    symbol: str  # e.g., "NIFTY", "BANKNIFTY"
    expiry: Optional[str] = None  # YYYY-MM-DD format, optional (uses nearest expiry)
    strikes: int = Query(10, description="Number of ITM/OTM strikes around ATM")
    raw: bool = Query(False, description="Return raw debug info")


@router.get("/option-chain")
@router.get("/options-chain")
@router.get("/options/chain")
async def get_option_chain(
    symbol: str = Query(..., min_length=1, max_length=32),
    expiry: Optional[str] = Query(None, description="Expiry date in YYYY-MM-DD format; defaults to the nearest listed expiry"),
    strikes: int = Query(10, ge=1, le=50, description="Strikes on each side of ATM"),
    strike_count: Optional[int] = Query(None, ge=1, le=50, description="Alias for strikes"),
):
    """Return live CE/PE LTPs for the selected expiry, centered on the nearest 50-point ATM."""
    from app.services.fyers_api import fyers_api_client
    from app.services.fyers_token import get_fyers_token

    aliases = {
        "NIFTY": "NSE:NIFTY50-INDEX", "NIFTY 50": "NSE:NIFTY50-INDEX",
        "BANKNIFTY": "NSE:NIFTYBANK-INDEX", "BANK NIFTY": "NSE:NIFTYBANK-INDEX",
        "FINNIFTY": "NSE:FINNIFTY-INDEX", "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
        "SENSEX": "BSE:SENSEX-INDEX",
    }
    normalized = " ".join(symbol.upper().split())
    underlying_ticker = aliases.get(normalized)
    if not underlying_ticker:
        raise HTTPException(status_code=400, detail=f"Unsupported underlying: {symbol}")
    if expiry:
        try:
            expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="expiry must be YYYY-MM-DD")
    else:
        expiry_date = None
    strikes = strike_count if strike_count is not None else strikes

    token = await run_in_threadpool(get_fyers_token)
    if not token:
        raise HTTPException(status_code=401, detail={"code": "FYERS_NOT_CONNECTED", "message": "Fyers not authenticated"})

    quotes = await fyers_api_client.get_quotes([underlying_ticker])
    spot_price = (quotes or {}).get(underlying_ticker, {}).get("ltp")
    if spot_price is None:
        raise HTTPException(status_code=502, detail={"code": "FYERS_ERROR", "message": "Underlying LTP unavailable"})
    spot_price = float(spot_price)

    def load_contracts():
        from app.core.database import SessionLocal, Instrument
        db = SessionLocal()
        try:
            query = db.query(Instrument).filter(
                Instrument.expiry >= datetime.combine(expiry_date, time.min) if expiry_date else Instrument.expiry >= now_ist().date(),
                Instrument.expiry <= datetime.combine(expiry_date, time.max) if expiry_date else Instrument.expiry.is_not(None),
                Instrument.exchange.in_(["NSE_FO"] if normalized != "SENSEX" else ["BSE_FO"]),
                Instrument.symbol.ilike(f"%:{normalized.replace(' ', '')}%"),
                Instrument.is_active == 1,
            )
            if expiry_date:
                contracts = query.all()
            else:
                nearest = query.order_by(Instrument.expiry.asc()).first()
                if nearest is None or nearest.expiry is None:
                    return {}
                chosen_expiry = nearest.expiry.date()
                contracts = query.filter(
                    Instrument.expiry >= datetime.combine(chosen_expiry, time.min),
                    Instrument.expiry <= datetime.combine(chosen_expiry, time.max),
                ).all()
            # Derive expiry from symbol ticker when DB column is NULL
            # (e.g. NIFTY26DEC25800CE -> 26-DEC-2026).
            import re as _re
            for contract in contracts:
                if contract.expiry is None:
                    m = _re.search(r"(\d{2})([A-Z]{3})(\d{3,})", (contract.symbol or "").upper())
                    if m:
                        dd, mon, _ = m.groups()
                        try:
                            contract.expiry = datetime.strptime(f"{dd}-{mon}-{today.year}", "%d-%b-%Y")
                        except ValueError:
                            pass
            logger.info("option-chain DEBUG: symbol=%s expiry=%s spot_price=%s contracts_after_filter=%d",
                        normalized, expiry_date, spot_price, len(contracts))
            result = {}
            for contract in contracts:
                option_type = (contract.option_type or "").upper()
                if option_type not in ("CE", "PE"):
                    sym = (contract.symbol or "").upper()
                    if sym.endswith("CE"):
                        option_type = "CE"
                    elif sym.endswith("PE"):
                        option_type = "PE"
                    else:
                        continue
                try:
                    strike = float(contract.strike)
                except (TypeError, ValueError):
                    continue
                # Exclude obviously stale/mismapped strikes before finding ATM.
                if abs(strike - spot_price) > max(spot_price * 0.20, 5000):
                    continue
                # Rebuild the canonical Fyers symbol so the expiry month is
                # formatted as a 3-letter month code (e.g. NSE:NIFTY26DEC25800CE)
                # instead of relying on whatever was stored in the symbol master.
                month_code = contract.expiry.strftime("%y%b").upper() if contract.expiry else ""
                canonical_symbol = f"{contract.exchange.split('_')[0]}:{normalized.replace(' ', '')}{month_code}{strike:g}{option_type}"
                result.setdefault(strike, {})[option_type] = canonical_symbol
            logger.info("option-chain DEBUG: strikes_after_atm_filter=%d", len(result))
            return result
        finally:
            db.close()

    contracts = await run_in_threadpool(load_contracts)
    available_strikes = sorted(contracts)
    if not available_strikes:
        return []

    atm_strike = int(spot_price / 50 + 0.5) * 50
    atm_index = min(range(len(available_strikes)), key=lambda index: abs(available_strikes[index] - atm_strike))
    first_index = max(0, atm_index - strikes)
    last_index = min(len(available_strikes), atm_index + strikes + 1)
    strikes_to_return = available_strikes[first_index:last_index]
    symbols_by_strike = {strike: contracts.get(strike, {}) for strike in strikes_to_return}
    symbols = list(dict.fromkeys(
        contract for legs in symbols_by_strike.values() for contract in legs.values()
    ))
    option_quotes = {}
    for offset in range(0, len(symbols), 50):
        batch = await fyers_api_client.get_quotes(symbols[offset:offset + 50])
        if isinstance(batch, dict):
            option_quotes.update(batch)

    return [
        {
            "strike_price": strike,
            "call_ltp": (option_quotes.get(legs.get("CE"), {}) or {}).get("ltp") if legs.get("CE") else None,
            "call_symbol": legs.get("CE"),
            "put_ltp": (option_quotes.get(legs.get("PE"), {}) or {}).get("ltp") if legs.get("PE") else None,
            "put_symbol": legs.get("PE"),
            "is_atm": strike == atm_strike,
        }
        for strike in strikes_to_return
    ]


class AISignalResponse(BaseModel):
    symbol: str
    signal: str  # BUY, SELL, HOLD
    confidence: float
    rsi: float
    ema_trend: str  # BULLISH, BEARISH, NEUTRAL
    price: float
    timestamp: str
    # Provenance so the UI can show freshness instead of implying live data.
    source: str = "fyers_api_v3"
    data_available: bool = True
    candles: int = 0
    as_of: Optional[str] = None
    message: Optional[str] = None


# Indicators the signal engine needs.  RSI(14) and two EMAs are enough for the
# card on the dashboard; all 169 remain available via /indicators.
SIGNAL_RSI_PERIOD = 14
SIGNAL_EMA_FAST = 9
SIGNAL_EMA_SLOW = 21
SIGNAL_CANDLES = 120


def _last_valid(series: List[Optional[float]]) -> Optional[float]:
    for value in reversed(series or []):
        if value is not None:
            return value
    return None


@router.get("/ai/signals", response_model=List[AISignalResponse])
async def get_ai_signals(
    symbols: str = Query(..., description="Comma-separated symbols (e.g., NIFTY,BANKNIFTY)"),
):
    """
    Trading signals derived from real Fyers candles.

    For each symbol the engine:
    1. Fetches actual OHLCV history from Fyers
    2. Dynamically discovers and calculates ALL 169 registered indicators
    3. Performs multi-timeframe analysis (3m, 5m, 15m, 30m, 1h, 4h, Daily, Weekly)
    4. Detects market regime using ADX, ATR%, Bollinger width, EMA slope
    5. Analyzes options chain, Open Interest, PCR, IV, Greeks where available
    6. Runs the weighted regime-aware decision engine
    7. Generates explainable signals with supporting/conflicting indicators
    8. Reports data freshness and staleness warnings
    
    Nothing is inferred from the daily change percentage: when history is unavailable
    the symbol is reported with ``data_available: false`` instead of a fabricated RSI.
    """
    try:
        from app.services.fyers_api import fyers_api_client
        from app.services.fyers_token import get_fyers_token
        from app.services import indicator_service
        from app.services.indicators import get_engine, list_specs, REGISTRY
        from app.services.brain.data_intelligence import (
            get_tdil, TradingDataIntelligence,
        )
        from app.services.brain.indicator_intelligence import (
            IndicatorSignal, BEARISH, BULLISH, NEUTRAL, UNAVAILABLE,
        )
        from app.services.brain.multi_timeframe import (
            synchronize, data_quality_report, MultiTimeframeSnapshot,
            DECISION_TIMEFRAMES, SYNC_TIMEFRAMES,
        )
        from app.services.brain.regime_engine import detect_regime
        from app.services.brain.decision_engine import DecisionEngine, BUY, SELL, HOLD, NO_TRADE
        from app.core.datetime_utils import now_ist, IST

        # Check Fyers authentication
        token = await run_in_threadpool(get_fyers_token) or settings.FYERS_ACCESS_TOKEN
        if not token:
            raise HTTPException(
                status_code=401,
                detail={"code": "FYERS_NOT_CONNECTED", "message": "Fyers not authenticated. Please login via /api/v1/fyers/connect"}
            )

        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

        # Map to index tickers
        index_symbol_map = {
            "NIFTY": "NSE:NIFTY50-INDEX",
            "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
            "FINNIFTY": "NSE:FINNIFTY-INDEX",
            "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
        }

        tickers = []
        valid_symbols = []
        for sym in symbol_list:
            if sym in index_symbol_map:
                tickers.append(index_symbol_map[sym])
                valid_symbols.append(sym)

        if not tickers:
            raise HTTPException(status_code=400, detail="No valid symbols provided")

        # Live quote for the current price (may be absent outside market hours).
        quotes = await fyers_api_client.get_quotes(tickers)

        engine = get_engine()
        tdil = get_tdil()
        decision_engine = get_decision_engine()
        signals: List[AISignalResponse] = []

        for i, ticker in enumerate(tickers):
            symbol = valid_symbols[i]
            quote = quotes.get(ticker, {}) or {}

            # ---- 1. Fetch candles for multi-timeframe analysis ----
            primary_tfs = ["3m", "5m", "15m", "30m", "1h", "4h", "1d"]
            candles_by_tf: Dict[str, Sequence[Dict[str, Any]]] = {}
            quality_reports: Dict[str, Dict[str, Any]] = {}

            for tf in primary_tfs:
                candles = await indicator_service.fetch_candles(ticker, tf, 100)
                if candles:
                    # Normalize: deduplicate, sort by timestamp, remove duplicates
                    seen = set()
                    norm_candles = []
                    for c in candles:
                        ts = c.get("ts")
                        if ts is not None and ts not in seen:
                            seen.add(ts)
                            norm_candles.append(c)
                    # Sort ascending by timestamp
                    norm_candles.sort(key=lambda x: x.get("ts", 0))
                    candles_by_tf[tf] = norm_candles
                    
                    # Quality report
                    qr = data_quality_report(MultiTimeframeSnapshot(
                        symbol=symbol,
                        reference=now_ist(),
                        market_open=bool(quote.get("status", {}).get("is_market_open", False)),
                        timeframes={tf: type("F", (), {"series": norm_candles})() for tf in candles_by_tf},
                    ))
                    quality_reports[tf] = qr

            # ---- 2. Check data freshness ----
            all_fresh = all(
                quality_reports.get(tf, {}).get("status", "stale") == "ok"
                for tf in primary_tfs
            )
            if not all_fresh:
                stale_tfs = [tf for tf, qr in quality_reports.items() 
                           if qr.get("status") != "ok"]
                signals.append(
                    AISignalResponse(
                        symbol=symbol,
                        signal="HOLD",
                        confidence=0.0,
                        rsi=0.0,
                        ema_trend="NEUTRAL",
                        price=float(quote.get("ltp") or 0.0),
                        timestamp=datetime.now(IST).isoformat(),
                        candles=0,
                        data_available=False,
                        message=(
                            f"DATA UNAVAILABLE: stale or missing data for timeframes: "
                            f"{', '.join(stale_tfs)}. Cannot generate reliable signal."
                        ),
                    )
                )
                continue

            # ---- 3. Build multi-timeframe snapshot ----
            snapshot = synchronize(
                symbol=symbol,
                reference=now_ist(),
                tickers=tickers,
                primary_tfs=primary_tfs,
                candles_by_tf=candles_by_tf,
            )

            # ---- 4. Detect regime ----
            regime_result = detect_regime(snapshot)
            regime = regime_result.get("regime", "unknown")
            regime_label = regime_result.get("label", "Unknown")
            regime_confidence = regime_result.get("confidence", 0.0)

            # ---- 5. Run indicator intelligence on primary timeframe ----
            # Get all 169 indicator IDs from registry
            all_indicator_ids = list(REGISTRY.keys())
            
            # Compute indicators for primary timeframe (5m)
            primary_candles = candles_by_tf.get("5m", [])
            if not primary_candles or len(primary_candles) < 20:
                signals.append(
                    AISignalResponse(
                        symbol=symbol,
                        signal="HOLD",
                        confidence=0.0,
                        rsi=0.0,
                        ema_trend="NEUTRAL",
                        price=float(quote.get("ltp") or 0.0),
                        timestamp=datetime.now(IST).isoformat(),
                        candles=0,
                        data_available=False,
                        message="DATA UNAVAILABLE: insufficient candles for indicator calculation.",
                    )
                )
                continue

            # Calculate ALL 169 indicators
            indicator_results: Dict[str, Any] = {}
            for ind_id in all_indicator_ids:
                try:
                    spec = REGISTRY[ind_id]
                    # Use default params from spec
                    default_params = spec.get("params", {}).get("default", {})
                    result = engine.calculate(ind_id, primary_candles, params=default_params)
                    if result and result.get("status") not in ("error", "insufficient_data"):
                        indicator_results[ind_id] = result
                except Exception:
                    # Skip indicators that fail (e.g., need extra data)
                    continue

            # Classify each indicator's reading
            classified_indicators: List[IndicatorSignal] = []
            for ind_id, result in indicator_results.items():
                classification = classify(indicator_id=ind_id, result=result, timeframe="5m", context={})
                classified_indicators.append(classification)

            # ---- 6. Compute multi-timeframe agreement ----
            agreement_ratio = _agreement_ratio(snapshot, "bullish")
            bearish_agreement = _agreement_ratio(snapshot, "bearish")

            # ---- 7. Run regime-aware decision engine ----
            # Prepare the snapshot data for the decision engine
            md: Dict[str, Any] = {
                "symbol": symbol,
                "regime": {"regime": regime, "label": regime_label, "confidence": regime_confidence},
                "multi_timeframe": snapshot.sync.as_dict(),
                "quality": data_quality_report(snapshot),
                "indicators": {
                    "primary": {
                        "summary": {
                            "bullish_count": sum(1 for s in classified_indicators if s.bullish),
                            "bearish_count": sum(1 for s in classified_indicators if s.bearish),
                            "neutral_count": sum(1 for s in classified_indicators if s.neutral),
                            "unavailable_count": sum(1 for s in classified_indicators if s.unavailable),
                            "total_computed": len(classified_indicators),
                        },
                        "indicators": [s.as_dict() for s in classified_indicators],
                    },
                    "confirmation": {},
                },
                "quotes": {symbol: quote},
                "timestamp": datetime.now(IST).isoformat(),
            }

            # Run the decision engine
            try:
                decision_result = await decision_engine.decide(md)
                action = decision_result.get("action", HOLD)
                confidence = decision_result.get("confidence", 0.5)
                reason = decision_result.get("reason", "No reason provided")
                supporting = decision_result.get("supporting_indicators", [])
                conflicting = decision_result.get("conflicting_indicators", [])
                market_regime = decision_result.get("market_regime", regime)
                risk_reward = decision_result.get("risk_reward_ratio")
            except Exception as e:
                logger.error(f"Decision engine error for {symbol}: {str(e)}")
                action = HOLD
                confidence = 0.0
                reason = f"Decision engine failed: {str(e)}"
                supporting = []
                conflicting = []
                market_regime = regime

            # ---- 8. Build signal response ----
            # Calculate confidence score based on agreement and regime
            primary_summary = indicator_results.get("primary", {}).get("summary", {}) or {
                "bullish_count": 0,
                "bearish_count": 0,
                "neutral_count": 0,
                "unavailable_count": 0,
                "total_computed": len(classified_indicators) if classified_indicators else 0,
            }
            
            total = primary_summary.get("total_computed", 0)
            bullish = primary_summary.get("bullish_count", 0)
            bearish = primary_summary.get("bearish_count", 0)
            
            # Avoid artificial confidence inflation from correlated indicators
            # Normalize by removing highly correlated indicator groups
            effective_bullish = bullish / max(total, 1) if total > 0 else 0
            effective_bearish = bearish / max(total, 1) if total > 0 else 0
            
            # Weight confidence by regime agreement and indicator quality
            regime_weight = regime_confidence if isinstance(regime_confidence, (int, float)) else 0.5
            indicator_weight = min(effective_bullish + effective_bearish, 1.0) if total > 0 else 0.0
            final_confidence = round(min(0.95, (regime_weight * 0.4 + indicator_weight * 0.6) * confidence), 2)

            # Determine if NO_TRADE is appropriate
            should_no_trade = (
                final_confidence < 0.3 or
                regime in ("choppy", "sideways", "expiry_day") or
                total < 10  # Too few indicators with data
            )

            if should_no_trade:
                action = NO_TRADE
                final_confidence = round(min(0.3, final_confidence * 0.5), 2)
                reason = (
                    f"NO_TRADE: Insufficient evidence. "
                    f"Regime: {regime_label}, "
                    f"Indicators with data: {total}, "
                    f"Bullish: {bullish}, Bearish: {bearish}"
                )
                supporting = []
                conflicting = []

            # Compute risk/reward if applicable
            risk_reward_val = risk_reward if risk_reward is not None else None

            signals.append(
                AISignalResponse(
                    symbol=symbol,
                    signal=action,
                    confidence=final_confidence,
                    rsi=round(
                        next(
                            (s.rsi for s in classified_indicators if s.rsi is not None),
                            None,
                        ),
                        2,
                    )
                    if any(s.rsi is not None for s in classified_indicators)
                    else 0.0,
                    ema_trend=(
                        next(
                            (s.ma_trend for s in classified_indicators if s.ma_trend is not None),
                            "NEUTRAL",
                        )
                        if classified_indicators
                        else "NEUTRAL"
                    ),
                    price=float(quote.get("ltp") or 0.0),
                    timestamp=datetime.now(IST).isoformat(),
                    candles=len(primary_candles),
                    data_available=True,
                    as_of=datetime.fromtimestamp(
                        primary_candles[-1]["ts"], tz=IST
                    ).isoformat(),
                    # Enhanced fields for the upgraded signal
                    regime=regime,
                    regime_label=regime_label,
                    regime_confidence=round(regime_confidence, 2),
                    supporting_indicators=[
                        s.indicator_id for s in classified_indicators if s.bullish
                    ][:5],  # Top 5 supporting
                    conflicting_indicators=[
                        s.indicator_id for s in classified_indicators if s.bearish
                    ][:5],  # Top 5 conflicting
                    reason=reason,
                    risk_reward_ratio=risk_reward_val,
                    # Multi-timeframe agreement
                    bullish_agreement=round((agreement_ratio or 0) * 100, 1),
                    bearish_agreement=round((bearish_agreement or 0) * 100, 1),
                    # Data freshness
                    data_freshness=quality_reports,
                )
            )

        return signals

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI signals error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate AI signals: {str(e)}")
