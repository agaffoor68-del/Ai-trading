"""Indicator service: candle loading + engine orchestration.

The FastAPI layer stays thin; everything reusable (and testable without a web
server) lives here.  Market data always comes from the configured provider
(Fyers REST, with the Redis tick cache untouched) — this module never invents
prices.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.services.indicators import CATEGORIES, REGISTRY, get_engine
from app.services.indicators.engine import IndicatorError

logger = logging.getLogger(__name__)

# Fyers resolutions accepted by the provider.  ``1w``/``1M`` are not in
# market.py's map, so they are resolved here instead of mutating that map.
RESOLUTION_BY_INTERVAL: Dict[str, str] = {
    "1m": "1", "2m": "2", "3m": "3", "5m": "5", "10m": "10", "15m": "15",
    "20m": "20", "30m": "30", "45m": "45", "1h": "60", "60m": "60",
    "2h": "120", "4h": "240", "1d": "1D", "d": "1D", "1wk": "1W", "1w": "1W",
    "1mo": "1M", "1M": "1M",
}

SUPPORTED_INTERVALS: List[str] = ["1m", "3m", "5m", "10m", "15m", "30m", "1h", "2h", "4h", "1d", "1wk", "1mo"]

_SECONDS_PER_DAY = 86400


def normalize_interval(interval: str) -> str:
    key = (interval or "").strip().lower()
    if key in RESOLUTION_BY_INTERVAL:
        return key
    raise ValueError(
        f"Unsupported interval '{interval}'. Use one of: {', '.join(SUPPORTED_INTERVALS)}"
    )


def _days_for(interval: str, limit: int) -> int:
    """How many calendar days of history are needed for ``limit`` candles."""
    per_day = {
        "1m": 375, "2m": 187, "3m": 125, "5m": 75, "10m": 37, "15m": 25,
        "20m": 19, "30m": 12, "45m": 8, "1h": 6, "60m": 6, "2h": 3,
        "4h": 2, "1d": 1, "1wk": 7, "1mo": 30,
    }
    if interval in ("1wk", "1w", "1W"):
        return max(14, int(limit * 7.5))
    if interval in ("1mo", "1M"):
        return max(60, int(limit * 31))
    return max(5, int(limit / per_day.get(interval, 75)) + 2)


async def fetch_candles(symbol: str, interval: str = "5m", limit: int = 300) -> List[dict]:
    """Historical OHLCV from the configured provider, oldest first.

    Returns ``[]`` when the provider has no data (market closed, invalid
    symbol, expired token); callers must surface that as "data unavailable".
    """
    interval = normalize_interval(interval)
    limit = max(20, min(int(limit), 1000))
    resolution = RESOLUTION_BY_INTERVAL[interval]

    from app.core.datetime_utils import now_ist
    from app.core.symbol_map import to_fyers
    from app.services.fyers_api import fyers_api_client

    fyers_symbol = to_fyers(symbol)
    now = int(now_ist().timestamp())
    start = now - _days_for(interval, limit) * _SECONDS_PER_DAY
    try:
        result = await fyers_api_client.get_history(fyers_symbol, resolution, start, now)
    except Exception as exc:  # provider/network failure must not 500 the API
        logger.error("get_history failed for %s: %s", fyers_symbol, exc)
        return []

    if not isinstance(result, dict) or result.get("error") or not result.get("candles"):
        if isinstance(result, dict) and result.get("error"):
            logger.warning("Fyers error for %s: %s", fyers_symbol, result["error"])
        return []

    candles: List[dict] = []
    for row in result["candles"]:
        if len(row) < 5:
            continue
        candles.append(
            {
                "ts": int(row[0]),
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5] if len(row) > 5 else 0,
            }
        )
    candles.sort(key=lambda c: c["ts"])
    return candles[-limit:]


async def fetch_benchmark(symbol: str, interval: str, limit: int) -> Optional[List[dict]]:
    """Optional second series for beta / correlation / pair / cointegration."""
    if not symbol:
        return None
    try:
        candles = await fetch_candles(symbol, interval, limit)
    except ValueError:
        return None
    return candles or None


async def build_extras(
    interval: str,
    limit: int,
    benchmark_symbol: Optional[str] = None,
    with_options: bool = False,
    option_symbol: Optional[str] = None,
) -> Dict[str, Any]:
    """Collect provider data the OHLCV series cannot express."""
    extras: Dict[str, Any] = {}
    if benchmark_symbol:
        candles = await fetch_benchmark(benchmark_symbol, interval, limit)
        if candles:
            extras["benchmark"] = [c["close"] for c in candles]
            extras["benchmark_symbol"] = benchmark_symbol
    if with_options:
        chain = await fetch_option_chain(option_symbol)
        if chain:
            extras["option_chain"] = chain
            extras["spot"] = chain.get("spot")
    return extras


async def fetch_option_chain(symbol: Optional[str] = None) -> Optional[dict]:
    """Option chain in the shape expected by the options indicators.

    Uses the same provider call as the existing option-chain page.  Returns
    ``None`` when no chain is available so indicators report data_unavailable.
    """
    try:
        from app.api.v1.endpoints.options_chain import get_options_chain
    except Exception as exc:  # pragma: no cover - import-time safety
        logger.warning("options chain endpoint unavailable: %s", exc)
        return None
    try:
        payload = await get_options_chain(symbol=symbol, exchange="NSE", limit=50)
    except TypeError:
        try:
            payload = await get_options_chain(symbol=symbol)
        except Exception as exc:
            logger.warning("option chain fetch failed: %s", exc)
            return None
    except Exception as exc:
        logger.warning("option chain fetch failed: %s", exc)
        return None

    if not isinstance(payload, dict):
        return None
    strikes = payload.get("strikes") or payload.get("data") or []
    if not strikes:
        return None
    spot = payload.get("spot") or payload.get("ltp") or payload.get("underlying_value")
    expiry = payload.get("expiry") or payload.get("expiry_date")
    return {"expiry": expiry, "spot": spot, "strikes": strikes, "raw_keys": sorted(payload.keys())}


def list_indicators(
    category: Optional[str] = None,
    query: Optional[str] = None,
    status: Optional[str] = None,
    market: Optional[str] = None,
    timeframe: Optional[str] = None,
    chart: Optional[str] = None,
    repaint: Optional[bool] = None,
    ids: Optional[Iterable[str]] = None,
) -> List[dict]:
    """Filtered registry metadata (JSON-safe, no compute callables)."""
    wanted = set(ids) if ids else None
    needle = (query or "").strip().lower()
    out: List[dict] = []
    for spec in REGISTRY.values():
        if category and spec["category"] != category:
            continue
        if status and spec["status"] != status:
            continue
        if chart and spec["chart"] != chart:
            continue
        if repaint is not None and bool(spec["repaint"]) != repaint:
            continue
        if market and market not in spec["markets"]:
            continue
        if timeframe and timeframe not in spec["timeframes"]:
            continue
        if wanted is not None and spec["id"] not in wanted:
            continue
        if needle and needle not in " ".join(
            [spec["id"], spec["name"], spec["description"], spec["category_label"]]
        ).lower():
            continue
        out.append({k: v for k, v in spec.items() if k != "compute"})
    return sorted(out, key=lambda s: (CATEGORIES[s["category"]]["order"], s["name"].lower()))


def indicator_detail(indicator_id: str) -> dict:
    spec = REGISTRY.get(indicator_id)
    if spec is None:
        raise IndicatorError(f"Unknown indicator id: {indicator_id}")
    detail = {k: v for k, v in spec.items() if k != "compute"}
    detail["examples"] = {
        "chart": spec["chart"],
        "default_params": {p["name"]: p["default"] for p in spec["params"]},
    }
    return detail


def category_summary() -> List[dict]:
    counts: Dict[str, int] = {}
    statuses: Dict[str, Dict[str, int]] = {}
    for spec in REGISTRY.values():
        counts[spec["category"]] = counts.get(spec["category"], 0) + 1
        statuses.setdefault(spec["category"], {})
        statuses[spec["category"]][spec["status"]] = statuses[spec["category"]].get(spec["status"], 0) + 1
    return [
        {
            "id": key,
            "label": meta["label"],
            "order": meta["order"],
            "count": counts.get(key, 0),
            "statuses": statuses.get(key, {}),
        }
        for key, meta in sorted(CATEGORIES.items(), key=lambda kv: kv[1]["order"])
    ]


async def calculate_async(
    symbol: str,
    interval: str,
    indicator_ids: List[str],
    params: Optional[dict] = None,
    limit: int = 300,
    benchmark_symbol: Optional[str] = None,
    with_options: bool = False,
    option_symbol: Optional[str] = None,
) -> dict:
    engine = get_engine()
    candles = await fetch_candles(symbol, interval, limit)
    extras = await build_extras(interval, limit, benchmark_symbol, with_options, option_symbol)
    return assemble(engine, symbol, interval, indicator_ids, params, candles, extras)


def assemble(
    engine,
    symbol: str,
    interval: str,
    indicator_ids: List[str],
    params: Optional[dict],
    candles: List[dict],
    extras: Optional[dict] = None,
    with_options: bool = False,
    option_symbol: Optional[str] = None,
) -> dict:
    """Calculate ``indicator_ids`` over already-fetched candles."""
    if not candles:
        return {
            "symbol": symbol,
            "interval": interval,
            "candles": 0,
            "data_available": False,
            "message": "Data unavailable: the provider returned no candles for this symbol/interval.",
            "results": {},
        }
    prepared_extras = extras or {}
    results = engine.calculate_many(indicator_ids, candles, params, prepared_extras)
    last = candles[-1]
    return {
        "symbol": symbol,
        "interval": interval,
        "candles": len(candles),
        "data_available": True,
        "as_of": last.get("ts"),
        "last_close": last.get("close"),
        "extras_used": sorted(k for k in prepared_extras if k != "raw_keys"),
        "results": results,
    }
