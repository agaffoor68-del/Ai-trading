"""
Backtest engine using real Yahoo Finance data.

No random/synthetic data is used -- every candle comes from Yahoo Finance
(via app.services.yfinance_data_service). Each trade records entry time,
exit time, entry price, exit price, and PnL so the UI can show exactly
when each trade was entered and exited.

All times are IST (Asia/Kolkata).
"""

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import List, Optional, Dict, Any

from app.services.yfinance_data_service import fetch_ohlcv, to_yahoo_symbol

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


def _ist(ts: int) -> str:
    dt = datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(IST)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _compute_supertrend(candles: List[dict], length: int = 10, multiplier: float = 3.0) -> List[Optional[float]]:
    n = len(candles)
    if n < length + 1:
        return [None] * n

    tr = [0.0] * n
    for i in range(1, n):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i - 1]["close"]
        tr[i] = max(high - low, abs(high - prev_close), abs(low - prev_close))

    atr = [0.0] * n
    for i in range(length, n):
        atr[i] = sum(tr[i - length + 1:i + 1]) / length

    upper = [0.0] * n
    lower = [0.0] * n
    for i in range(n):
        hl2 = (candles[i]["high"] + candles[i]["low"]) / 2.0
        atr_val = atr[i] if atr[i] and atr[i] > 0 else 0.0
        upper[i] = hl2 + multiplier * atr_val
        lower[i] = hl2 - multiplier * atr_val

    final_upper = [0.0] * n
    final_lower = [0.0] * n
    for i in range(n):
        if i == 0:
            final_upper[i] = upper[i]
            final_lower[i] = lower[i]
        else:
            final_upper[i] = upper[i] if (upper[i] < final_upper[i - 1] or candles[i - 1]["close"] > final_upper[i - 1]) else final_upper[i - 1]
            final_lower[i] = lower[i] if (lower[i] > final_lower[i - 1] or candles[i - 1]["close"] < final_lower[i - 1]) else final_lower[i - 1]

    st = [None] * n
    for i in range(n):
        if i == 0:
            st[i] = final_lower[i]
        else:
            prev_st = st[i - 1]
            if prev_st == final_upper[i - 1]:
                if candles[i]["close"] <= final_upper[i]:
                    st[i] = final_upper[i]
                else:
                    st[i] = final_lower[i]
            else:
                if candles[i]["close"] >= final_lower[i]:
                    st[i] = final_lower[i]
                else:
                    st[i] = final_upper[i]
    return st


