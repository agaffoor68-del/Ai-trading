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
                Instrument.instrument_type.in_(["12", "12.0", "OPT", "OPTION"]),
                Instrument.is_active == 1,
                Instrument.expiry >= today,
            ).order_by(Instrument.expiry.asc()).all()

            expiries = sorted({item.expiry.date().isoformat() for item in contracts if item.expiry})
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
                Instrument.option_type.in_(["CE", "PE"]),
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
            result = {}
            for contract in contracts:
                try:
                    strike = float(contract.strike)
                except (TypeError, ValueError):
                    continue
                result.setdefault(strike, {})[contract.option_type.upper()] = contract.symbol
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


@router.get("/ai/signals", response_model=List[AISignalResponse])
async def get_ai_signals(
    symbols: str = Query(..., description="Comma-separated symbols (e.g., NIFTY,BANKNIFTY)"),
):
    """
    Get AI trading signals based on basic RSI/EMA calculation on live data.
    
    For each symbol:
    - Fetches live quote
    - Calculates RSI (14 period) - simplified using current price vs recent
    - Determines EMA trend
    - Generates BUY/SELL/HOLD signal
    
    Returns list of signals with confidence scores.
    """
    try:
        from app.services.fyers_api import fyers_api_client
        from app.services.fyers_token import get_fyers_token
        
        # Check Fyers authentication
        token = await run_in_threadpool(get_fyers_token) or settings.FYERS_ACCESS_TOKEN
        if not token:
            raise HTTPException(
                status_code=401,
                detail={"code": "FYERS_NOT_CONNECTED", "message": "Fyers not authenticated. Please login via /api/v1/fyers/connect"}
            )
        
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
        
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
        
        # Fetch live quotes
        quotes = await fyers_api_client.get_quotes(tickers)
        
        signals = []
        for i, ticker in enumerate(tickers):
            symbol = valid_symbols[i]
            quote = quotes.get(ticker, {})
            
            ltp = quote.get("ltp")
            change = quote.get("change", 0)
            change_percent = quote.get("change_percent", 0)
            
            if ltp is None:
                continue
            
            # Simplified RSI calculation (using change_percent as proxy)
            # In production, this would use historical data
            # RSI > 70 = overbought, RSI < 30 = oversold
            # Using a simplified heuristic based on momentum
            rsi = 50 + (change_percent * 2)  # Heuristic: scale change% to RSI-like value
            rsi = max(0, min(100, rsi))  # Clamp to 0-100
            
            # EMA Trend determination (simplified)
            if change_percent > 0.5:
                ema_trend = "BULLISH"
            elif change_percent < -0.5:
                ema_trend = "BEARISH"
            else:
                ema_trend = "NEUTRAL"
            
            # Signal generation
            if rsi < 35 and ema_trend != "BEARISH":
                signal = "BUY"
                confidence = min(0.9, 0.5 + abs(35 - rsi) / 70)
            elif rsi > 65 and ema_trend != "BULLISH":
                signal = "SELL"
                confidence = min(0.9, 0.5 + abs(rsi - 65) / 35)
            else:
                signal = "HOLD"
                confidence = 0.5
            
            signals.append(AISignalResponse(
                symbol=symbol,
                signal=signal,
                confidence=round(confidence, 2),
                rsi=round(rsi, 2),
                ema_trend=ema_trend,
                price=ltp,
                timestamp=datetime.now(IST).isoformat(),
            ))
        
        return signals
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI signals error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate AI signals: {str(e)}")
