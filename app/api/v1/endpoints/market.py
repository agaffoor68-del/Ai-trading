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


# ETF/Unwanted suffixes to deprioritize (unless explicitly searched)
ETF_EXCLUSION_PATTERNS = ["BEES", "ADD", "EW", "ETF", "NIFTYBEES", "NIFTYADD"]

# Noise patterns to EXCLUDE unless explicitly searched (filters obscure indices)
NOISE_PATTERNS = [
    "AQL", "GS", "ALPHA", "500", "200", "100", "50", 
    "MIDCAP", "SMALLCAP", "LARGECAP", "MICROCAP",
    "AUTO", "PHARMA", "IT", "METAL", "REALTY", "ENERGY",
    "MEDIA", "FMCG", "PVT", "BANK", "FIN", "COMM"
]

# Index keywords that should be prioritized
INDEX_KEYWORDS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "BANKEX"]

# Exact match symbols for main indices (symbol_ticker format from Fyers)
EXACT_INDEX_SYMBOLS = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:BANKNIFTY-INDEX",
    "FINNIFTY": "NSE:FINNIFTY-INDEX",
    "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
    "SENSEX": "BSE:SENSEX-INDEX",
    "BANKEX": "BSE:BANKEX-INDEX",
}

# Instrument type priority: Index=1, Futures=2, Options=3, Equity=4, Others=5
INSTRUMENT_TYPE_PRIORITY = {
    "13": 1,   # Index
    "INDEX": 1,
    "11": 2,   # Futures
    "FUT": 2,
    "FUTURE": 2,
    "12": 3,   # Options
    "OPT": 3,
    "OPTION": 3,
    "10": 4,   # Equity
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
    
    # If user explicitly searched for the noise term, don't filter it
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
        from sqlalchemy import or_, func

        db = SessionLocal()
        try:
            query_upper = query.upper()
            
            # Check if query is an exact index keyword
            is_exact_index = query_upper in EXACT_INDEX_SYMBOLS
            target_index_symbol = EXACT_INDEX_SYMBOLS.get(query_upper)
            
            # Fetch more results for better ranking
            fetch_limit = min(limit * 5, 200)
            
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
                .limit(fetch_limit)
                .all()
            )

            # Convert to list of dicts for ranking
            result_dicts = [
                {
                    "symbol": inst.symbol,
                    "exchange": inst.exchange,
                    "name": inst.name,
                    "fyers_token": inst.fyers_token,
                    "instrument_type": inst.instrument_type,
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
                    main_index_match = 0 if symbol == target_clean or symbol == target_index_symbol else 1
                else:
                    main_index_match = 1
                
                # 1. Exact match on symbol
                exact_match = 0 if symbol == query_upper else 1
                
                # 2. Starts with query (prefix match)
                prefix_match = 0 if symbol.startswith(query_upper) else 1
                
                # 3. Index keyword exact match (NIFTY, BANKNIFTY, etc.)
                index_priority = 0 if is_index_like(query, item.get("symbol", "")) else 1
                
                # 4. Instrument type priority (Index > FUT > OPT > EQ > Others)
                type_priority = get_instrument_priority(inst_type)
                
                # 5. F&O boost (instrument_type 11/12) for index queries
                fo_boost = 0
                if is_index_like(query, item.get("symbol", "")) and inst_type.upper() in ["11", "12", "FUT", "OPT"]:
                    fo_boost = -1  # Boost F&O for index searches
                
                # 6. ETF deprioritization
                etf_penalty = 10 if is_etf_like(symbol) else 0
                
                # 7. Segment priority (FO before CM for indices)
                segment_priority = 0 if item.get("exchange") == "NSE_FO" else 1
                
                return (main_index_match, exact_match, prefix_match, index_priority, type_priority + fo_boost, etf_penalty, segment_priority, symbol)

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
    except Exception as e:
        logger.error(f"Symbol search error: {str(e)}")
        return {"query": query, "results": [], "total": 0, "error": str(e)}


@router.post("/quotes")
async def get_quotes(
    symbols: list[str] = Query(..., description="List of symbols (e.g., NSE:NIFTY50-INDEX, NSE:SBIN-EQ)"),
):
    """
    Get live quotes for multiple symbols.
    Fyers API v3 is the ONLY data source.
    """
    try:
        from app.services.redis_ws import redis_tick_store
        
        # Check Redis cache for all symbols
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
        
        # For missing symbols, we'd normally fetch from Fyers REST API
        # For now, return what we have
        for symbol in missing:
            results[symbol] = {
                "symbol": symbol,
                "ltp": None,
                "change": None,
                "change_percent": None,
                "source": "fyers_api_v3",
                "message": "Subscribe via Fyers WebSocket for live quotes",
            }
        
        return {"quotes": results, "total": len(symbols)}
    except Exception as e:
        logger.error(f"Quotes error: {str(e)}")
        return {"quotes": {}, "total": 0, "error": str(e)}


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
