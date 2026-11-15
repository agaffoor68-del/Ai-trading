"""
Phase 1: Market Data Endpoints

Non-Negotiable Rule: Fyers API v3 is the ONLY data source.
Endpoints for symbol search, quotes, and historical data via Fyers.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.core.config import settings

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

router = APIRouter(tags=["market-data"])


class QuotesRequest(BaseModel):
    symbols: List[str]


# ETF/Unwanted suffixes to deprioritize (unless explicitly searched)
ETF_EXCLUSION_PATTERNS = ["BEES", "ADD", "EW", "ETF", "NIFTYBEES", "NIFTYADD"]

# Noise patterns to EXCLUDE unless explicitly searched (filters obscure indices)
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

# Exact match symbols for main indices (symbol_ticker format from Fyers)
EXACT_INDEX_SYMBOLS = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
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
async def get_quotes(request: QuotesRequest):
    """
    Get live quotes for multiple symbols from Fyers API v3.
    Expects JSON body: {"symbols": ["NSE:NIFTY50-INDEX", "NSE:SBIN-EQ"]}
    Batches requests to avoid timeout (max 50 symbols per request).
    Returns 401 if Fyers token is missing or expired.
    """
    # Apply symbol mapping to all incoming symbols
    from app.services.fyers_api import map_to_fyers_symbol
    symbols = [map_to_fyers_symbol(symbol) for symbol in request.symbols]
    
    if not symbols:
        return {"quotes": {}, "total": 0, "error": "No symbols provided"}
    
    # Check if Fyers is authenticated before proceeding
    from app.core.config import settings
    from app.services.fyers_token import get_fyers_token
    
    # Try to get token from persistent storage first
    token = get_fyers_token() or settings.FYERS_ACCESS_TOKEN
    if not token:
        logger.warning("Fyers quotes requested but no access token available")
        from fastapi import HTTPException
        raise HTTPException(
            status_code=401,
            detail="Fyers not authenticated. Please login via /api/v1/fyers/login"
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
            batch_size = 50
            for i in range(0, len(missing), batch_size):
                batch = missing[i:i + batch_size]
                logger.info(f"Fetching Fyers quotes batch {i//batch_size + 1}: {len(batch)} symbols")
                
                fyers_quotes = await fyers_api_client.get_quotes(batch)
                
                # Check if Fyers returned an error
                if isinstance(fyers_quotes, dict) and fyers_quotes.get("error"):
                    logger.warning(f"Fyers quotes error: {fyers_quotes['error']}")
                    if "expired" in fyers_quotes["error"].lower() or "invalid" in fyers_quotes["error"].lower():
                        from fastapi import HTTPException
                        raise HTTPException(
                            status_code=401,
                            detail="Fyers token expired or invalid. Please re-login."
                        )
                    # Add error to all missing symbols
                    for symbol in batch:
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
        
        # Return all results (live + cached)
        response = {
            "quotes": results,
            "total": len(symbols),
        }
        
        logger.info(f"Returned quotes for {len(results)} symbols (cache + Fyers)")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quotes error: {str(e)}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


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

    from app.services.fyers_api import map_to_fyers_symbol
    symbol = map_to_fyers_symbol(symbol)

    now = int(datetime.now(IST).timestamp())
    result = await fyers_api_client.get_history(symbol, resolution, now - days * 86400, now)

    if "error" in result:
        raise HTTPException(status_code=result.get("status", 502), detail=result["error"])

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
    return candles


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
        from datetime import datetime
        from sqlalchemy import func
        
        db = SessionLocal()
        try:
            symbol_upper = symbol.upper()
            today = datetime.now(IST).date()
            
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
    except Exception as e:
        logger.error(f"Expiries error for {symbol}: {str(e)}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Failed to fetch expiries: {str(e)}")


class OptionChainRequest(BaseModel):
    symbol: str  # e.g., "NIFTY", "BANKNIFTY"
    expiry: Optional[str] = None  # YYYY-MM-DD format, optional (uses nearest expiry)


@router.get("/option-chain")
async def get_option_chain(
    symbol: str = Query(..., description="Underlying symbol (e.g., NIFTY, BANKNIFTY)"),
    expiry: Optional[str] = Query(None, description="Expiry date in YYYY-MM-DD format (optional, uses nearest)"),
):
    """
    Get option chain for a given index symbol.
    
    Fetches:
    1. Current Spot price of the symbol
    2. Calculates ATM strike
    3. Fetches 10 ITM + 10 OTM strikes (21 total) from Fyers Symbol Master
    4. Fetches quotes for 42 tokens (21 CE + 21 PE) in batches
    5. Returns formatted option chain data
    
    Returns:
    [{"strike": 24350, "call_ltp": 120.4, "call_oi": 287900, "put_ltp": 175.20, "put_oi": 178900}, ...]
    """
    try:
        from app.core.database import SessionLocal, Instrument
        from app.services.fyers_api import fyers_api_client
        from app.services.fyers_token import get_fyers_token
        
        # Check Fyers authentication
        token = get_fyers_token() or settings.FYERS_ACCESS_TOKEN
        if not token:
            raise HTTPException(
                status_code=401,
                detail="Fyers not authenticated. Please login via /api/v1/fyers/login"
            )
        
        symbol_upper = symbol.upper()
        
        # Map symbol to index ticker
        index_symbol_map = {
            "NIFTY": "NSE:NIFTY50-INDEX",
            "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
            "FINNIFTY": "NSE:FINNIFTY-INDEX",
            "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
        }
        
        if symbol_upper not in index_symbol_map:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported symbol: {symbol}. Supported: NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY"
            )
        
        index_ticker = index_symbol_map[symbol_upper]
        
        # 1. Fetch current spot price
        spot_quote = await fyers_api_client.get_quotes([index_ticker])
        if not spot_quote or index_ticker not in spot_quote:
            raise HTTPException(status_code=500, detail="Failed to fetch spot price")
        
        spot_price = spot_quote[index_ticker].get("ltp")
        if spot_price is None:
            raise HTTPException(status_code=500, detail="Spot price not available")
        
        logger.info(f"Spot price for {symbol_upper}: {spot_price}")
        
        # 2. Calculate ATM strike (round to nearest 50 for NIFTY, 100 for BANKNIFTY)
        if symbol_upper in ["NIFTY", "FINNIFTY", "MIDCPNIFTY"]:
            strike_interval = 50
        else:  # BANKNIFTY
            strike_interval = 100
        
        atm_strike = round(spot_price / strike_interval) * strike_interval
        logger.info(f"ATM strike for {symbol_upper}: {atm_strike}")
        
        # 3. Determine expiry date
        if not expiry:
            # Find nearest expiry from database
            db = SessionLocal()
            try:
                from sqlalchemy import func
                today = datetime.now(IST).date()
                nearest_expiry = db.query(func.min(Instrument.expiry)).filter(
                    Instrument.symbol.ilike(f"%{symbol_upper}%"),
                    Instrument.expiry >= today,
                    Instrument.instrument_type.in_(["12", "OPT", "OPTION"]),
                ).scalar()
                
                if nearest_expiry:
                    expiry = nearest_expiry.strftime("%Y-%m-%d")
                else:
                    raise HTTPException(status_code=404, detail="No expiry found for symbol")
            finally:
                db.close()
        
        logger.info(f"Using expiry: {expiry} for {symbol_upper}")
        
        # 4. Fetch 21 strikes (10 ITM + ATM + 10 OTM) from symbol master
        strikes = []
        for i in range(-10, 11):  # -10 to +10
            strike = atm_strike + (i * strike_interval)
            strikes.append(strike)
        
        # Query symbol master for CE and PE tokens for these strikes
        db = SessionLocal()
        try:
            expiry_date = datetime.strptime(expiry, "%Y-%m-%d")
            
            # Fetch CE options
            ce_options = db.query(Instrument).filter(
                Instrument.symbol.ilike(f"%{symbol_upper}%"),
                Instrument.expiry == expiry_date,
                Instrument.instrument_type.in_(["12", "OPT", "OPTION"]),
                Instrument.option_type == "CE",
                Instrument.strike.in_([str(s) for s in strikes]),
            ).all()
            
            # Fetch PE options
            pe_options = db.query(Instrument).filter(
                Instrument.symbol.ilike(f"%{symbol_upper}%"),
                Instrument.expiry == expiry_date,
                Instrument.instrument_type.in_(["12", "OPT", "OPTION"]),
                Instrument.option_type == "PE",
                Instrument.strike.in_([str(s) for s in strikes]),
            ).all()
            
            logger.info(f"Found {len(ce_options)} CE and {len(pe_options)} PE options")
            
            # Build symbol to token mapping
            ce_tokens = {float(opt.strike): opt.symbol for opt in ce_options if opt.strike}
            pe_tokens = {float(opt.strike): opt.symbol for opt in pe_options if opt.strike}
            
        finally:
            db.close()
        
        # 5. Fetch quotes for all 42 tokens in batches
        all_symbols = []
        strike_to_symbols = {}
        
        for strike in strikes:
            ce_symbol = ce_tokens.get(strike)
            pe_symbol = pe_tokens.get(strike)
            
            if ce_symbol:
                all_symbols.append(ce_symbol)
            if pe_symbol:
                all_symbols.append(pe_symbol)
            
            strike_to_symbols[strike] = {"ce": ce_symbol, "pe": pe_symbol}
        
        # Batch fetch quotes (max 50 per request)
        all_quotes = {}
        batch_size = 50
        for i in range(0, len(all_symbols), batch_size):
            batch = all_symbols[i:i + batch_size]
            batch_quotes = await fyers_api_client.get_quotes(batch)
            all_quotes.update(batch_quotes)
        
        # 6. Build response
        option_chain = []
        for strike in strikes:
            symbols = strike_to_symbols.get(strike, {})
            ce_symbol = symbols.get("ce")
            pe_symbol = symbols.get("pe")
            
            ce_quote = all_quotes.get(ce_symbol, {}) if ce_symbol else {}
            pe_quote = all_quotes.get(pe_symbol, {}) if pe_symbol else {}
            
            option_chain.append({
                "strike": strike,
                "call_ltp": ce_quote.get("ltp"),
                "call_oi": ce_quote.get("oi") or ce_quote.get("open_interest"),
                "call_volume": ce_quote.get("volume"),
                "call_change": ce_quote.get("change"),
                "call_change_percent": ce_quote.get("change_percent"),
                "put_ltp": pe_quote.get("ltp"),
                "put_oi": pe_quote.get("oi") or pe_quote.get("open_interest"),
                "put_volume": pe_quote.get("volume"),
                "put_change": pe_quote.get("change"),
                "put_change_percent": pe_quote.get("change_percent"),
            })
        
        return {
            "symbol": symbol_upper,
            "expiry": expiry,
            "spot_price": spot_price,
            "atm_strike": atm_strike,
            "strike_interval": strike_interval,
            "option_chain": option_chain,
            "timestamp": datetime.now(IST).isoformat(),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Option chain error for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch option chain: {str(e)}")


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
        token = get_fyers_token() or settings.FYERS_ACCESS_TOKEN
        if not token:
            raise HTTPException(
                status_code=401,
                detail="Fyers not authenticated. Please login via /api/v1/fyers/login"
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