def _compute_rsi(candles: List[dict], length: int = 14) -> List[Optional[float]]:
    n = len(candles)
    if n <= length:
        return [None] * n

    rsi = [None] * n
    gains = [0.0] * n
    losses = [0.0] * n

    for i in range(1, n):
        change = candles[i]["close"] - candles[i - 1]["close"]
        if change > 0:
            gains[i] = change
        else:
            losses[i] = -change

    avg_gain = sum(gains[1:length + 1]) / length
    avg_loss = sum(losses[1:length + 1]) / length

    for i in range(length + 1, n):
        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))
        avg_gain = (avg_gain * (length - 1) + gains[i]) / length
        avg_loss = (avg_loss * (length - 1) + losses[i]) / length

    if avg_loss == 0:
        rsi[length] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[length] = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def run_backtest(
    symbol: str,
    strategy: str = "Supertrend + RSI",
    interval: str = "15m",
    range_: str = "60d",
    initial_capital: float = 100000.0,
    quantity: int = 1,
    sl_pct: float = 0.5,
    target_pct: float = 1.0,
) -> Dict[str, Any]:
    candles = fetch_ohlcv(symbol, interval=interval, range_=range_)
    if not candles or len(candles) < 30:
        return {
            "symbol": symbol,
            "strategy": strategy,
            "interval": interval,
            "range": range_,
            "error": "Insufficient real data from Yahoo Finance",
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
            "initial_capital": initial_capital,
            "equity_curve": [],
            "trades": [],
            "data_source": "Yahoo Finance (real)",
        }

    yahoo_symbol = to_yahoo_symbol(symbol)
    n = len(candles)

    supertrend = _compute_supertrend(candles)
    rsi = _compute_rsi(candles)

    trades: List[dict] = []
    equity_curve: List[dict] = []
    capital = initial_capital
    peak = initial_capital
    max_drawdown = 0.0

    position: Optional[dict] = None

    for i in range(n):
        close = candles[i]["close"]
        high = candles[i]["high"]
        low = candles[i]["low"]
        st = supertrend[i]
        rsi_val = rsi[i]

        if st is None or rsi_val is None:
            equity_curve.append({"time": candles[i]["time"], "datetime_ist": candles[i]["datetime_ist"], "equity": capital})
            continue

        if position is not None:
            entry_price = position["entry_price"]
            side = position["side"]
            sl = entry_price * (1 - sl_pct / 100.0) if side == "BUY" else entry_price * (1 + sl_pct / 100.0)
            target = entry_price * (1 + target_pct / 100.0) if side == "BUY" else entry_price * (1 - target_pct / 100.0)

            exit_triggered = False
            exit_reason = ""
            exit_price = close
            if side == "BUY":
                if low <= sl:
                    exit_triggered = True
                    exit_reason = "SL"
                    exit_price = sl
                elif high >= target:
                    exit_triggered = True
                    exit_reason = "TARGET"
                    exit_price = target
                elif st is not None and i > 0 and supertrend[i - 1] is not None and close < st:
                    exit_triggered = True
                    exit_reason = "STREND_FLIP"
                    exit_price = close
            else:
                if high >= sl:
                    exit_triggered = True
                    exit_reason = "SL"
                    exit_price = sl
                elif low <= target:
                    exit_triggered = True
                    exit_reason = "TARGET"
                    exit_price = target
                elif st is not None and i > 0 and supertrend[i - 1] is not None and close > st:
                    exit_triggered = True
                    exit_reason = "STREND_FLIP"
                    exit_price = close

            if exit_triggered:
                pnl = (exit_price - entry_price) * quantity if side == "BUY" else (entry_price - exit_price) * quantity
                pnl_pct = (pnl / (entry_price * quantity)) * 100.0
                capital += pnl
                if capital > peak:
                    peak = capital
                dd = peak - capital
                if dd > max_drawdown:
                    max_drawdown = dd

                trades.append({
                    "entry_time": position["entry_time"],
                    "exit_time": candles[i]["datetime_ist"],
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "side": side,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "exit_reason": exit_reason,
                })
                position = None

        if position is None:
            bullish = close > st
            bearish = close < st

            if strategy == "Supertrend + RSI":
                if bullish and rsi_val < 60:
                    position = {"side": "BUY", "entry_idx": i, "entry_price": close, "entry_time": candles[i]["datetime_ist"]}
                elif bearish and rsi_val > 40:
                    position = {"side": "SELL", "entry_idx": i, "entry_price": close, "entry_time": candles[i]["datetime_ist"]}
            elif strategy == "VWAP Bounce":
                if bullish:
                    position = {"side": "BUY", "entry_idx": i, "entry_price": close, "entry_time": candles[i]["datetime_ist"]}
                elif bearish:
                    position = {"side": "SELL", "entry_idx": i, "entry_price": close, "entry_time": candles[i]["datetime_ist"]}

        equity_curve.append({
            "time": candles[i]["time"],
            "datetime_ist": candles[i]["datetime_ist"],
            "equity": round(capital, 2),
        })

    if position is not None:
        entry_price = position["entry_price"]
        side = position["side"]
        close = candles[-1]["close"]
        pnl = (close - entry_price) * quantity if side == "BUY" else (entry_price - close) * quantity
        pnl_pct = (pnl / (entry_price * quantity)) * 100.0
        capital += pnl
        trades.append({
            "entry_time": position["entry_time"],
            "exit_time": candles[-1]["datetime_ist"],
            "entry_price": round(entry_price, 2),
            "exit_price": round(close, 2),
            "side": side,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "exit_reason": "END_OF_DATA",
        })

    winning = sum(1 for t in trades if t["pnl"] > 0)
    losing = sum(1 for t in trades if t["pnl"] < 0)
    total_pnl = sum(t["pnl"] for t in trades)
    win_rate = (winning / len(trades) * 100.0) if trades else 0.0

    return {
        "symbol": symbol,
        "yahoo_symbol": yahoo_symbol,
        "strategy": strategy,
        "interval": interval,
        "range": range_,
        "initial_capital": initial_capital,
        "final_capital": round(capital, 2),
        "total_trades": len(trades),
        "winning_trades": winning,
        "losing_trades": losing,
        "win_rate": round(win_rate, 2),
        "total_pnl": round(total_pnl, 2),
        "max_drawdown": round(max_drawdown, 2),
        "data_source": "Yahoo Finance (real)",
        "candles_used": n,
        "equity_curve": equity_curve,
        "trades": trades,
    }
