"""Regime-adaptive strategy engine (Task 2).

The engine answers two questions, in this order, before any signal exists:

1. **What market condition is this?**  ``detect_regime`` classifies the current
   multi-timeframe snapshot into one of the supported regimes using measured
   evidence (ADX, ATR%, Bollinger width, EMA slope, Donchian position) — never a
   guess and never a hardcoded label.
2. **Which strategy is allowed here, and at what size?**  ``select_strategy``
   maps the regime to an explicit playbook and computes position size from the
   *actual* risk budget, so the same code path is used for paper and live.

Every decision carries the evidence that produced it, plus the strategies that
were rejected and why, so the UI can explain itself.  When evidence is thin the
engine returns ``low_confidence`` and the caller must fall back to WAIT/NO_TRADE.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.services.indicators import get_engine
from app.services.indicators.engine import IndicatorError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regime vocabulary (stable ids — the DB and the UI both key off these)
# ---------------------------------------------------------------------------
TREND_UP_STRONG = "trend_up_strong"
TREND_UP_WEAK = "trend_up_weak"
TREND_DOWN_STRONG = "trend_down_strong"
TREND_DOWN_WEAK = "trend_down_weak"
SIDEWAYS = "sideways"
HIGH_VOLATILITY = "high_volatility"
LOW_VOLATILITY = "low_volatility"
BREAKOUT = "breakout"
BREAKDOWN = "breakdown"
REVERSAL = "reversal"
CHOPPY = "choppy"
EXPIRY_DAY = "expiry_day"

REGIME_LABELS: Dict[str, str] = {
    TREND_UP_STRONG: "Strong bullish trend",
    TREND_UP_WEAK: "Weak bullish trend",
    TREND_DOWN_STRONG: "Strong bearish trend",
    TREND_DOWN_WEAK: "Weak bearish trend",
    SIDEWAYS: "Sideways market",
    HIGH_VOLATILITY: "High volatility",
    LOW_VOLATILITY: "Low volatility",
    BREAKOUT: "Breakout",
    BREAKDOWN: "Breakdown",
    REVERSAL: "Reversal / transition",
    CHOPPY: "Choppy market",
    EXPIRY_DAY: "Expiry-day market",
}

# Regimes where a directional entry is structurally unsupported.
NON_DIRECTIONAL = frozenset({SIDEWAYS, CHOPPY, LOW_VOLATILITY})

# ADX thresholds (Wilder convention).
ADX_STRONG = 25.0
ADX_TRENDING = 20.0
ADX_CHOP = 15.0

# ATR as a percentage of price.  These scales are timeframe-dependent: a 5m
# bar's range and a daily bar's range differ by roughly an order of magnitude,
# so a single threshold would mislabel one of them.
ATR_HIGH_PCT_BY_TF: Dict[str, float] = {
    "1m": 0.25, "3m": 0.30, "5m": 0.45, "10m": 0.55, "15m": 0.65,
    "30m": 0.85, "1h": 1.05, "2h": 1.25, "4h": 1.50, "1d": 2.20,
    "1wk": 4.00, "1mo": 7.00,
}
ATR_LOW_PCT_BY_TF: Dict[str, float] = {
    "1m": 0.035, "3m": 0.045, "5m": 0.065, "10m": 0.09, "15m": 0.11,
    "30m": 0.16, "1h": 0.22, "2h": 0.30, "4h": 0.40, "1d": 0.60,
    "1wk": 1.20, "1mo": 2.20,
}
# Defaults when the timeframe is unknown (5m-like behaviour).
ATR_HIGH_PCT = ATR_HIGH_PCT_BY_TF["5m"]
ATR_LOW_PCT = ATR_LOW_PCT_BY_TF["5m"]


def atr_thresholds(timeframe: str) -> Tuple[float, float]:
    """Return ``(high_pct, low_pct)`` for a timeframe."""
    key = (timeframe or "5m").lower()
    return (
        ATR_HIGH_PCT_BY_TF.get(key, ATR_HIGH_PCT),
        ATR_LOW_PCT_BY_TF.get(key, ATR_LOW_PCT),
    )

# Bollinger width (band width / middle) thresholds.
BB_SQUEEZE = 0.012
BB_EXPANSION = 0.055


@dataclass
class RegimeEvidence:
    """The measurements behind a regime label (all nullable — never faked)."""

    adx: Optional[float] = None
    atr: Optional[float] = None
    atr_pct: Optional[float] = None
    bb_width: Optional[float] = None
    ema_fast: Optional[float] = None
    ema_slow: Optional[float] = None
    ema_slope_pct: Optional[float] = None
    donchian_position: Optional[float] = None
    efficiency_ratio: Optional[float] = None
    close: Optional[float] = None
    timeframe_bias: Dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        def r(value: Optional[float], digits: int = 3) -> Optional[float]:
            return None if value is None else round(value, digits)

        return {
            "adx": r(self.adx, 2),
            "atr": r(self.atr, 2),
            "atr_pct": r(self.atr_pct, 4),
            "bb_width": r(self.bb_width, 5),
            "ema_fast": r(self.ema_fast, 2),
            "ema_slow": r(self.ema_slow, 2),
            "ema_slope_pct": r(self.ema_slope_pct, 4),
            "donchian_position": r(self.donchian_position, 4),
            "efficiency_ratio": r(self.efficiency_ratio, 4),
            "close": r(self.close, 2),
            "timeframe_bias": dict(self.timeframe_bias),
        }


@dataclass
class RegimeResult:
    regime: str
    label: str
    confidence: float  # 0..1, derived from how many signals agree
    evidence: RegimeEvidence
    reason: str
    alternates: List[str] = field(default_factory=list)
    low_confidence: bool = False

    @property
    def directional(self) -> bool:
        return self.regime not in NON_DIRECTIONAL

    def as_dict(self) -> Dict[str, Any]:
        return {
            "regime": self.regime,
            "label": self.label,
            "confidence": round(self.confidence, 3),
            "low_confidence": self.low_confidence,
            "directional": self.directional,
            "reason": self.reason,
            "alternates": self.alternates,
            "evidence": self.evidence.as_dict(),
        }


# ---------------------------------------------------------------------------
# Indicator extraction
# ---------------------------------------------------------------------------
# Indicators the regime detector needs.  All exist in the central registry.
REGIME_INDICATORS: Tuple[str, ...] = ("adx", "atr", "ema", "bollinger_bandwidth", "donchian")


def _last_numeric(result: Optional[Dict[str, Any]]) -> Optional[float]:
    """Newest numeric value from an engine result (series may be dict or list)."""
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


def _named_series(result: Optional[Dict[str, Any]], *names: str) -> Optional[List[Any]]:
    """Pull a named series out of an engine result (e.g. ema_fast / upper)."""
    if not isinstance(result, dict):
        return None
    series = result.get("series")
    if not isinstance(series, dict):
        return series if isinstance(series, list) else None
    for name in names:
        candidate = series.get(name)
        if isinstance(candidate, (list, tuple)):
            return list(candidate)
    # Fall back to the single series when the indicator emits only one.
    lists = [v for v in series.values() if isinstance(v, (list, tuple))]
    return list(lists[0]) if len(lists) == 1 else None


def _last_of(values: Optional[Sequence[Any]]) -> Optional[float]:
    if not values:
        return None
    for value in reversed(values):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def timeframe_bias(closes: Sequence[float]) -> str:
    """Directional read of a close series, normalised by its own noise.

    The recent five-bar mean is compared with the previous five-bar mean and
    divided by the average absolute bar change.  That makes the threshold
    scale-free: a 2-point drift on NIFTY and a 200-point drift on an index
    future are judged consistently, and a flat series cannot look directional.
    """
    values = [float(c) for c in closes if c is not None]
    if len(values) < 10:
        return "unknown"

    recent = sum(values[-5:]) / 5.0
    prior = sum(values[-10:-5]) / 5.0
    diff = recent - prior

    window = values[-21:]
    steps = [abs(window[i] - window[i - 1]) for i in range(1, len(window))]
    if not steps:
        return "unknown"
    avg_abs = sum(steps) / len(steps)
    if avg_abs <= 0:
        return "neutral"

    z = diff / avg_abs
    if z > 1.0:
        return "bullish"
    if z < -1.0:
        return "bearish"
    return "neutral"


def efficiency_ratio(closes: Sequence[float], window: int = 20) -> Optional[float]:
    """Kaufman efficiency ratio: net move divided by total path travelled.

    ``1.0`` is a perfectly straight move; near ``0`` is pure chop.  Unlike ADX
    this needs no smoothing and no OHLC, so it separates trend from range even
    when volatility is low.
    """
    values = [float(c) for c in closes if c is not None]
    if len(values) < window + 1:
        return None
    segment = values[-(window + 1):]
    net = abs(segment[-1] - segment[0])
    path = sum(abs(segment[i] - segment[i - 1]) for i in range(1, len(segment)))
    if path <= 0:
        return 0.0
    return net / path


def _ema_slope(closes: Sequence[float], period: int = 20) -> Optional[float]:
    """Percent slope of an EMA over the last few bars (no look-ahead)."""
    if len(closes) < period + 5:
        return None
    alpha = 2.0 / (period + 1)
    ema = sum(closes[:period]) / period
    history: List[float] = []
    for price in closes[period:]:
        ema = price * alpha + ema * (1 - alpha)
        history.append(ema)
    if len(history) < 5 or history[-5] <= 0:
        return None
    return (history[-1] - history[-5]) / history[-5] * 100.0


# ---------------------------------------------------------------------------
# Regime detection
# ---------------------------------------------------------------------------
def detect_regime(
    candles_by_timeframe: Dict[str, Sequence[Dict[str, Any]]],
    primary_timeframe: str = "5m",
    is_expiry_day: bool = False,
    reference_close: Optional[float] = None,
) -> RegimeResult:
    """Classify the market from **real** candles across timeframes.

    ``candles_by_timeframe`` maps timeframe → ascending OHLCV dicts as returned
    by the provider.  Indicators are computed from those candles directly, so
    ADX/ATR reflect genuine wicks and ranges rather than a reconstructed
    approximation.  Only the primary timeframe's indicators drive the label;
    the other timeframes contribute the agreement read.
    """
    series: Dict[str, List[Dict[str, Any]]] = {
        tf: [c for c in (candles or []) if isinstance(c, dict) and c.get("close") is not None]
        for tf, candles in candles_by_timeframe.items()
    }
    closes_by_tf: Dict[str, List[float]] = {
        tf: [float(c["close"]) for c in candles] for tf, candles in series.items()
    }

    primary_candles = series.get(primary_timeframe) or []
    primary = closes_by_tf.get(primary_timeframe) or []
    evidence = RegimeEvidence()

    biases = {
        tf: timeframe_bias(values)
        for tf, values in closes_by_tf.items()
        if values
    }
    evidence.timeframe_bias = biases

    if len(primary) < 25:
        return RegimeResult(
            regime=SIDEWAYS,
            label=REGIME_LABELS[SIDEWAYS],
            confidence=0.0,
            evidence=evidence,
            reason=(
                f"insufficient history on {primary_timeframe} "
                f"({len(primary)} closes, 25 required) — regime unknown"
            ),
            low_confidence=True,
        )

    evidence.close = reference_close if reference_close is not None else primary[-1]
    evidence.efficiency_ratio = efficiency_ratio(primary)

    # --- indicators from the shared engine, computed on the real candles
    try:
        results = get_engine().calculate_many(list(REGIME_INDICATORS), primary_candles, None)
    except (IndicatorError, Exception) as error:  # never let regime kill a decision
        logger.warning("regime indicator calculation failed: %s", error)
        results = {}

    adx = _last_numeric(results.get("adx"))
    atr = _last_numeric(results.get("atr"))
    bb_width = _last_numeric(results.get("bollinger_bandwidth"))

    ema_result = results.get("ema")
    fast_series = _named_series(ema_result, "ema_fast", "fast", "ema9", "ema_9")
    slow_series = _named_series(ema_result, "ema_slow", "slow", "ema21", "ema_21")
    evidence.ema_fast = _last_of(fast_series)
    evidence.ema_slow = _last_of(slow_series)
    evidence.ema_slope_pct = _ema_slope(primary)

    donchian = results.get("donchian")
    upper = _last_of(_named_series(donchian, "upper", "donchian_upper", "high"))
    lower = _last_of(_named_series(donchian, "lower", "donchian_lower", "low"))
    if upper is not None and lower is not None and upper > lower and evidence.close:
        evidence.donchian_position = (evidence.close - lower) / (upper - lower)

    evidence.adx = adx
    evidence.atr = atr
    if atr is not None and evidence.close:
        evidence.atr_pct = atr / evidence.close * 100.0
    evidence.bb_width = bb_width

    # --- decision tree, strongest structural evidence first
    scores: Dict[str, float] = {}

    bullish_tf = sum(1 for b in biases.values() if b == "bullish")
    bearish_tf = sum(1 for b in biases.values() if b == "bearish")
    total_tf = max(1, len(biases))

    efficiency = evidence.efficiency_ratio
    trending_efficiency = efficiency is not None and efficiency >= 0.30
    choppy_efficiency = efficiency is not None and efficiency < 0.18
    primary_bias = biases.get(primary_timeframe, "unknown")
    directional_bias = primary_bias in ("bullish", "bearish")

    # A clean, low-noise move is a trend even when ADX has not caught up yet;
    # ADX lags a fresh directional leg by several bars.
    clean_directional = efficiency is not None and efficiency >= 0.55 and directional_bias

    strong_trend = adx is not None and adx >= ADX_STRONG and trending_efficiency
    trending = (
        (adx is not None and adx >= ADX_TRENDING and trending_efficiency)
        or clean_directional
    )
    choppy = choppy_efficiency or (adx is not None and adx < ADX_CHOP and not clean_directional)

    high_pct, low_pct = atr_thresholds(primary_timeframe)
    high_vol = evidence.atr_pct is not None and evidence.atr_pct >= high_pct
    low_vol = evidence.atr_pct is not None and evidence.atr_pct <= low_pct
    squeeze = bb_width is not None and bb_width <= BB_SQUEEZE
    expanding = bb_width is not None and bb_width >= BB_EXPANSION
    slope = evidence.ema_slope_pct

    at_breakout = (
        evidence.donchian_position is not None
        and evidence.donchian_position >= 0.97
        and (expanding or high_vol)
    )
    at_breakdown = (
        evidence.donchian_position is not None
        and evidence.donchian_position <= 0.03
        and (expanding or high_vol)
    )
    # Reversal: price pinned at an extreme while the trend score disagrees.
    reversal_up = (
        evidence.donchian_position is not None
        and evidence.donchian_position <= 0.03
        and bearish_tf >= max(1, total_tf // 2)
        and slope is not None
        and slope > 0.05
    )
    reversal_down = (
        evidence.donchian_position is not None
        and evidence.donchian_position >= 0.97
        and bullish_tf >= max(1, total_tf // 2)
        and slope is not None
        and slope < -0.05
    )

    if is_expiry_day:
        scores[EXPIRY_DAY] = 0.55
    if at_breakout:
        scores[BREAKOUT] = 0.8
    if at_breakdown:
        scores[BREAKDOWN] = 0.8
    if reversal_up or reversal_down:
        scores[REVERSAL] = 0.7
    if high_vol:
        scores[HIGH_VOLATILITY] = 0.6
    if low_vol:
        scores[LOW_VOLATILITY] = 0.6
    if squeeze and not expanding:
        scores[LOW_VOLATILITY] = max(scores.get(LOW_VOLATILITY, 0), 0.55)
    if choppy:
        scores[CHOPPY] = 0.65

    bullish = (evidence.ema_fast is not None and evidence.ema_slow is not None
               and evidence.ema_fast > evidence.ema_slow) or (slope or 0) > 0
    if strong_trend or trending:
        if bullish:
            scores[TREND_UP_STRONG if strong_trend else TREND_UP_WEAK] = (
                0.75 if strong_trend else 0.6
            )
        else:
            scores[TREND_DOWN_STRONG if strong_trend else TREND_DOWN_WEAK] = (
                0.75 if strong_trend else 0.6
            )
        # A trend label supersedes a low-volatility tag: quiet drift is still
        # directional, and the strategy engine needs the direction.
        scores.pop(LOW_VOLATILITY, None)
    if not scores:
        scores[SIDEWAYS] = 0.5

    # Breakouts and reversals outrank the ambient trend label.
    priority = [
        BREAKOUT, BREAKDOWN, REVERSAL, EXPIRY_DAY, HIGH_VOLATILITY,
        TREND_UP_STRONG, TREND_DOWN_STRONG, TREND_UP_WEAK, TREND_DOWN_WEAK,
        LOW_VOLATILITY, CHOPPY, SIDEWAYS,
    ]
    ranked = sorted(
        scores.items(),
        key=lambda kv: (kv[1], -priority.index(kv[0]) if kv[0] in priority else -99),
        reverse=True,
    )
    regime = ranked[0][0]
    alternates = [name for name, _ in ranked[1:4]]

    # --- confidence: how much of the evidence actually agrees with the label
    agreeing = 0
    total_signals = 0
    directional_bias = biases.get(primary_timeframe, "unknown")

    def check(condition: Optional[bool]) -> None:
        nonlocal agreeing, total_signals
        if condition is None:
            return
        total_signals += 1
        if condition:
            agreeing += 1

    if regime in (TREND_UP_STRONG, TREND_UP_WEAK):
        check(bullish)
        check(slope is not None and slope > 0)
        check(bullish_tf >= bearish_tf)
        check(strong_trend if regime == TREND_UP_STRONG else trending)
    elif regime in (TREND_DOWN_STRONG, TREND_DOWN_WEAK):
        check(not bullish)
        check(slope is not None and slope < 0)
        check(bearish_tf >= bullish_tf)
        check(strong_trend if regime == TREND_DOWN_STRONG else trending)
    elif regime == BREAKOUT:
        check(at_breakout)
        check(bullish_tf >= bearish_tf)
        check(expanding or high_vol)
    elif regime == BREAKDOWN:
        check(at_breakdown)
        check(bearish_tf >= bullish_tf)
        check(expanding or high_vol)
    elif regime == CHOPPY:
        check(choppy)
        check(evidence.bb_width is not None and evidence.bb_width < BB_EXPANSION)
    elif regime == HIGH_VOLATILITY:
        check(high_vol)
        check(expanding)
    elif regime == LOW_VOLATILITY:
        check(low_vol or squeeze)
        check(not expanding)
    elif regime == REVERSAL:
        check(reversal_up or reversal_down)
    else:
        check(not trending)
        check(not high_vol)

    confidence = (agreeing / total_signals) if total_signals else 0.0
    low_confidence = total_signals < 2 or confidence < 0.5

    reason = _regime_reason(regime, evidence, adx, atr, bb_width, directional_bias)

    return RegimeResult(
        regime=regime,
        label=REGIME_LABELS[regime],
        confidence=confidence,
        evidence=evidence,
        reason=reason,
        alternates=alternates,
        low_confidence=low_confidence,
    )


def _regime_reason(
    regime: str,
    evidence: RegimeEvidence,
    adx: Optional[float],
    atr: Optional[float],
    bb_width: Optional[float],
    bias: str,
) -> str:
    parts: List[str] = []
    if adx is not None:
        parts.append(f"ADX {adx:.1f}")
    if evidence.atr_pct is not None:
        parts.append(f"ATR {evidence.atr_pct:.2f}% of price")
    if bb_width is not None:
        parts.append(f"BB width {bb_width:.4f}")
    if evidence.ema_slope_pct is not None:
        parts.append(f"EMA slope {evidence.ema_slope_pct:+.3f}%")
    if evidence.donchian_position is not None:
        parts.append(f"Donchian position {evidence.donchian_position:.2f}")
    if evidence.efficiency_ratio is not None:
        parts.append(f"efficiency {evidence.efficiency_ratio:.2f}")
    if bias != "unknown":
        parts.append(f"primary bias {bias}")
    measured = ", ".join(parts) if parts else "no measurable evidence"
    return f"{REGIME_LABELS[regime]} — {measured}"


def _closes(candles: Sequence[Dict[str, Any]]) -> List[float]:
    """Extract real closes from provider candles (no synthesis)."""
    return [float(c["close"]) for c in candles if isinstance(c, dict) and c.get("close") is not None]


# ---------------------------------------------------------------------------
# Strategy playbooks
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StrategySpec:
    """A regime-specific playbook entry."""

    name: str
    direction: str  # long | short | both | none
    style: str  # trend | mean_reversion | breakout | none
    stop_atr_mult: float
    target_atr_mult: float
    risk_pct: float  # fraction of equity risked per trade
    entry_note: str
    invalidation: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "direction": self.direction,
            "style": self.style,
            "stop_atr_mult": self.stop_atr_mult,
            "target_atr_mult": self.target_atr_mult,
            "risk_pct": self.risk_pct,
            "entry_note": self.entry_note,
            "invalidation": self.invalidation,
        }


NO_TRADE_SPEC = StrategySpec(
    name="no_trade",
    direction="none",
    style="none",
    stop_atr_mult=0.0,
    target_atr_mult=0.0,
    risk_pct=0.0,
    entry_note="No validated edge in this regime — stay flat.",
    invalidation="Regime changes to a trending or breakout state with confirmation.",
)

PLAYBOOK: Dict[str, StrategySpec] = {
    TREND_UP_STRONG: StrategySpec(
        "trend_follow_long", "long", "trend", 1.5, 3.0, 0.005,
        "Buy pullbacks to the fast EMA while ADX stays above 25.",
        "Close back below the slow EMA or ADX falling under 20.",
    ),
    TREND_UP_WEAK: StrategySpec(
        "trend_follow_long_reduced", "long", "trend", 2.0, 2.5, 0.0035,
        "Smaller size; only take pullback entries with higher-timeframe agreement.",
        "Higher timeframes flip bearish or ADX drops under 15.",
    ),
    TREND_DOWN_STRONG: StrategySpec(
        "trend_follow_short", "short", "trend", 1.5, 3.0, 0.005,
        "Sell rallies into the fast EMA while ADX stays above 25.",
        "Close back above the slow EMA or ADX falling under 20.",
    ),
    TREND_DOWN_WEAK: StrategySpec(
        "trend_follow_short_reduced", "short", "trend", 2.0, 2.5, 0.0035,
        "Smaller size; only take rally entries with higher-timeframe agreement.",
        "Higher timeframes flip bullish or ADX drops under 15.",
    ),
    BREAKOUT: StrategySpec(
        "breakout_continuation", "long", "breakout", 1.2, 3.5, 0.004,
        "Enter on the retest of the broken range high with expanding volume.",
        "Price closes back inside the prior range (failed breakout).",
    ),
    BREAKDOWN: StrategySpec(
        "breakdown_continuation", "short", "breakout", 1.2, 3.5, 0.004,
        "Enter on the retest of the broken range low with expanding volume.",
        "Price closes back inside the prior range (failed breakdown).",
    ),
    REVERSAL: StrategySpec(
        "reversal_confirmation", "both", "mean_reversion", 1.8, 2.8, 0.0025,
        "Wait for a structure shift (CHoCH) before entering against the prior trend.",
        "Prior trend resumes and takes out the reversal swing.",
    ),
    HIGH_VOLATILITY: StrategySpec(
        "volatility_expansion", "both", "breakout", 2.5, 3.0, 0.0025,
        "Half size; require a confirmed close beyond the range before entry.",
        "Volatility collapses back under the expansion threshold.",
    ),
    LOW_VOLATILITY: NO_TRADE_SPEC,
    SIDEWAYS: StrategySpec(
        "range_fade", "both", "mean_reversion", 1.0, 1.6, 0.002,
        "Fade the range edges only, with a tight stop outside the band.",
        "Price accepts outside the range (trend beginning).",
    ),
    CHOPPY: NO_TRADE_SPEC,
    EXPIRY_DAY: StrategySpec(
        "expiry_range_fade", "both", "mean_reversion", 1.0, 1.4, 0.0015,
        "Quarter size; only fade extremes near the pinning strike.",
        "Premium expansion or a move beyond the expiry range.",
    ),
}

# Fallback used when regime confidence is too low to trust any playbook.
FALLBACK_REGIME = SIDEWAYS


@dataclass
class StrategySelection:
    """Why this strategy, at this size, or why nothing is allowed."""

    strategy: StrategySpec
    regime: RegimeResult
    allowed: bool
    reason: str
    rejected: List[Dict[str, str]] = field(default_factory=list)
    fallback_applied: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy.as_dict(),
            "regime": self.regime.as_dict(),
            "allowed": self.allowed,
            "reason": self.reason,
            "rejected": self.rejected,
            "fallback_applied": self.fallback_applied,
        }


def select_strategy(
    regime: RegimeResult,
    mtf_agreement: Optional[float] = None,
    allow_low_confidence: bool = False,
) -> StrategySelection:
    """Pick the playbook for ``regime``, refusing when evidence is thin.

    ``mtf_agreement`` is the fraction (0..1) of timeframes that agree with the
    regime direction.  A weak agreement demotes a trend playbook rather than
    silently trading it.
    """
    rejected: List[Dict[str, str]] = []

    if regime.low_confidence and not allow_low_confidence:
        fallback = PLAYBOOK[FALLBACK_REGIME]
        return StrategySelection(
            strategy=fallback,
            regime=regime,
            allowed=False,
            reason=(
                f"regime confidence {regime.confidence:.0%} is below the 50% floor; "
                f"falling back to {REGIME_LABELS[FALLBACK_REGIME]} behaviour"
            ),
            rejected=[{"strategy": PLAYBOOK[regime.regime].name, "reason": "low regime confidence"}],
            fallback_applied=True,
        )

    spec = PLAYBOOK.get(regime.regime, NO_TRADE_SPEC)

    if spec.direction == "none":
        for name, other in PLAYBOOK.items():
            if name != regime.regime and other.direction != "none":
                rejected.append({"strategy": other.name, "reason": f"not a {REGIME_LABELS[name]} regime"})
        return StrategySelection(
            strategy=spec,
            regime=regime,
            allowed=False,
            reason=f"{REGIME_LABELS[regime.regime]}: no validated directional edge",
            rejected=rejected[:4],
        )

    # Multi-timeframe disagreement blocks directional trend entries.
    if (
        regime.regime in (TREND_UP_STRONG, TREND_UP_WEAK, TREND_DOWN_STRONG, TREND_DOWN_WEAK)
        and mtf_agreement is not None
        and mtf_agreement < 0.5
    ):
        rejected.append(
            {"strategy": spec.name, "reason": f"multi-timeframe agreement only {mtf_agreement:.0%}"}
        )
        return StrategySelection(
            strategy=NO_TRADE_SPEC,
            regime=regime,
            allowed=False,
            reason=(
                f"{REGIME_LABELS[regime.regime]} on the primary timeframe, but only "
                f"{mtf_agreement:.0%} of timeframes agree — conflict, no entry"
            ),
            rejected=rejected,
        )

    if regime.regime == HIGH_VOLATILITY:
        rejected.append(
            {"strategy": PLAYBOOK[TREND_UP_STRONG].name, "reason": "volatility too high for trend entries"}
        )

    return StrategySelection(
        strategy=spec,
        regime=regime,
        allowed=True,
        reason=f"{REGIME_LABELS[regime.regime]} → {spec.name} ({spec.entry_note})",
        rejected=rejected,
    )


# ---------------------------------------------------------------------------
# Position sizing
# ---------------------------------------------------------------------------
@dataclass
class PositionSize:
    """Sizing result; ``quantity == 0`` means the trade is not permitted."""

    quantity: int
    risk_amount: float
    risk_per_unit: float
    stop_distance: float
    notional: float
    allowed: bool
    reason: str
    capped_by: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "quantity": self.quantity,
            "risk_amount": round(self.risk_amount, 2),
            "risk_per_unit": round(self.risk_per_unit, 2),
            "stop_distance": round(self.stop_distance, 2),
            "notional": round(self.notional, 2),
            "allowed": self.allowed,
            "reason": self.reason,
            "capped_by": self.capped_by,
        }


def size_position(
    entry: float,
    atr: Optional[float],
    spec: StrategySpec,
    equity: float,
    max_position_size: int = 50,
    lot_size: int = 1,
    available_exposure: Optional[float] = None,
    daily_loss_remaining: Optional[float] = None,
) -> PositionSize:
    """Risk-based sizing bounded by every configured limit.

    Risk per trade is ``equity * spec.risk_pct``.  Quantity is derived from the
    ATR stop distance, then clamped by the position-size cap, the remaining
    exposure budget and the remaining daily-loss budget.  If any input is
    missing the trade is refused rather than guessed.
    """
    if not spec.stop_atr_mult or spec.risk_pct <= 0:
        return PositionSize(0, 0.0, 0.0, 0.0, 0.0, False, "strategy does not permit entries")

    if entry <= 0:
        return PositionSize(0, 0.0, 0.0, 0.0, 0.0, False, "invalid entry price")

    if atr is None or atr <= 0:
        return PositionSize(
            0, 0.0, 0.0, 0.0, 0.0, False,
            "ATR unavailable — cannot derive a volatility stop, refusing to size",
        )

    if equity <= 0:
        return PositionSize(0, 0.0, 0.0, 0.0, 0.0, False, "equity unavailable")

    stop_distance = atr * spec.stop_atr_mult
    risk_budget = equity * spec.risk_pct
    capped_by: Optional[str] = None

    if daily_loss_remaining is not None:
        if daily_loss_remaining <= 0:
            return PositionSize(
                0, 0.0, stop_distance, stop_distance, 0.0, False,
                "daily loss limit already reached",
                capped_by="daily_loss",
            )
        if daily_loss_remaining < risk_budget:
            risk_budget = daily_loss_remaining
            capped_by = "daily_loss"

    raw_quantity = int(risk_budget // stop_distance) if stop_distance > 0 else 0
    quantity = raw_quantity

    if quantity > max_position_size:
        quantity = max_position_size
        capped_by = "max_position_size"

    if available_exposure is not None:
        max_by_exposure = int(available_exposure // entry) if entry > 0 else 0
        if quantity > max_by_exposure:
            quantity = max_by_exposure
            capped_by = "max_exposure"

    if lot_size > 1:
        quantity = (quantity // lot_size) * lot_size

    if quantity <= 0:
        return PositionSize(
            0, 0.0, stop_distance, stop_distance, 0.0, False,
            "risk budget too small for one unit at this stop distance",
            capped_by=capped_by,
        )

    risk_amount = quantity * stop_distance
    return PositionSize(
        quantity=quantity,
        risk_amount=risk_amount,
        risk_per_unit=stop_distance,
        stop_distance=stop_distance,
        notional=quantity * entry,
        allowed=True,
        reason=(
            f"{quantity} units risk ₹{risk_amount:,.0f} "
            f"({spec.risk_pct:.2%} of ₹{equity:,.0f}) at a {spec.stop_atr_mult:g}×ATR stop"
        ),
        capped_by=capped_by,
    )


def stop_and_target(
    entry: float,
    atr: Optional[float],
    spec: StrategySpec,
    direction: str,
) -> Dict[str, Optional[float]]:
    """Regime-specific stop-loss and two targets, derived from ATR."""
    if atr is None or atr <= 0 or entry <= 0:
        return {"stop_loss": None, "target_1": None, "target_2": None, "risk_reward": None}

    stop = atr * spec.stop_atr_mult
    t1 = atr * spec.target_atr_mult
    t2 = atr * spec.target_atr_mult * 1.6
    sign = -1 if direction == "short" else 1

    return {
        "stop_loss": round(entry - sign * stop, 2),
        "target_1": round(entry + sign * t1, 2),
        "target_2": round(entry + sign * t2, 2),
        "risk_reward": round(spec.target_atr_mult / spec.stop_atr_mult, 2)
        if spec.stop_atr_mult
        else None,
    }


__all__ = [
    "ADX_CHOP",
    "ADX_STRONG",
    "ADX_TRENDING",
    "BREAKDOWN",
    "BREAKOUT",
    "CHOPPY",
    "EXPIRY_DAY",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "NON_DIRECTIONAL",
    "PLAYBOOK",
    "PositionSize",
    "REGIME_LABELS",
    "REGIME_INDICATORS",
    "REVERSAL",
    "RegimeEvidence",
    "RegimeResult",
    "SIDEWAYS",
    "StrategySelection",
    "StrategySpec",
    "TREND_DOWN_STRONG",
    "TREND_DOWN_WEAK",
    "TREND_UP_STRONG",
    "TREND_UP_WEAK",
    "detect_regime",
    "select_strategy",
    "size_position",
    "stop_and_target",
    "timeframe_bias",
]
