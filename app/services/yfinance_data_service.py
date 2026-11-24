"""
Real Yahoo Finance data service.

Reads live/historical OHLCV directly from Yahoo Finance's chart API
(https://query1.finance.yahoo.com/v8/finance/chart/{symbol}) -- this is the
exact endpoint the `yfinance` Python package queries under the hood. Using it
directly avoids the `yfinance`/`pandas`/`numpy` dependency stack (which is not
installable on this Android/Python-3.14 environment) while still returning
100% real Yahoo data -- no random/synthetic data anywhere.

All timestamps are converted to IST (Asia/Kolkata).
"""

import json
import logging
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import List, Optional

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

# Mapping of user-friendly Indian symbols to Yahoo Finance tickers.
# Indices use Yahoo's ^-prefixed tickers; equities use the .NS (NSE) suffix.
YAHOO_SYMBOL_MAP = {
    "NIFTY 50": "^NSEI",
    "NIFTY50": "^NSEI",
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "BANK NIFTY": "^NSEBANK",
    "NIFTY BANK": "^NSEBANK",
    "FINNIFTY": "^NSEFIN",
    "FIN NIFTY": "^NSEFIN",
    "MIDCPNIFTY": "^NSEMDCP50",
    "MIDCAP NIFTY": "^NSEMDCP50",
    "SENSEX": "^BSESN",
    "BSE SENSEX": "^BSESN",
}

# Yahoo chart interval -> allowed lookback range. Yahoo restricts intraday
# granularity to recent windows; we pick a valid range per interval so requests
# never return empty due to an out-of-window interval/range combo.
INTERVAL_DEFAULT_RANGE = {
    "1m": "7d",
    "2m": "60d",
    "5m": "60d",
    "15m": "60d",
    "30m": "60d",
    "60m": "730d",
    "90m": "730d",
    "1h": "730d",
    "1d": "max",
    "1wk": "max",
    "1mo": "max",
}


def to_yahoo_symbol(symbol: str) -> str:
    """Convert a user-friendly symbol to a Yahoo Finance ticker."""
    key = symbol.strip().upper()
    if key in YAHOO_SYMBOL_MAP:
        return YAHOO_SYMBOL_MAP[key]
    if "^" in key or "." in key or "-" in key:
        return key
    # Equity on NSE by default.
    return f"{key}.NS"


def _fetch_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _unix_to_ist(ts: int) -> str:
    dt = datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(IST)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def fetch_ohlcv(
    symbol: str,
    interval: str = "1d",
    range_: Optional[str] = None,
) -> List[dict]:
    """
    Fetch real OHLCV candles from Yahoo Finance.

    Args:
        symbol: User-friendly symbol (e.g. "RELIANCE", "NIFTY 50", "^NSEI").
        interval: Candle interval ("1m", "5m", "15m", "1h", "1d", ...).
        range_: Lookback range ("1d", "5d", "1mo", "max", ...). Defaults per
            interval per Yahoo's constraints.

    Returns:
        List of dicts: {time, open, high, low, close, volume, datetime_ist}.
        Empty list on failure (logged, never raises).
    """
    yahoo_symbol = to_yahoo_symbol(symbol)
    rng = range_ or INTERVAL_DEFAULT_RANGE.get(interval, "max")
    url = YAHOO_BASE + "/" + yahoo_symbol + "?range=" + rng + "&interval=" + interval

    try:
        data = _fetch_json(url)
    except Exception as exc:
        logger.error("Yahoo Finance fetch failed for %s (%s): %s", symbol, url, exc)
        return []

    try:
        result = data["chart"]["result"][0]
    except (KeyError, IndexError, TypeError):
        logger.error("Yahoo Finance returned no result for %s", symbol)
        return []

    meta = result.get("meta", {}) or {}
    timestamps = result.get("timestamp") or []
    quotes = (result.get("indicators") or {}).get("quote") or [{}]
    quote = quotes[0]

    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    n = min(len(timestamps), len(opens), len(highs), len(lows), len(closes))
    candles: List[dict] = []
    for i in range(n):
        close = closes[i]
        if close is None:
            continue
        ts = int(timestamps[i])
        candles.append(
            {
                "time": ts,
                "datetime_ist": _unix_to_ist(ts),
                "open": float(opens[i]) if opens[i] is not None else None,
                "high": float(highs[i]) if highs[i] is not None else None,
                "low": float(lows[i]) if lows[i] is not None else None,
                "close": float(close),
                "volume": float(volumes[i]) if i < len(volumes) and volumes[i] is not None else 0.0,
            }
        )

    logger.info("Yahoo Finance: %s (%s) -> %d candles", yahoo_symbol, interval, len(candles))
    return candles


def fetch_latest(symbol: str) -> Optional[dict]:
    """Fetch the most recent candle for a symbol (1-day interval)."""
    candles = fetch_ohlcv(symbol, interval="1d", range_="5d")
    return candles[-1] if candles else None
