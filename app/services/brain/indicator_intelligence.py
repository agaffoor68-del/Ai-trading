"""Indicator intelligence: turn raw indicator output into graded evidence.

The engine computes 169 series.  This module decides, per indicator, whether it
reads **bullish**, **bearish** or **neutral**, how strong that read is, and which
rule produced it — so the dashboard can explain every contribution instead of
showing a bare number.

Two rules keep it honest:

* an indicator with no usable value is reported ``unavailable`` with the engine's
  own reason, never silently dropped and never defaulted to neutral-with-a-number;
* a rule that does not exist for an id falls back to a documented, generic
  category rule, and the response says ``rule="generic"`` so the user knows the
  reading is a heuristic rather than a tuned interpretation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from app.services.indicators import REGISTRY, get_engine

logger = logging.getLogger(__name__)

BULLISH = "bullish"
BEARISH = "bearish"
NEUTRAL = "neutral"
UNAVAILABLE = "unavailable"

# Indicators worth computing on the confirmation timeframes.  Computing all 169
# on seven timeframes per symbol per minute would be wasteful; this subset is
# what multi-timeframe confluence actually consumes.
MTF_CORE_INDICATORS: Tuple[str, ...] = (
    "ema", "sma", "supertrend", "adx", "rsi", "macd", "atr",
    "bollinger", "donchian", "vwap", "obv", "stochrsi",
)

# Indicator ids whose "value" is a price-like level to compare with close.
_PRICE_LEVEL_IDS = frozenset(
    {
        "ema", "sma", "wma", "vwma", "dema", "tema", "hma", "kama", "alma",
        "zlema", "t3", "mcginley", "vwap", "anchored_vwap", "supertrend",
        "parabolic_sar", "ichimoku", "bollinger", "keltner", "donchian",
        "vwap_bands", "ma_ribbon",
    }
)

# Oscillators bounded 0..100 where extremes mean reversion.
_BOUNDED_OSCILLATORS = frozenset(
    {"rsi", "stochrsi", "stoch", "mfi", "ultimate_oscillator", "connors_rsi", "tsi_rsi"}
)

# Momentum ids where sign alone is the read.
_SIGN_MOMENTUM = frozenset(
    {
        "macd", "roc", "momentum", "trix", "ppo", "tsi", "awesome_oscillator",
        "cmf", "chaikin_oscillator", "force_index", "obv", "volume_weighted_macd",
        "relative_volume", "accumulation_distribution", "ease_of_movement",
    }
)

# Bounded oscillators where a high reading is *bearish* (overbought) and a low
# reading is bullish.  Williams %R runs -100..0, so it is inverted.
_INVERTED_OSCILLATORS = frozenset({"williams_r"})


@dataclass
class IndicatorSignal:
    """One indicator's graded contribution."""

    id: str
    name: str
    category: str
    timeframe: str
    value: Optional[float]
    direction: str
    strength: float  # 0..1
    rule: str  # specific | generic | threshold | none
    note: str
    status: str  # ok | unavailable | insufficient_data
    contributes: bool = False
    repaint: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "timeframe": self.timeframe,
            "value": None if self.value is None else round(self.value, 4),
            "direction": self.direction,
            "strength": round(self.strength, 3),
            "rule": self.rule,
            "note": self.note,
            "status": self.status,
            "contributes": self.contributes,
            "repaint": self.repaint,
        }


# ---------------------------------------------------------------------------
# Value extraction
# ---------------------------------------------------------------------------
def extract_value(result: Optional[Dict[str, Any]]) -> Optional[float]:
    """Newest numeric value from an engine result of any shape."""
    if not isinstance(result, dict):
        return None
    series = result.get("series")
    values: List[Any] = []
    if isinstance(series, dict):
        for item in series.values():
            if isinstance(item, (list, tuple)):
                values.extend(item)
            elif isinstance(item, (int, float)) and not isinstance(item, bool):
                values.append(item)
    elif isinstance(series, (list, tuple)):
        values.extend(series)
    for value in reversed(values):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    meta = result.get("meta") or {}
    if isinstance(meta, dict):
        for value in reversed(list(meta.values())):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    return None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _distance_strength(value: float, reference: float, scale: float) -> float:
    """How far ``value`` sits from ``reference`` relative to ``scale``."""
    if scale <= 0:
        return 0.0
    return _clamp(abs(value - reference) / scale)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------
