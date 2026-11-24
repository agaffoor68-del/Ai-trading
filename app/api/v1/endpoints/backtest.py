"""
Backtest endpoints.

Runs strategy backtests on REAL Yahoo Finance data (no random/synthetic data).
Each trade includes entry time, exit time, entry price, exit price, and PnL.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from asyncio import to_thread as run_in_threadpool

from app.services.backtest_engine import run_backtest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["backtest"])


class BacktestRequest(BaseModel):
    symbol: str = "RELIANCE"
    strategy: str = "Supertrend + RSI"
    interval: str = "15m"
    range: str = "60d"
    initial_capital: float = 100000.0
    quantity: int = 1
    sl_pct: float = 0.5
    target_pct: float = 1.0


class BacktestResponse(BaseModel):
    symbol: str
    yahoo_symbol: str
    strategy: str
    interval: str
    range: str
    initial_capital: float
    final_capital: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    max_drawdown: float
    data_source: str
    candles_used: int
    equity_curve: list
    trades: list


@router.post("/backtest/run", response_model=BacktestResponse)
async def run_backtest_endpoint(req: BacktestRequest):
    """
    Run a backtest on real Yahoo Finance data.

    Returns trades with entry_time, exit_time, entry_price, exit_price, side, pnl.
    """
    try:
        result = await run_in_threadpool(
            run_backtest,
            symbol=req.symbol,
            strategy=req.strategy,
            interval=req.interval,
            range_=req.range,
            initial_capital=req.initial_capital,
            quantity=req.quantity,
            sl_pct=req.sl_pct,
            target_pct=req.target_pct,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Backtest error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(exc)}")


@router.get("/backtest/run")
async def run_backtest_get(
    symbol: str = "RELIANCE",
    strategy: str = "Supertrend + RSI",
    interval: str = "15m",
    range: str = "60d",
    initial_capital: float = 100000.0,
    quantity: int = 1,
    sl_pct: float = 0.5,
    target_pct: float = 1.0,
):
    """GET variant for simple URL-based backtest requests."""
    req = BacktestRequest(
        symbol=symbol,
        strategy=strategy,
        interval=interval,
        range=range,
        initial_capital=initial_capital,
        quantity=quantity,
        sl_pct=sl_pct,
        target_pct=target_pct,
    )
    return await run_backtest_endpoint(req)
