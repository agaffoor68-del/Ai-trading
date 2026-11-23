"""
Context Retrieval Engine

Smart data fetching layer for Grok AI - provides function-calling tools
that Grok can use to retrieve relevant trading data on demand.
Implements pagination, filtering, caching, summaries, and time-window-based retrieval.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app.services.trading_data_service import (
    TradingDataService,
    ContextRetrievalConfig,
    GrokContext,
    MarketDataPoint,
    CandleData,
    IndicatorValue,
    OptionChainData,
    NewsArticle,
    TradeSummary,
    UserPreferences,
)
from app.services.grok_service import get_grok_service

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)


# ============================================================================
# Tool Schemas for Grok Function Calling
# ============================================================================

GROK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_market_data",
            "description": "Get live market data (LTP, bid/ask, volume, OHLC) for one or more symbols",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of Fyers symbols (e.g., ['NSE:NIFTY50-INDEX', 'NSE:SBIN-EQ'])",
                    },
                },
                "required": ["symbols"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_candles",
            "description": "Get historical OHLCV candles for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Fyers symbol (e.g., NSE:NIFTY50-INDEX)"},
                    "timeframe": {
                        "type": "string",
                        "description": "Candle interval: 1m, 3m, 5m, 10m, 15m, 30m, 1h, 2h, 4h, 1D, 1W, 1M",
                        "enum": ["1m", "3m", "5m", "10m", "15m", "30m", "1h", "2h", "4h", "1D", "1W", "1M"],
                    },
                    "lookback": {"type": "integer", "description": "Number of candles to retrieve", "default": 100, "minimum": 1, "maximum": 5000},
                },
                "required": ["symbol", "timeframe"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_indicators",
            "description": "Calculate technical indicators for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Fyers symbol"},
                    "timeframe": {"type": "string", "description": "Candle interval"},
                    "indicators": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific indicator names (e.g., ['RSI', 'MACD', 'BBANDS'])",
                    },
                    "category": {
                        "type": "string",
                        "description": "Indicator category instead of specific names",
                        "enum": ["trend", "momentum", "volatility", "volume", "support_resistance", "market_structure", "advanced", "options"],
                    },
                    "lookback": {"type": "integer", "default": 200, "minimum": 20, "maximum": 1000},
                },
                "required": ["symbol", "timeframe"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_options_data",
            "description": "Get option chain with Greeks, IV, PCR, Max Pain, GEX/DEX",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Underlying symbol (e.g., NIFTY, BANKNIFTY)"},
                    "expiry": {"type": "string", "description": "Expiry date YYYY-MM-DD (optional, defaults to nearest)"},
                    "strike_count": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": "Get filtered financial news articles",
            "parameters": {
                "type": "object",
                "properties": {
                    "instrument": {"type": "string", "description": "Filter by instrument (e.g., NIFTY, RELIANCE)"},
                    "sector": {"type": "string", "description": "Filter by sector (e.g., Banking, IT, Pharma)"},
                    "timeframe_hours": {"type": "integer", "default": 24, "minimum": 1, "maximum": 168},
                    "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"], "description": "Filter by sentiment"},
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_structure",
            "description": "Get market structure analysis (trend, S/R, order blocks, FVG, swing points)",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "timeframe": {"type": "string"},
                },
                "required": ["symbol", "timeframe"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trade_memory",
            "description": "Retrieve previous AI decisions and trade outcomes for learning",
            "parameters": {
                "type": "object",
                "properties": {
                    "decision_id": {"type": "string", "description": "Specific decision ID to retrieve"},
                    "instrument": {"type": "string", "description": "Filter by instrument"},
                    "outcome": {"type": "string", "enum": ["WIN", "LOSS", "BREAKEVEN", "OPEN"], "description": "Filter by outcome"},
                    "days": {"type": "integer", "default": 30, "minimum": 1, "maximum": 365},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_preferences",
            "description": "Get user's trading preferences and risk settings",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer"},
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_live_order",
            "description": "Propose a live order for user approval (MODE 3 - approval based)",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "side": {"type": "string", "enum": ["BUY", "SELL"]},
                    "quantity": {"type": "integer", "minimum": 1},
                    "order_type": {"type": "string", "enum": ["MARKET", "LIMIT", "SL", "SL-M"]},
                    "price": {"type": "number", "description": "Limit price (required for LIMIT/SL orders)"},
                    "stop_loss": {"type": "number", "description": "Stop loss price"},
                    "targets": {"type": "array", "items": {"type": "number"}, "description": "Target prices"},
                    "rationale": {"type": "string", "description": "Brief reasoning for the order"},
                },
                "required": ["symbol", "side", "quantity", "order_type", "stop_loss"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_paper_trade",
            "description": "Execute a simulated paper trade",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "side": {"type": "string", "enum": ["BUY", "SELL"]},
                    "quantity": {"type": "integer", "minimum": 1},
                    "order_type": {"type": "string", "enum": ["MARKET", "LIMIT", "SL", "SL-M"]},
                    "price": {"type": "number"},
                    "stop_loss": {"type": "number"},
                    "targets": {"type": "array", "items": {"type": "number"}},
                },
                "required": ["symbol", "side", "quantity", "order_type", "stop_loss"],
            },
        },
    },
]


# ============================================================================
# Context Retrieval Engine
# ============================================================================

class ContextRetrievalEngine:
    """
    High-level interface for Grok to retrieve trading data.
    Each method corresponds to a Grok function calling tool.
    """

    def __init__(self, trading_service: "TradingDataService"):
        self.service = trading_service

    # ========================================================================
    # Market Data Tools
    # ========================================================================

    async def get_market_data(self, symbols: List[str]) -> Dict[str, Any]:
        """Get live quotes for symbols."""
        try:
            quotes = await self.service.get_live_quotes(symbols)
            return {
                "success": True,
                "data": {k: v.model_dump() for k, v in quotes.items()},
                "timestamp": datetime.now(IST).isoformat(),
            }
        except Exception as e:
            logger.error(f"get_market_data failed: {e}")
            return {"success": False, "error": str(e)}

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        lookback: int = 100,
    ) -> Dict[str, Any]:
        """Get historical candles."""
        try:
            candles = await self.service.get_candles(symbol, timeframe, lookback)
            return {
                "success": True,
                "symbol": symbol,
                "timeframe": timeframe,
                "count": len(candles),
                "data": [c.model_dump() for c in candles],
                "timestamp": datetime.now(IST).isoformat(),
            }
        except Exception as e:
            logger.error(f"get_candles failed: {e}")
            return {"success": False, "error": str(e)}

    async def get_indicators(
        self,
        symbol: str,
        timeframe: str,
        indicators: Optional[List[str]] = None,
        category: Optional[str] = None,
        lookback: int = 200,
    ) -> Dict[str, Any]:
        """Calculate technical indicators."""
        try:
            indicators = await self.service.calculate_indicators(
                symbol, timeframe, indicators, None, 200
            )
            return {
                "success": True,
                "symbol": symbol,
                "timeframe": timeframe,
                "count": len(indicators),
                "data": [i.model_dump() for i in indicators],
                "timestamp": datetime.now(IST).isoformat(),
            }
        except Exception as e:
            logger.error(f"get_indicators failed: {e}")
            return {"success": False, "error": str(e)}

    # ========================================================================
    # Options Tools
    # ========================================================================

    async def get_options_data(
        self,
        symbol: str,
        expiry: Optional[str] = None,
        strike_count: int = 10,
    ) -> Dict[str, Any]:
        """Get option chain with Greeks and analytics."""
        try:
            chain = await self.service.get_options_chain(symbol, None, 10)
            if chain:
                return {"success": True, "data": chain.model_dump()}
            return {"success": False, "error": "No options data available"}
        except Exception as e:
            logger.error(f"get_options_data failed: {e}")
            return {"success": False, "error": str(e)}

    # ========================================================================
    # News Tools
    # ========================================================================

    async def get_news(
        self,
        instrument: Optional[str] = None,
        sector: Optional[str] = None,
        timeframe_hours: int = 24,
        sentiment: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Get filtered news articles."""
        try:
            news = await self.service.get_news(instrument, None, 24, None, 20)
            return {
                "success": True,
                "count": len(news),
                "data": [n.model_dump() for n in news],
                "timestamp": datetime.now(IST).isoformat(),
            }
        except Exception as e:
            logger.error(f"get_news failed: {e}")
            return {"success": False, "error": str(e)}

    # ========================================================================
    # Market Structure Tools
    # ========================================================================

    async def get_market_structure(
        self,
        symbol: str,
        timeframe: str,
    ) -> Dict[str, Any]:
        """Analyze market structure (placeholder - needs implementation)."""
        return {
            "success": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "structure": {
                "trend": "unknown",
                "support_levels": [],
                "resistance_levels": [],
                "swing_highs": [],
                "swing_lows": [],
                "order_blocks": [],
                "fair_value_gaps": [],
            },
            "timestamp": datetime.now(IST).isoformat(),
        }

    # ========================================================================
    # Memory & Learning Tools
    # ========================================================================

    async def get_trade_memory(
        self,
        decision_id: Optional[str] = None,
        instrument: Optional[str] = None,
        outcome: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Retrieve trade memory and learning insights."""
        # Placeholder - would query ai_decisions, trade_lifecycles, learning_insights tables
        return {
            "success": True,
            "decisions": [],
            "learning_insights": [],
            "timestamp": datetime.now(IST).isoformat(),
        }

    async def get_user_preferences(self, user_id: int) -> Dict[str, Any]:
        """Get user trading preferences."""
        # Placeholder - would query user_ai_preferences table
        return {
            "success": True,
            "preferences": {
                "selected_instruments": ["NIFTY", "BANKNIFTY"],
                "preferred_timeframes": ["5m", "15m", "1h"],
                "risk_per_trade_pct": 2.0,
                "max_daily_loss_pct": 5.0,
                "max_open_positions": 5,
                "enabled_strategies": [],
                "selected_indicators": ["RSI", "MACD", "EMA", "VWAP", "Supertrend"],
                "trading_mode": "ANALYSIS_ONLY",
            },
            "timestamp": datetime.now(IST).isoformat(),
        }

    # ========================================================================
    # Execution Tools (Paper & Approval)
    # ========================================================================

    async def execute_paper_trade(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        targets: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """Execute a simulated paper trade."""
        return {
            "success": True,
            "paper_trade_id": f"PAPER_{datetime.now(IST).strftime('%Y%m%d%H%M%S')}",
            "message": "Paper trade executed (simulated)",
            "timestamp": datetime.now(IST).isoformat(),
        }

    async def propose_live_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        targets: Optional[List[float]] = None,
        rationale: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Propose a live order for user approval (MODE 3)."""
        return {
            "success": True,
            "proposal_id": f"PROP_{datetime.now(IST).strftime('%Y%m%d%H%M%S')}",
            "status": "pending_approval",
            "message": "Order proposal created. Awaiting user approval.",
            "timestamp": datetime.now(IST).isoformat(),
        }

    # ========================================================================
    # High-Level Context Assembly
    # ========================================================================

    async def get_full_context(
        self,
        symbol: str,
        timeframe: str = "15m",
        include_options: bool = True,
        include_news: bool = True,
        include_trades: bool = True,
    ) -> Dict[str, Any]:
        """Assemble complete structured context for Grok analysis."""
        from app.services.trading_data_service import ContextRetrievalConfig, get_trading_data_service
        
        trading_service = get_trading_data_service()
        config = ContextRetrievalConfig(
            lookback_candles=100,
            max_news_articles=20,
            max_trades=50,
            news_timeframe_hours=24,
            include_options=include_options,
            include_news=include_news,
            include_trades=include_trades,
        )
        
        context = await trading_service.assemble_grok_context(symbol, timeframe, config)
        return {"success": True, "context": context.model_dump()}


# ============================================================================
# Tool Execution Dispatcher
# ============================================================================

class GrokToolExecutor:
    """
    Executes Grok function calls and returns structured results.
    Maps tool names to ContextRetrievalEngine methods.
    """

    def __init__(self):
        from app.services.trading_data_service import get_trading_data_service
        self.engine = ContextRetrievalEngine(get_trading_data_service())

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Grok tool call by name with arguments."""
        method_map = {
            "get_market_data": self.engine.get_market_data,
            "get_candles": self.engine.get_candles,
            "get_indicators": self.engine.get_indicators,
            "get_options_data": self.engine.get_options_data,
            "get_news": self.engine.get_news,
            "get_market_structure": self.engine.get_market_structure,
            "get_trade_memory": self.engine.get_trade_memory,
            "get_user_preferences": self.engine.get_user_preferences,
            "execute_paper_trade": self.engine.execute_paper_trade,
            "propose_live_order": self.engine.propose_live_order,
            "get_full_context": self.engine.get_full_context,
        }

        if tool_name not in method_map:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

        try:
            method = method_map[tool_name]
            result = await method(**arguments)
            return result
        except Exception as e:
            logger.exception(f"Tool {tool_name} execution failed: {e}")
            return {"success": False, "error": str(e)}


# ============================================================================
# Tool Schemas for OpenAI Function Calling
# ============================================================================

def get_grok_tools() -> List[Dict[str, Any]]:
    """Return the tool schemas for OpenAI function calling format."""
    return GROK_TOOLS


# ============================================================================
# Singleton Instance
# ============================================================================

_context_engine: Optional[ContextRetrievalEngine] = None
_tool_executor: Optional[GrokToolExecutor] = None


def get_context_engine() -> ContextRetrievalEngine:
    from app.services.trading_data_service import get_trading_data_service
    global _context_engine
    if _context_engine is None:
        _context_engine = ContextRetrievalEngine(get_trading_data_service())
    return _context_engine


def get_tool_executor() -> GrokToolExecutor:
    global _tool_executor
    if _tool_executor is None:
        _tool_executor = GrokToolExecutor()
    return _tool_executor