Context = Dict[str, Any]


def _rule_price_level(value: float, ctx: Context) -> Tuple[str, float, str]:
    close = ctx.get("close")
    if close is None or close <= 0:
        return NEUTRAL, 0.0, "close unavailable for comparison"
    atr = ctx.get("atr")
    scale = atr if atr and atr > 0 else close * 0.005
    gap = close - value
    direction = BULLISH if gap > 0 else BEARISH if gap < 0 else NEUTRAL
    strength = _distance_strength(close, value, scale * 2)
    position = "above" if gap > 0 else "below"
    return direction, strength, f"close {close:.2f} is {position} the level {value:.2f}"


def _rule_bounded_oscillator(value: float, ctx: Context) -> Tuple[str, float, str]:
    if value >= 70:
        return BEARISH, _clamp((value - 70) / 30), f"{value:.1f} is overbought (>=70)"
    if value <= 30:
        return BULLISH, _clamp((30 - value) / 30), f"{value:.1f} is oversold (<=30)"
    return NEUTRAL, 0.0, f"{value:.1f} is mid-range"


def _rule_williams(value: float, ctx: Context) -> Tuple[str, float, str]:
    # -100..0; near -100 is oversold (bullish), near 0 is overbought (bearish).
    if value <= -80:
        return BULLISH, _clamp((-80 - value) / 20), f"{value:.1f} is oversold (<=-80)"
    if value >= -20:
        return BEARISH, _clamp((value + 20) / 20), f"{value:.1f} is overbought (>=-20)"
    return NEUTRAL, 0.0, f"{value:.1f} is mid-range"


def _rule_cci(value: float, ctx: Context) -> Tuple[str, float, str]:
    if value >= 100:
        return BULLISH, _clamp((value - 100) / 100), f"{value:.1f} above +100"
    if value <= -100:
        return BEARISH, _clamp((-100 - value) / 100), f"{value:.1f} below -100"
    return NEUTRAL, 0.0, f"{value:.1f} inside the +/-100 band"


def _rule_sign(value: float, ctx: Context) -> Tuple[str, float, str]:
    reference = ctx.get("atr") or abs(value) or 1.0
    if value > 0:
        return BULLISH, _distance_strength(value, 0.0, reference * 2), f"positive ({value:.3f})"
    if value < 0:
        return BEARISH, _distance_strength(value, 0.0, reference * 2), f"negative ({value:.3f})"
    return NEUTRAL, 0.0, "at zero"


def _rule_adx(value: float, ctx: Context) -> Tuple[str, float, str]:
    """ADX measures strength, not direction — it never votes on direction."""
    if value >= 25:
        return NEUTRAL, _clamp((value - 25) / 25), f"strong trend ({value:.1f}) — strength only"
    if value < 15:
        return NEUTRAL, _clamp((15 - value) / 15), f"weak/no trend ({value:.1f}) — strength only"
    return NEUTRAL, 0.0, f"developing trend ({value:.1f}) — strength only"


def _rule_aroon(value: float, ctx: Context) -> Tuple[str, float, str]:
    if value >= 70:
        return BULLISH, _clamp((value - 70) / 30), f"{value:.1f} shows a strong up-swing"
    if value <= 30:
        return BEARISH, _clamp((30 - value) / 30), f"{value:.1f} shows a strong down-swing"
    return NEUTRAL, 0.0, f"{value:.1f} is inconclusive"


def _rule_mfi(value: float, ctx: Context) -> Tuple[str, float, str]:
    if value >= 80:
        return BEARISH, _clamp((value - 80) / 20), f"{value:.1f} overbought (>=80)"
    if value <= 20:
        return BULLISH, _clamp((20 - value) / 20), f"{value:.1f} oversold (<=20)"
    return NEUTRAL, 0.0, f"{value:.1f} is mid-range"


