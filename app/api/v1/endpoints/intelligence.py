"""AI market intelligence endpoints.

These surfaces compose the existing engines — multi-timeframe pipeline, regime
detector, strategy playbooks, the 169-indicator panel and the options analyser —
into one explainable read per instrument.  Nothing is fabricated: when a source
is unavailable the block says so and the overall verdict degrades to NO_TRADE.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.core import market_time as mt
from app.core.datetime_utils import now_ist
from app.services.brain import indicator_intelligence as ii
from app.services.brain import multi_timeframe as mtf
from app.services.brain import regime_engine as re

logger = logging.getLogger(__name__)
router = APIRouter(tags=["intelligence"])

SUPPORTED_SYMBOLS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]


def _normalize_symbol(symbol: str) -> str:
    normalized = " ".join(symbol.upper().split())
    if normalized not in SUPPORTED_SYMBOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported symbol '{symbol}'. Use one of: {', '.join(SUPPORTED_SYMBOLS)}",
        )
    return normalized


def _agreement_ratio(snapshot: mtf.MultiTimeframeSnapshot, direction: str) -> Optional[float]:
    """Share of usable timeframes whose bias matches ``direction``."""
    biases = [
        re.timeframe_bias(snapshot.closes(tf))
        for tf in snapshot.sync.usable_timeframes
        if snapshot.closes(tf)
    ]
    if not biases:
        return None
    matching = sum(1 for bias in biases if bias == direction)
    return round(matching / len(biases), 3)


def _expiry_day(snapshot: mtf.MultiTimeframeSnapshot) -> bool:
    """True when today is the weekly index expiry.

    NSE weekly contracts expire on Thursday; when that Thursday is a holiday the
    expiry moves to the previous trading day.  The market calendar is the source
    of truth for holidays, so a shutdown Thursday is not treated as expiry.
    """
    from datetime import timedelta

    from app.core.market_calendar import MarketCalendar

    today = now_ist().date()
    if not MarketCalendar().is_trading_day(today):
        return False
    if today.weekday() == 3:  # Thursday
        return True
    # Friday that follows a Thursday holiday: expiry was pulled back a day.
    if today.weekday() == 4:
        thursday = today - timedelta(days=1)
        return not MarketCalendar().is_trading_day(thursday)
    return False


def _verdict(
    snapshot: mtf.MultiTimeframeSnapshot,
    regime: re.RegimeResult,
    selection: re.StrategySelection,
    indicator_summary: Optional[ii.IndicatorSummary],
    options_bias: Optional[str],
) -> Dict[str, Any]:
    """Combine every block into one decision, refusing when evidence is thin."""
    blockers: List[str] = []

    if not snapshot.usable:
        blockers.append("no usable timeframe (market data unavailable or stale)")

    if regime.low_confidence:
        blockers.append(f"regime confidence {regime.confidence:.0%} below floor")

    if not selection.allowed:
        blockers.append(selection.reason)

    if indicator_summary is not None and indicator_summary.total:
        voters = indicator_summary.bullish + indicator_summary.bearish
        if voters == 0:
            blockers.append("no indicator cast a directional vote")
        elif indicator_summary.agreement < 0.55:
            blockers.append(
                f"indicator agreement {indicator_summary.agreement:.0%} below 55%"
            )

    if blockers:
        return {
            "action": "NO_TRADE",
            "allowed": False,
            "reason": "; ".join(blockers),
            "blockers": blockers,
        }

    direction = "long" if indicator_summary and indicator_summary.net_score > 0 else "short"
    if indicator_summary and indicator_summary.net_score == 0:
        direction = "long" if regime.regime in (re.TREND_UP_STRONG, re.TREND_UP_WEAK, re.BREAKOUT) else "short"

    if options_bias and options_bias != "neutral":
        if options_bias == "bullish" and direction == "short":
            blockers.append("options positioning contradicts the indicator direction")
        if options_bias == "bearish" and direction == "long":
            blockers.append("options positioning contradicts the indicator direction")

    if blockers:
        return {
            "action": "WAIT",
            "allowed": False,
            "reason": "; ".join(blockers),
            "blockers": blockers,
        }

    return {
        "action": "BUY" if direction == "long" else "SELL",
        "allowed": True,
        "direction": direction,
        "reason": selection.reason,
        "blockers": [],
    }


@router.get("/{symbol}")
async def get_intelligence(
    symbol: str,
    timeframe: str = Query("5m", description="Primary decision timeframe"),
    limit: int = Query(300, ge=50, le=1000),
    include_indicators: bool = Query(True, description="Compute the 169-indicator panel"),
    include_options: bool = Query(True, description="Analyse the option chain"),
):
    """Full, explainable market read for one index."""
    normalized = _normalize_symbol(symbol)

    snapshot = await mtf.build_snapshot(normalized, limit=limit)
    if not snapshot.timeframes:
        raise HTTPException(status_code=503, detail="market data unavailable")

    candles_by_tf = {tf: snapshot.candles(tf) for tf in snapshot.timeframes}
    expiry_day = _expiry_day(snapshot)

    regime = re.detect_regime(
        candles_by_tf,
        primary_timeframe=timeframe,
        is_expiry_day=expiry_day,
        reference_close=snapshot.candles(timeframe)[-1]["close"] if snapshot.candles(timeframe) else None,
    )

    bias = "unknown"
    if regime.regime in (re.TREND_UP_STRONG, re.TREND_UP_WEAK, re.BREAKOUT):
        bias = "bullish"
    elif regime.regime in (re.TREND_DOWN_STRONG, re.TREND_DOWN_WEAK, re.BREAKDOWN):
        bias = "bearish"
    agreement = _agreement_ratio(snapshot, bias) if bias != "unknown" else None

    selection = re.select_strategy(regime, mtf_agreement=agreement)

    # --- indicator panel
    indicator_panel = None
    primary_summary: Optional[ii.IndicatorSummary] = None
    if include_indicators and snapshot.candles(timeframe):
        signals, primary_summary = ii.compute_panel(snapshot.candles(timeframe), timeframe)
        confirmation: Dict[str, Any] = {}
        for tf in snapshot.sync.usable_timeframes:
            if tf == timeframe or not snapshot.candles(tf):
                continue
            _, summary = ii.compute_panel(snapshot.candles(tf), tf, ii.MTF_CORE_INDICATORS)
            confirmation[tf] = summary.as_dict()
        indicator_panel = {
            "summary": primary_summary.as_dict(),
            "indicators": [s.as_dict() for s in signals],
            "confirmation": confirmation,
        }

    # --- options
    options_payload: Dict[str, Any] = {"available": False, "message": "not requested"}
    options_bias: Optional[str] = None
    if include_options:
        try:
            from app.api.v1.endpoints.options_chain import fetch_chain_data
            from app.services import options_intelligence

            chain = await fetch_chain_data(normalized, None, 10)
            if chain.get("data_available"):
                analysis = options_intelligence.analyze_chain(
                    symbol=normalized,
                    rows=chain["option_chain"],
                    spot=float(chain["spot_price"]),
                    expiry=datetime.strptime(chain["expiry"], "%Y-%m-%d").date(),
                    atm_strike=chain.get("atm_strike"),
                )
                options_payload = analysis.as_dict(include_chain=False)
                options_payload["expiries"] = chain.get("expiries", [])
                options_bias = analysis.bias
            else:
                options_payload = {
                    "available": False,
                    "message": chain.get("message", "options data unavailable"),
                }
        except HTTPException as error:
            options_payload = {"available": False, "message": str(error.detail)}
        except Exception as error:  # never let options break the market read
            logger.warning("options intelligence failed for %s: %s", normalized, error)
            options_payload = {"available": False, "message": f"options error: {error}"}

    verdict = _verdict(snapshot, regime, selection, primary_summary, options_bias)

    # --- entry levels from real price and measured ATR
    entry_block: Dict[str, Any] = {"available": False}
    primary_candles = snapshot.candles(timeframe)
    if primary_candles and verdict["allowed"]:
        atr_value = ii.extract_value(
            {"series": {"atr": [regime.evidence.atr]}} if regime.evidence.atr else None
        )
        entry = float(primary_candles[-1]["close"])
        levels = re.stop_and_target(
            entry, regime.evidence.atr, selection.strategy, verdict.get("direction", "long")
        )
        size = re.size_position(
            entry=entry,
            atr=regime.evidence.atr,
            spec=selection.strategy,
            equity=0.0,  # equity comes from the risk config; refused until supplied
        )
        entry_block = {
            "available": True,
            "entry": entry,
            **levels,
            "sizing": size.as_dict(),
            "note": (
                "sizing requires the account equity from the risk configuration; "
                "it is not assumed here"
            ),
        }

    return {
        "symbol": normalized,
        "timeframe": timeframe,
        "timestamp": now_ist().isoformat(),
        "market_open": snapshot.market_open,
        "expiry_day": expiry_day,
        "data_quality": mtf.data_quality_report(snapshot),
        "sync": snapshot.sync.as_dict(),
        "regime": regime.as_dict(),
        "multi_timeframe": {
            "agreement": agreement,
            "bias": bias,
            "per_timeframe": {
                tf: {
                    "bias": re.timeframe_bias(snapshot.closes(tf)),
                    "last_close": snapshot.timeframes[tf].last_close,
                    "status": snapshot.timeframes[tf].quality.status,
                    "candles": snapshot.timeframes[tf].quality.candles,
                }
                for tf in snapshot.timeframes
            },
        },
        "strategy": selection.as_dict(),
        "indicators": indicator_panel,
        "options": options_payload,
        "verdict": verdict,
        "entry_plan": entry_block,
    }


@router.get("/{symbol}/data-quality")
async def get_data_quality(
    symbol: str,
    limit: int = Query(300, ge=50, le=1000),
):
    """Synchronisation and freshness report across every timeframe."""
    normalized = _normalize_symbol(symbol)
    snapshot = await mtf.build_snapshot(normalized, limit=limit)
    return mtf.data_quality_report(snapshot)


@router.get("/{symbol}/indicators")
async def get_indicator_panel(
    symbol: str,
    timeframe: str = Query("5m"),
    category: Optional[str] = Query(None, description="Filter by category id"),
    direction: Optional[str] = Query(None, description="bullish | bearish | neutral | unavailable"),
    limit: int = Query(300, ge=50, le=1000),
):
    """Every registered indicator with value, direction, strength and status."""
    normalized = _normalize_symbol(symbol)
    snapshot = await mtf.build_snapshot(
        normalized, timeframes=[timeframe], limit=limit
    )
    candles = snapshot.candles(timeframe)
    if not candles:
        item = snapshot.timeframes.get(timeframe)
        raise HTTPException(
            status_code=503,
            detail={
                "message": "market data unavailable for this timeframe",
                "reason": item.quality.reason if item else "no data",
            },
        )

    signals, summary = ii.compute_panel(candles, timeframe)
    rows = [s.as_dict() for s in signals]
    if category:
        rows = [r for r in rows if r["category"] == category]
    if direction:
        rows = [r for r in rows if r["direction"] == direction]

    return {
        "symbol": normalized,
        "timeframe": timeframe,
        "timestamp": now_ist().isoformat(),
        "summary": summary.as_dict(),
        "total": len(rows),
        "library_total": len(signals),
        "indicators": rows,
    }


@router.get("")
async def get_market_overview(
    limit: int = Query(200, ge=50, le=1000),
    include_options: bool = Query(False),
):
    """Compact read for every supported index (dashboard overview cards)."""
    results: List[Dict[str, Any]] = []
    for symbol in SUPPORTED_SYMBOLS:
        try:
            payload = await get_intelligence(
                symbol,
                timeframe="5m",
                limit=limit,
                include_indicators=False,
                include_options=include_options,
            )
            results.append(
                {
                    "symbol": symbol,
                    "available": True,
                    "market_open": payload["market_open"],
                    "regime": payload["regime"]["regime"],
                    "regime_label": payload["regime"]["label"],
                    "regime_confidence": payload["regime"]["confidence"],
                    "bias": payload["multi_timeframe"]["bias"],
                    "agreement": payload["multi_timeframe"]["agreement"],
                    "action": payload["verdict"]["action"],
                    "allowed": payload["verdict"]["allowed"],
                    "reason": payload["verdict"]["reason"],
                    "strategy": payload["strategy"]["strategy"]["name"],
                    "last_close": (
                        payload["multi_timeframe"]["per_timeframe"].get("5m", {}).get("last_close")
                    ),
                    "sync_aligned": payload["sync"]["aligned"],
                    "skew_seconds": payload["sync"]["skew_seconds"],
                    "timestamp": payload["timestamp"],
                }
            )
        except HTTPException as error:
            results.append(
                {
                    "symbol": symbol,
                    "available": False,
                    "reason": str(error.detail),
                }
            )
        except Exception as error:
            logger.exception("overview failed for %s", symbol)
            results.append({"symbol": symbol, "available": False, "reason": str(error)})
    return {"count": len(results), "instruments": results}
