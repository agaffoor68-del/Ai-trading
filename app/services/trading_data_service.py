"""
Trading Data Intelligence Layer

Centralized, secure data access for the Grok AI Trading Brain.
Provides efficient, paginated, cached, time-window-based data retrieval
for all trading data: market data, indicators, options, trades, news, user prefs.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.database import SessionLocal, Instrument
from app.core.datetime_utils import IST, now_ist
from app.services.fyers_api import fyers_api_client
from app.services.fyers_token import get_fyers_token
from app.services.redis_ws import redis_tick_store

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models for Grok Context
# ============================================================================

class MarketDataPoint(BaseModel):
    symbol: str
    ltp: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[int] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    timestamp: Optional[str] = None
    source: str = "unknown"


class CandleData(BaseModel):
    time: int  # Unix timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float


class IndicatorValue(BaseModel):
    name: str
    value: Optional[float] = None
    values: Optional[Dict[str, float]] = None  # For multi-output indicators
    parameters: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[str] = None
    interpretation: Optional[str] = None
    category: Optional[str] = None


class OptionGreeks(BaseModel):
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None


class OptionChainData(BaseModel):
    symbol: str
    expiry: str
    spot_price: float
    atm_strike: float
    strikes: List[Dict[str, Any]] = Field(default_factory=list)
    pcr: Optional[float] = None
    max_pain: Optional[float] = None
    gex: Optional[float] = None
    dex: Optional[float] = None
    iv_rank: Optional[float] = None
    iv_percentile: Optional[float] = None
    timestamp: str


class NewsArticle(BaseModel):
    headline: str
    source: str
    url: str
    timestamp: str
    instrument: Optional[str] = None
    sector: Optional[str] = None
    sentiment: Optional[str] = None  # "positive", "negative", "neutral"
    impact: Optional[str] = None  # "high", "medium", "low"
    reliability: Optional[str] = None  # "confirmed", "unverified", "rumor"
    impact_duration: Optional[str] = None  # "intraday", "swing", "long-term"


class TradeSummary(BaseModel):
    decision_id: str
    instrument: str
    decision: str  # BUY, SELL, HOLD
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    targets: List[float] = Field(default_factory=list)
    actual_entry: Optional[float] = None
    actual_exit: Optional[float] = None
    pnl: Optional[float] = None
    duration_minutes: Optional[int] = None
    outcome: Optional[str] = None  # "WIN", "LOSS", "BREAKEVEN", "OPEN"
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    timestamp: str


class UserPreferences(BaseModel):
    selected_instruments: List[str] = Field(default_factory=list)
    preferred_timeframes: List[str] = Field(default_factory=list)
    risk_per_trade_pct: float = 2.0
    max_daily_loss_pct: float = 5.0
    max_open_positions: int = 5
    enabled_strategies: List[str] = Field(default_factory=list)
    selected_indicators: List[str] = Field(default_factory=list)
    trading_mode: str = "ANALYSIS_ONLY"  # ANALYSIS_ONLY, PAPER, APPROVAL, AUTONOMOUS


class DataQuality(BaseModel):
    completeness: float  # 0.0 - 1.0
    freshness_seconds: Optional[int] = None
    source: str
    warnings: List[str] = Field(default_factory=list)


class GrokContext(BaseModel):
    """Complete structured context for Grok AI analysis."""
    instrument: str
    timeframe: str
    market_data: Optional[MarketDataPoint] = None
    candles: List[CandleData] = Field(default_factory=list)
    indicators: List[IndicatorValue] = Field(default_factory=list)
    options: Optional[OptionChainData] = None
    news: List[NewsArticle] = Field(default_factory=list)
    trades: List[TradeSummary] = Field(default_factory=list)
    user_prefs: Optional[UserPreferences] = None
    data_quality: DataQuality = Field(
        default_factory=lambda: DataQuality(completeness=0.0, source="unknown")
    )
    generated_at: str = Field(default_factory=lambda: now_ist().isoformat())


@dataclass
class ContextRetrievalConfig:
    """Configuration for context retrieval."""
    lookback_candles: int = 100
    max_news_articles: int = 20
    max_trades: int = 50
    news_timeframe_hours: int = 24
    include_options: bool = True
    include_news: bool = True
    include_trades: bool = True
    indicator_categories: Optional[List[str]] = None  # None = all


# ============================================================================
# Trading Data Service
# ============================================================================

class TradingDataService:
    """
    Centralized, secure data access for Grok AI.
    
    Features:
    - Efficient data retrieval with pagination & time windows
    - Redis caching for frequently accessed data
    - Time-window-based retrieval (not full history dumps)
    - Data quality metrics
    - Rate limiting protection
    - Structured, typed responses
    """

    def __init__(self):
        self._candle_cache: Dict[str, List[CandleData]] = {}
        self._indicator_cache: Dict[str, List[IndicatorValue]] = {}
        self._cache_ttl_seconds = 60  # 1 minute cache for live data

    # -------------------------------------------------------------------------
    # Market Data
    # -------------------------------------------------------------------------

    async def get_live_quotes(self, symbols: List[str]) -> Dict[str, MarketDataPoint]:
        """Get live quotes from Redis cache with Fyers REST fallback."""
        if not symbols:
            return {}

        results = {}
        missing = []

        # 1. Try Redis cache first (populated by WebSocket)
        for symbol in symbols:
            try:
                cached = await redis_tick_store.get_tick(symbol)
                if cached and cached.get("ltp") is not None:
                    results[symbol] = MarketDataPoint(
                        symbol=symbol,
                        ltp=cached.get("ltp"),
                        change=cached.get("change"),
                        change_percent=cached.get("change_percent"),
                        bid=cached.get("bid"),
                        ask=cached.get("ask"),
                        volume=cached.get("volume"),
                        open=cached.get("open"),
                        high=cached.get("high"),
                        low=cached.get("low"),
                        close=cached.get("close"),
                        timestamp=cached.get("updated_at"),
                        source="redis_cache",
                    )
                else:
                    missing.append(symbol)
            except Exception as e:
                logger.warning(f"Redis tick read failed for {symbol}: {e}")
                missing.append(symbol)

        # 2. Fallback to Fyers REST for missing symbols
        if missing:
            try:
                fyers_quotes = await fyers_api_client.get_quotes(missing)
                if isinstance(fyers_quotes, dict) and not fyers_quotes.get("error"):
                    for symbol, quote in fyers_quotes.items():
                        if isinstance(quote, dict) and quote.get("ltp") is not None:
                            results[symbol] = MarketDataPoint(
                                symbol=symbol,
                                ltp=quote.get("ltp"),
                                change=quote.get("change"),
                                change_percent=quote.get("change_percent"),
                                bid=quote.get("bid"),
                                ask=quote.get("ask"),
                                volume=quote.get("volume"),
                                open=quote.get("open"),
                                high=quote.get("high"),
                                low=quote.get("low"),
                                close=quote.get("close"),
                                timestamp=quote.get("updated_at") or quote.get("timestamp"),
                                source="fyers_rest_fallback",
                            )
                            # Write back to Redis for next time
                            try:
                                await redis_tick_store.write_tick(symbol, quote)
                            except Exception:
                                pass
                        else:
                            results[symbol] = MarketDataPoint(
                                symbol=symbol,
                                source="fyers_rest_fallback",
                            )
                # Symbols not returned by Fyers at all
                for symbol in missing:
                    if symbol not in results:
                        results[symbol] = MarketDataPoint(symbol=symbol, source="unavailable")
            except Exception as e:
                logger.warning(f"Fyers REST fallback failed: {e}")
                for symbol in missing:
                    if symbol not in results:
                        results[symbol] = MarketDataPoint(symbol=symbol, source="error")

        return results

    async def get_candles(
        self,
        symbol: str,
        interval: str = "5m",
        lookback: int = 100,
    ) -> List[CandleData]:
        """Get historical candles with caching."""
        cache_key = f"{symbol}:{interval}:{lookback}"
        
        # Check cache first
        if cache_key in self._candle_cache:
            cached = self._candle_cache[cache_key]
            if cached and len(cached) >= lookback:
                return cached[-lookback:]

        # Fetch from Fyers
        from app.api.v1.endpoints.market import INTERVAL_TO_RESOLUTION
        resolution = INTERVAL_TO_RESOLUTION.get(interval.strip().lower(), "5")
        
        try:
            now_ts = int(now_ist().timestamp())
            # Calculate lookback days based on interval
            if interval in ["1m", "2m", "3m", "5m"]:
                days = max(1, lookback // 75)  # ~75 candles per day in 5m
            elif interval in ["15m", "30m"]:
                days = max(1, lookback // 20)
            elif interval in ["1h", "2h", "4h"]:
                days = max(1, lookback // 6)
            else:
                days = max(5, lookback)

            result = await fyers_api_client.get_history(
                symbol=symbol,
                resolution=resolution,
                start_ts=now_ts - days * 86400,
                end_ts=now_ts,
            )

            if isinstance(result, dict) and result.get("candles"):
                candles = []
                for c in result["candles"]:
                    if len(c) >= 6:
                        candles.append(CandleData(
                            time=c[0],
                            open=c[1],
                            high=c[2],
                            low=c[3],
                            close=c[4],
                            volume=c[5],
                        ))
                
                # Cache the result
                self._candle_cache[cache_key] = candles
                return candles[-lookback:]
        except Exception as e:
            logger.error(f"Failed to fetch candles for {symbol}: {e}")

        return []

    async def get_instrument_info(self, symbol: str) -> Dict[str, Any]:
        """Get instrument info (lot size, tick size, expiries)."""
        try:
            from app.core.database import SessionLocal, Instrument
            from sqlalchemy import func
            
            db = SessionLocal()
            try:
                # This mirrors the instrument-info endpoint logic
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
                    return {"error": f"Unsupported underlying: {symbol}"}
                
                exchange, underlying = mapping
                today = now_ist().date()
                
                contracts = db.query(Instrument).filter(
                    Instrument.exchange == "NSE_FO" if exchange == "NSE" else "BSE_FO",
                    Instrument.symbol.ilike(f"{exchange}:{underlying}%"),
                    Instrument.is_active == 1,
                ).order_by(Instrument.expiry.asc()).all()

                expiries = sorted({
                    item.expiry.date().isoformat() 
                    for item in contracts 
                    if item.expiry and item.expiry.date() >= today
                })

                if not expiries:
                    return {"symbol": underlying, "expiry_dates": [], "note": "No active expiries"}

                nearest_expiry = expiries[0]
                current_contracts = [
                    item for item in contracts 
                    if item.expiry and item.expiry.date().isoformat() == nearest_expiry
                ]
                
                from collections import Counter
                lot_sizes = Counter(
                    int(item.lot_size) 
                    for item in current_contracts 
                    if item.lot_size and int(item.lot_size) > 0
                )
                tick_sizes = Counter(
                    str(item.tick_size) 
                    for item in current_contracts 
                    if item.tick_size
                )

                return {
                    "symbol": underlying,
                    "lot_size": lot_sizes.most_common(1)[0][0] if lot_sizes else None,
                    "tick_size": float(tick_sizes.most_common(1)[0][0]) if tick_sizes else None,
                    "expiry_dates": expiries,
                }
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Instrument info failed for {symbol}: {e}")
            return {"error": str(e)}

    # -------------------------------------------------------------------------
    # Indicators
    # -------------------------------------------------------------------------

    async def calculate_indicators(
        self,
        symbol: str,
        timeframe: str,
        indicator_names: Optional[List[str]] = None,
        category: Optional[str] = None,
        lookback: int = 200,
    ) -> List[IndicatorValue]:
        """Calculate indicators for a symbol/timeframe."""
        # Fetch candles for calculation
        candles = await self.get_candles(symbol, timeframe, lookback)
        if len(candles) < 20:
            return []

        # Convert to DataFrame for pandas_ta
        import pandas as pd
        import pandas_ta as ta
        
        df = pd.DataFrame([{
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
        } for c in candles])

        results = []
        
        # Determine which indicators to calculate
        from app.services.indicator_engine import INDICATOR_REGISTRY
        
        if indicator_names:
            indicators_to_calc = {k: v for k, v in INDICATOR_REGISTRY.items() if k in indicator_names}
        elif category:
            indicators_to_calc = {k: v for k, v in INDICATOR_REGISTRY.items() if v.get("category") == category}
        else:
            indicators_to_calc = INDICATOR_REGISTRY

        for name, config in indicators_to_calc.items():
            try:
                func = config["func"]
                params = config["params"].get("default", {})
                
                # Call the pandas_ta function
                result = func(df["close"], **params) if "close" in func.__code__.co_varnames else func(df, **params)
                
                if result is not None and not result.empty:
                    # Get latest values
                    output_cols = config.get("output_cols", [])
                    output_names = config.get("output_names", {})
                    
                    for col in output_cols:
                        if col in result.columns:
                            latest_val = result[col].iloc[-1]
                            if pd.notna(latest_val):
                                display_name = output_names.get(col, col)
                                results.append(IndicatorValue(
                                    name=display_name,
                                    value=float(latest_val),
                                    parameters=params,
                                    timestamp=now_ist().isoformat(),
                                    category=config.get("category", "unknown"),
                                ))
            except Exception as e:
                logger.warning(f"Indicator {name} calculation failed: {e}")
                continue

        return results

    # -------------------------------------------------------------------------
    # Options Data
    # -------------------------------------------------------------------------

    async def get_options_chain(
        self,
        symbol: str,
        expiry: Optional[str] = None,
        strike_count: int = 10,
    ) -> Optional[OptionChainData]:
        """Get option chain with Greeks and analytics."""
        try:
            # Normalize symbol
            underlying_map = {
                "NIFTY": ("NSE", "NIFTY", "NSE:NIFTY50-INDEX"),
                "NIFTY 50": ("NSE", "NIFTY", "NSE:NIFTY50-INDEX"),
                "BANKNIFTY": ("NSE", "BANKNIFTY", "NSE:NIFTYBANK-INDEX"),
                "BANK NIFTY": ("NSE", "BANKNIFTY", "NSE:NIFTYBANK-INDEX"),
                "FINNIFTY": ("NSE", "FINNIFTY", "NSE:FINNIFTY-INDEX"),
                "MIDCPNIFTY": ("NSE", "MIDCPNIFTY", "NSE:MIDCPNIFTY-INDEX"),
                "SENSEX": ("BSE", "SENSEX", "BSE:SENSEX-INDEX"),
            }
            normalized = " ".join(symbol.upper().split())
            mapping = underlying_map.get(normalized)
            if not mapping:
                return None
            
            exchange, underlying, underlying_ticker = mapping
            
            # Get spot price
            quotes = await fyers_api_client.get_quotes([underlying_ticker])
            spot_price = 0.0
            if isinstance(quotes, dict) and not quotes.get("error"):
                spot_price = float(quotes.get(underlying_ticker, {}).get("ltp", 0))
            
            if spot_price <= 0:
                return None

            # Parse expiry
            if expiry:
                try:
                    expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                except ValueError:
                    return None
            else:
                expiry_date = None

            # Load contracts from database
            from app.core.database import SessionLocal, Instrument
            
            def load_contracts():
                db = SessionLocal()
                try:
                    today = now_ist().date()
                    query = db.query(Instrument).filter(
                        Instrument.exchange == ("NSE_FO" if exchange == "NSE" else "BSE_FO"),
                        Instrument.symbol.ilike(f"{exchange}:{underlying}%"),
                        Instrument.is_active == 1,
                        Instrument.expiry.is_not(None),
                        Instrument.expiry >= datetime.combine(today, datetime.min.time()),
                    ).order_by(Instrument.expiry.asc())

                    instruments = query.all()
                    candidates = []

                    for item in instruments:
                        ticker = (item.symbol or "").strip()
                        ticker_upper = ticker.upper()
                        side = (item.option_type or "").strip().upper()
                        if side not in {"CE", "PE"} and ticker_upper.endswith(("CE", "PE")):
                            side = ticker_upper[-2:]

                        code = str(item.instrument_type or "").strip().upper()
                        has_option_code = code in {"12", "12.0", "OPT", "OPTION"}
                        has_option_suffix = ticker_upper.endswith(("CE", "PE"))
                        expected_prefix = f"{exchange}:{underlying}".upper()

                        if side in {"CE", "PE"} and (has_option_code or has_option_suffix) and ticker_upper.startswith(expected_prefix):
                            if item.expiry is None:
                                import re
                                m = re.search(r"(\d{2})([A-Z]{3})(\d{3,})", ticker_upper)
                                if m:
                                    dd, mon, _ = m.groups()
                                    try:
                                        item.expiry = datetime.strptime(f"{dd}-{mon}-{today.year}", "%d-%b-%Y")
                                    except ValueError:
                                        pass
                            candidates.append((item, side))
                    
                    return candidates, spot_price
                finally:
                    db.close()

            candidates, spot = await asyncio.to_thread(load_contracts)
            
            if not candidates:
                return None

            # Filter by expiry
            active_expiries = sorted({
                item.expiry.date() 
                for item, _ in candidates 
                if item.expiry and item.expiry.date() >= now_ist().date()
            })
            
            if not active_expiries:
                return None

            chosen_expiry = expiry_date if expiry_date in active_expiries else active_expiries[0]
            
            # Filter to chosen expiry
            expiry_candidates = [
                (item, side) for item, side in candidates 
                if item.expiry and item.expiry.date() == chosen_expiry
            ]

            # Group by strike
            from collections import defaultdict
            strikes_dict = defaultdict(lambda: {"CE": None, "PE": None})
            for item, side in expiry_candidates:
                try:
                    strike = float(item.strike)
                    if abs(strike - spot) <= max(spot * 0.20, 5000):
                        month_code = item.expiry.strftime("%y%b").upper() if item.expiry else ""
                        canonical = f"{exchange}:{underlying}{month_code}{strike:g}{side}"
                        strikes_dict[strike][side] = canonical
                except (TypeError, ValueError):
                    continue

            available_strikes = sorted(strikes_dict.keys())
            if not available_strikes:
                return None

            # Find ATM
            atm_strike = min(available_strikes, key=lambda s: abs(s - spot))
            atm_index = available_strikes.index(atm_strike)
            selected_strikes = available_strikes[
                max(0, atm_index - strike_count):
                min(len(available_strikes), atm_index + strike_count + 1)
            ]

            # Get quotes for selected options
            option_symbols = []
            for strike in selected_strikes:
                for side in ("CE", "PE"):
                    if strikes_dict[strike].get(side):
                        option_symbols.append(strikes_dict[strike][side])

            option_quotes = {}
            for i in range(0, len(option_symbols), 50):
                batch = await fyers_api_client.get_quotes(option_symbols[i:i+50])
                if isinstance(batch, dict) and not batch.get("error"):
                    option_quotes.update(batch)

            # Build strikes data
            strikes_data = []
            for strike in selected_strikes:
                legs = strikes_dict[strike]
                ce_symbol = legs.get("CE")
                pe_symbol = legs.get("PE")
                
                ce_quote = option_quotes.get(ce_symbol, {}) if ce_symbol else {}
                pe_quote = option_quotes.get(pe_symbol, {}) if pe_symbol else {}
                
                strikes_data.append({
                    "strike": strike,
                    "call_ltp": ce_quote.get("ltp"),
                    "call_symbol": ce_symbol,
                    "call_oi": ce_quote.get("oi"),
                    "call_oi_change": ce_quote.get("oi_change"),
                    "call_iv": ce_quote.get("iv"),
                    "call_greeks": {
                        "delta": ce_quote.get("delta"),
                        "gamma": ce_quote.get("gamma"),
                        "theta": ce_quote.get("theta"),
                        "vega": ce_quote.get("vega"),
                    } if any(k in ce_quote for k in ["delta", "gamma", "theta", "vega"]) else None,
                    "put_ltp": pe_quote.get("ltp"),
                    "put_symbol": pe_symbol,
                    "put_oi": pe_quote.get("oi"),
                    "put_oi_change": pe_quote.get("oi_change"),
                    "put_iv": pe_quote.get("iv"),
                    "put_greeks": {
                        "delta": pe_quote.get("delta"),
                        "gamma": pe_quote.get("gamma"),
                        "theta": pe_quote.get("theta"),
                        "vega": pe_quote.get("vega"),
                    } if any(k in pe_quote for k in ["delta", "gamma", "theta", "vega"]) else None,
                    "is_atm": strike == atm_strike,
                })

            # Calculate PCR
            total_call_oi = sum(s.get("call_oi", 0) or 0 for s in strikes_data)
            total_put_oi = sum(s.get("put_oi", 0) or 0 for s in strikes_data)
            pcr = total_put_oi / total_call_oi if total_call_oi > 0 else None

            # Max Pain calculation (simplified)
            max_pain = None
            if strikes_data:
                min_pain = float('inf')
                for s in strikes_data:
                    strike = s["strike"]
                    call_oi = s.get("call_oi", 0) or 0
                    put_oi = s.get("put_oi", 0) or 0
                    pain = call_oi * max(0, strike - atm_strike) + put_oi * max(0, atm_strike - strike)
                    if pain < min_pain:
                        min_pain = pain
                        max_pain = strike

            return OptionChainData(
                symbol=underlying,
                expiry=chosen_expiry.isoformat(),
                spot_price=spot,
                atm_strike=atm_strike,
                strikes=strikes_data,
                pcr=pcr,
                max_pain=max_pain,
                timestamp=now_ist().isoformat(),
            )
        except Exception as e:
            logger.error(f"Options chain failed for {symbol}: {e}")
            return None

    # -------------------------------------------------------------------------
    # News
    # -------------------------------------------------------------------------

    async def get_news(
        self,
        instrument: Optional[str] = None,
        sector: Optional[str] = None,
        timeframe_hours: int = 24,
        sentiment: Optional[str] = None,
        limit: int = 20,
    ) -> List[NewsArticle]:
        """Get filtered news articles."""
        # This would query a news_articles table
        # For now, return empty list - to be implemented with news ingestion
        return []

    # -------------------------------------------------------------------------
    # Trade History & Memory
    # -------------------------------------------------------------------------

    async def get_trade_history(
        self,
        instrument: Optional[str] = None,
        limit: int = 50,
        days: int = 30,
    ) -> List[TradeSummary]:
        """Get recent trade history."""
        # This would query ai_decisions and trade_lifecycles tables
        return []

    async def get_learning_insights(
        self,
        instrument: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get learning insights from past trades."""
        return []

    # -------------------------------------------------------------------------
    # User Preferences
    # -------------------------------------------------------------------------

    async def get_user_preferences(self, user_id: int) -> UserPreferences:
        """Get user trading preferences."""
        # This would query user_ai_preferences table
        return UserPreferences()

    # -------------------------------------------------------------------------
    # Context Assembly for Grok
    # -------------------------------------------------------------------------

    async def assemble_grok_context(
        self,
        instrument: str,
        timeframe: str = "15m",
        config: Optional[ContextRetrievalConfig] = None,
    ) -> GrokContext:
        """Assemble complete structured context for Grok analysis."""
        cfg = config or ContextRetrievalConfig()
        
        # Run all data fetches in parallel
        live_quotes_task = self.get_live_quotes([instrument])
        candles_task = self.get_candles(instrument, timeframe, cfg.lookback_candles)
        
        indicators_task = self.calculate_indicators(
            instrument, timeframe, 
            category=cfg.indicator_categories[0] if cfg.indicator_categories else None,
            lookback=cfg.lookback_candles
        )
        
        options_task = self.get_options_chain(instrument) if cfg.include_options else asyncio.sleep(0, result=None)
        news_task = self.get_news(instrument, timeframe_hours=cfg.news_timeframe_hours, limit=cfg.max_news_articles) if cfg.include_news else asyncio.sleep(0, result=[])
        trades_task = self.get_trade_history(instrument, limit=cfg.max_trades) if cfg.include_trades else asyncio.sleep(0, result=[])

        # Wait for all
        live_quotes, candles, indicators, options, news, trades = await asyncio.gather(
            live_quotes_task,
            candles_task,
            indicators_task,
            options_task,
            news_task,
            trades_task,
            return_exceptions=True,
        )

        # Handle exceptions
        for i, (name, result) in enumerate([
            ("live_quotes", live_quotes),
            ("candles", candles),
            ("indicators", indicators),
            ("options", options),
            ("news", news),
            ("trades", trades),
        ]):
            if isinstance(result, Exception):
                logger.error(f"Context assembly failed for {name}: {result}")
                if name == "live_quotes":
                    live_quotes = {}
                elif name == "candles":
                    candles = []
                elif name == "indicators":
                    indicators = []
                elif name == "options":
                    options = None
                elif name == "news":
                    news = []
                elif name == "trades":
                    trades = []

        # Build data quality metrics
        completeness = 0.0
        sources = []
        warnings = []
        
        if live_quotes and live_quotes.get(instrument):
            completeness += 0.3
            sources.append(live_quotes[instrument].source)
        else:
            warnings.append(f"No live quote for {instrument}")
        
        if candles:
            completeness += 0.3
            sources.append("fyers_candles")
        else:
            warnings.append("No candle data")
        
        if indicators:
            completeness += 0.2
        else:
            warnings.append("No indicators calculated")
        
        if options:
            completeness += 0.1
        if news:
            completeness += 0.1

        data_quality = DataQuality(
            completeness=completeness,
            freshness_seconds=30 if live_quotes.get(instrument, {}).get("source") == "redis_cache" else None,
            source=", ".join(set(sources)) or "unknown",
            warnings=warnings,
        )

        return GrokContext(
            instrument=instrument,
            timeframe=timeframe,
            market_data=live_quotes.get(instrument),
            candles=candles[-cfg.lookback_candles:] if isinstance(candles, list) else [],
            indicators=indicators if isinstance(indicators, list) else [],
            options=options if isinstance(options, OptionChainData) else None,
            news=news if isinstance(news, list) else [],
            trades=trades if isinstance(trades, list) else [],
            data_quality=data_quality,
        )


# ============================================================================
# Singleton Instance
# ============================================================================

_trading_data_service: Optional[TradingDataService] = None


def get_trading_data_service() -> TradingDataService:
    """Get or create the singleton trading data service instance."""
    global _trading_data_service
    if _trading_data_service is None:
        _trading_data_service = TradingDataService()
    return _trading_data_service