SPECIFIC_RULES: Dict[str, Callable[[float, Context], Tuple[str, float, str]]] = {
    "adx": _rule_adx,
    "cci": _rule_cci,
    "williams_r": _rule_williams,
    "mfi": _rule_mfi,
    "aroon": _rule_aroon,
    "ultimate_oscillator": _rule_bounded_oscillator,
    "connors_rsi": _rule_bounded_oscillator,
    "stoch": _rule_bounded_oscillator,
}


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
def classify(
    indicator_id: str,
    result: Optional[Dict[str, Any]],
    timeframe: str,
    context: Optional[Context] = None,
    spec: Optional[Dict[str, Any]] = None,
) -> IndicatorSignal:
    """Grade one indicator result into a signal."""
    ctx: Context = dict(context or {})
    entry = spec or REGISTRY.get(indicator_id) or {}
    name = entry.get("name", indicator_id)
    category = entry.get("category", "unknown")
    repaint = bool(entry.get("repaint"))

    status = (result or {}).get("status") if isinstance(result, dict) else None
    value = extract_value(result)

    if value is None:
        note = "no numeric value produced"
        if isinstance(result, dict):
            note = result.get("note") or status or note
        return IndicatorSignal(
            id=indicator_id, name=name, category=category, timeframe=timeframe,
            value=None, direction=UNAVAILABLE, strength=0.0, rule="none",
            note=note, status=status or "unavailable", repaint=repaint,
        )

    # 1. explicit rule for this id
    rule = SPECIFIC_RULES.get(indicator_id)
    if rule is not None:
        direction, strength, note = rule(value, ctx)
        return IndicatorSignal(
            id=indicator_id, name=name, category=category, timeframe=timeframe,
            value=value, direction=direction, strength=strength, rule="specific",
            note=note, status="ok", contributes=direction != NEUTRAL, repaint=repaint,
        )

    # 2. bounded oscillator threshold
    if indicator_id in _BOUNDED_OSCILLATORS:
        direction, strength, note = _rule_bounded_oscillator(value, ctx)
        return IndicatorSignal(
            id=indicator_id, name=name, category=category, timeframe=timeframe,
            value=value, direction=direction, strength=strength, rule="threshold",
            note=note, status="ok", contributes=direction != NEUTRAL, repaint=repaint,
        )

    # 3. price-level comparison
    if indicator_id in _PRICE_LEVEL_IDS or category in ("trend", "levels"):
        direction, strength, note = _rule_price_level(value, ctx)
        return IndicatorSignal(
            id=indicator_id, name=name, category=category, timeframe=timeframe,
            value=value, direction=direction, strength=strength,
            rule="specific" if indicator_id in _PRICE_LEVEL_IDS else "generic",
            note=note, status="ok", contributes=direction != NEUTRAL, repaint=repaint,
        )

    # 4. sign of a momentum/volume measure
    if indicator_id in _SIGN_MOMENTUM or category in ("momentum", "volume"):
        direction, strength, note = _rule_sign(value, ctx)
        return IndicatorSignal(
            id=indicator_id, name=name, category=category, timeframe=timeframe,
            value=value, direction=direction, strength=strength,
            rule="specific" if indicator_id in _SIGN_MOMENTUM else "generic",
            note=note, status="ok", contributes=direction != NEUTRAL, repaint=repaint,
        )

    # 5. volatility / options / statistics: reported, not directional
    return IndicatorSignal(
        id=indicator_id, name=name, category=category, timeframe=timeframe,
        value=value, direction=NEUTRAL, strength=0.0, rule="none",
        note=f"{category} indicator — descriptive, no directional vote",
        status="ok", contributes=False, repaint=repaint,
    )


@dataclass
class IndicatorSummary:
    """Aggregate of one timeframe's indicator panel."""

    timeframe: str
    total: int = 0
    bullish: int = 0
    bearish: int = 0
    neutral: int = 0
    unavailable: int = 0
    agreement: float = 0.0  # 0..1, share of voters that agree with the majority
    net_score: float = 0.0  # strength-weighted, -1..1
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    by_category: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "timeframe": self.timeframe,
            "total": self.total,
            "bullish": self.bullish,
            "bearish": self.bearish,
            "neutral": self.neutral,
            "unavailable": self.unavailable,
            "agreement": round(self.agreement, 3),
            "net_score": round(self.net_score, 3),
            "conflicts": self.conflicts,
            "by_category": self.by_category,
        }


def summarize(signals: Sequence[IndicatorSignal], timeframe: str) -> IndicatorSummary:
    """Count, weigh and de-duplicate the panel's evidence."""
    summary = IndicatorSummary(timeframe=timeframe, total=len(signals))
    if not signals:
        return summary

    weighted_bull = 0.0
    weighted_bear = 0.0

    for signal in signals:
        bucket = summary.by_category.setdefault(
            signal.category, {"bullish": 0, "bearish": 0, "neutral": 0, "unavailable": 0}
        )
        if signal.direction == BULLISH:
            summary.bullish += 1
            bucket["bullish"] += 1
            weighted_bull += max(signal.strength, 0.15)
        elif signal.direction == BEARISH:
            summary.bearish += 1
            bucket["bearish"] += 1
            weighted_bear += max(signal.strength, 0.15)
        elif signal.direction == UNAVAILABLE:
            summary.unavailable += 1
            bucket["unavailable"] += 1
        else:
            summary.neutral += 1
            bucket["neutral"] += 1

    voters = summary.bullish + summary.bearish
    if voters:
        majority = max(summary.bullish, summary.bearish)
        summary.agreement = majority / voters

    total_weight = weighted_bull + weighted_bear
    if total_weight > 0:
        summary.net_score = (weighted_bull - weighted_bear) / total_weight

    # Conflicts: opposing reads inside the same category are the ones that
    # actually matter for a decision.
    for category, counts in summary.by_category.items():
        if counts["bullish"] and counts["bearish"]:
            summary.conflicts.append(
                {
                    "category": category,
                    "bullish": counts["bullish"],
                    "bearish": counts["bearish"],
                    "note": f"{category} indicators disagree",
                }
            )

    return summary


def compute_panel(
    candles: Sequence[Dict[str, Any]],
    timeframe: str,
    indicator_ids: Optional[Iterable[str]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Tuple[List[IndicatorSignal], IndicatorSummary]:
    """Compute and grade a panel of indicators over real candles."""
    ids = list(indicator_ids or REGISTRY.keys())
    engine = get_engine()

    try:
        results = engine.calculate_many(ids, list(candles), params or None)
    except Exception as error:  # never let one bad series kill the panel
        logger.warning("indicator panel calculation failed: %s", error)
        results = {}

    context: Context = {}
    if candles:
        closes = [float(c["close"]) for c in candles]
        context["close"] = closes[-1]
        if len(closes) > 1 and closes[-2]:
            context["prev_close"] = closes[-2]
        atr_value = extract_value(results.get("atr"))
        if atr_value:
            context["atr"] = atr_value

    signals = [
        classify(indicator_id, results.get(indicator_id), timeframe, context)
        for indicator_id in ids
    ]
    return signals, summarize(signals, timeframe)


def build_mtf_panel(
    candles_by_timeframe: Dict[str, Sequence[Dict[str, Any]]],
    primary_timeframe: str,
    primary_ids: Optional[Iterable[str]] = None,
    confirmation_ids: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Full 169-indicator panel on the primary TF, core panel on the rest."""
    payload: Dict[str, Any] = {"primary": None, "confirmation": {}}

    primary_candles = candles_by_timeframe.get(primary_timeframe) or []
    if primary_candles:
        signals, summary = compute_panel(primary_candles, primary_timeframe, primary_ids)
        payload["primary"] = {
            "summary": summary.as_dict(),
            "indicators": [s.as_dict() for s in signals],
        }

    for timeframe, candles in candles_by_timeframe.items():
        if timeframe == primary_timeframe or not candles:
            continue
        signals, summary = compute_panel(
            candles, timeframe, confirmation_ids or MTF_CORE_INDICATORS
        )
        payload["confirmation"][timeframe] = {
            "summary": summary.as_dict(),
            "indicators": [s.as_dict() for s in signals],
        }

    return payload


__all__ = [
    "BEARISH",
    "BULLISH",
    "IndicatorSignal",
    "IndicatorSummary",
    "MTF_CORE_INDICATORS",
    "NEUTRAL",
    "UNAVAILABLE",
    "build_mtf_panel",
    "classify",
    "compute_panel",
    "extract_value",
    "summarize",
]
