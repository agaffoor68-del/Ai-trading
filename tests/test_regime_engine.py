"""Tests for the regime-adaptive strategy engine (Task 2)."""

from __future__ import annotations

import math

import pytest

from app.services.brain import regime_engine as re


def to_candles(closes: list[float], wick: float = 4.0) -> list[dict]:
    """Turn a close path into realistic OHLCV candles (real wicks)."""
    out = []
    previous = closes[0] if closes else 0.0
    for index, close in enumerate(closes):
        open_price = previous
        high = max(open_price, close) + wick
        low = min(open_price, close) - wick
        out.append(
            {
                "ts": 1_700_000_000 + index * 300,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1000.0 + index,
            }
        )
        previous = close
    return out


def trending_closes(count: int = 120, slope: float = 15.0, base: float = 22000.0,
                    noise: float = 8.0) -> list[float]:
    """Monotonic-ish series: strong directional trend with small noise."""
    return [base + i * slope + math.sin(i / 3.0) * noise for i in range(count)]


def choppy_closes(count: int = 120, base: float = 22000.0, amplitude: float = 8.0) -> list[float]:
    """Oscillating series with no net drift (range/mean-reverting)."""
    return [base + math.sin(i / 2.0) * amplitude for i in range(count)]


def volatile_closes(count: int = 120, base: float = 22000.0) -> list[float]:
    """Large alternating swings: high ATR, weak direction."""
    out = []
    for i in range(count):
        swing = 400.0 if i % 2 == 0 else -400.0
        out.append(base + swing + i * 0.2)
    return out


# ---------------------------------------------------------------- structure
def test_insufficient_history_returns_low_confidence():
    result = re.detect_regime({"5m": to_candles([100.0, 101.0, 102.0])}, primary_timeframe="5m")

    assert result.low_confidence is True
    assert result.confidence == 0.0
    assert "insufficient history" in result.reason
    assert result.regime == re.SIDEWAYS


def test_uptrend_is_detected_as_bullish_trend():
    candles = {
        "5m": to_candles(trending_closes(slope=15.0)),
        "15m": to_candles(trending_closes(slope=15.0)),
    }

    result = re.detect_regime(candles, primary_timeframe="5m")

    assert result.regime in (re.TREND_UP_STRONG, re.TREND_UP_WEAK)
    assert result.evidence.timeframe_bias["5m"] == "bullish"
    assert result.directional is True
    assert 0.0 <= result.confidence <= 1.0


def test_downtrend_is_detected_as_bearish_trend():
    candles = {
        "5m": to_candles(trending_closes(slope=-15.0)),
        "15m": to_candles(trending_closes(slope=-15.0)),
    }

    result = re.detect_regime(candles, primary_timeframe="5m")

    assert result.regime in (re.TREND_DOWN_STRONG, re.TREND_DOWN_WEAK)
    assert result.evidence.timeframe_bias["5m"] == "bearish"


def test_choppy_series_is_not_labelled_a_trend():
    candles = {
        "5m": to_candles(choppy_closes()),
        "15m": to_candles(choppy_closes()),
    }

    result = re.detect_regime(candles, primary_timeframe="5m")

    assert result.regime not in (re.TREND_UP_STRONG, re.TREND_DOWN_STRONG)
    assert result.evidence.efficiency_ratio is not None
    assert result.evidence.efficiency_ratio < 0.3


def test_high_volatility_regime_is_detected():
    candles = {
        "5m": to_candles(volatile_closes(), wick=50.0),
        "15m": to_candles(volatile_closes(), wick=50.0),
    }

    result = re.detect_regime(candles, primary_timeframe="5m")

    assert result.evidence.atr_pct is not None
    assert result.evidence.atr_pct > 0.5
    assert result.regime in (
        re.HIGH_VOLATILITY, re.CHOPPY, re.BREAKOUT, re.BREAKDOWN, re.REVERSAL,
        re.TREND_UP_WEAK, re.TREND_DOWN_WEAK,
    )


def test_expiry_day_is_reported_as_an_alternate():
    candles = {
        "5m": to_candles(trending_closes(slope=15.0)),
        "15m": to_candles(trending_closes(slope=15.0)),
    }

    result = re.detect_regime(candles, primary_timeframe="5m", is_expiry_day=True)

    assert re.EXPIRY_DAY in result.alternates or result.regime == re.EXPIRY_DAY


def test_evidence_serialises_to_json_safe_dict():
    import json

    result = re.detect_regime(
        {"5m": to_candles(trending_closes())}, primary_timeframe="5m"
    )
    payload = result.as_dict()

    json.dumps(payload)  # must not raise
    assert "evidence" in payload
    assert "regime" in payload
    assert isinstance(payload["confidence"], float)


def test_timeframe_bias_helper():
    assert re.timeframe_bias([100 + i for i in range(12)]) == "bullish"
    assert re.timeframe_bias([112 - i for i in range(12)]) == "bearish"
    assert re.timeframe_bias([100] * 12) == "neutral"
    assert re.timeframe_bias([100]) == "unknown"


def test_efficiency_ratio_separates_trend_from_chop():
    trend = re.efficiency_ratio(trending_closes(slope=2.0, noise=0.0))
    chop = re.efficiency_ratio(choppy_closes())

    assert trend is not None and chop is not None
    assert trend > 0.9
    assert chop < 0.3
    assert trend > chop


def test_efficiency_ratio_needs_enough_history():
    assert re.efficiency_ratio([100, 101, 102]) is None


# ------------------------------------------------------------ strategy choice
def test_strong_trend_selects_trend_playbook():
    regime = re.RegimeResult(
        regime=re.TREND_UP_STRONG, label="Strong bullish trend", confidence=0.9,
        evidence=re.RegimeEvidence(), reason="test",
    )

    selection = re.select_strategy(regime, mtf_agreement=0.8)

    assert selection.allowed is True
    assert selection.strategy.name == "trend_follow_long"
    assert selection.strategy.direction == "long"


def test_choppy_regime_blocks_entries():
    regime = re.RegimeResult(
        regime=re.CHOPPY, label="Choppy market", confidence=0.8,
        evidence=re.RegimeEvidence(), reason="test",
    )

    selection = re.select_strategy(regime)

    assert selection.allowed is False
    assert selection.strategy.name == "no_trade"


def test_low_confidence_falls_back_instead_of_trading():
    regime = re.RegimeResult(
        regime=re.TREND_UP_STRONG, label="Strong bullish trend", confidence=0.2,
        evidence=re.RegimeEvidence(), reason="weak", low_confidence=True,
    )

    selection = re.select_strategy(regime)

    assert selection.allowed is False
    assert selection.fallback_applied is True
    assert selection.rejected


def test_mtf_conflict_blocks_directional_entry():
    regime = re.RegimeResult(
        regime=re.TREND_UP_STRONG, label="Strong bullish trend", confidence=0.9,
        evidence=re.RegimeEvidence(), reason="test",
    )

    selection = re.select_strategy(regime, mtf_agreement=0.25)

    assert selection.allowed is False
    assert "conflict" in selection.reason.lower()
    assert selection.rejected


def test_strategy_selection_records_rejection_reasons():
    regime = re.RegimeResult(
        regime=re.CHOPPY, label="Choppy market", confidence=0.9,
        evidence=re.RegimeEvidence(), reason="test",
    )

    selection = re.select_strategy(regime)

    assert selection.rejected
    assert all("strategy" in r and "reason" in r for r in selection.rejected)


# ------------------------------------------------------------- position sizing
def _spec(**overrides) -> re.StrategySpec:
    base = dict(
        name="trend_follow_long", direction="long", style="trend",
        stop_atr_mult=1.5, target_atr_mult=3.0, risk_pct=0.005,
        entry_note="test", invalidation="test",
    )
    base.update(overrides)
    return re.StrategySpec(**base)


def test_position_size_is_risk_based():
    size = re.size_position(entry=100.0, atr=2.0, spec=_spec(), equity=500_000.0,
                            max_position_size=1000)

    # risk budget = 2500, stop distance = 3 -> 833 units
    assert size.allowed is True
    assert size.quantity == 833
    assert size.risk_amount <= 2500.0 + 1e-6


def test_position_size_capped_by_max_position_size():
    size = re.size_position(entry=100.0, atr=0.1, spec=_spec(), equity=500_000.0,
                            max_position_size=50)

    assert size.quantity == 50
    assert size.capped_by == "max_position_size"


def test_position_size_capped_by_exposure_budget():
    size = re.size_position(entry=100.0, atr=2.0, spec=_spec(), equity=500_000.0,
                            max_position_size=1000, available_exposure=5000.0)

    assert size.quantity == 50
    assert size.capped_by == "max_exposure"


def test_position_size_refuses_when_daily_loss_exhausted():
    size = re.size_position(entry=100.0, atr=2.0, spec=_spec(), equity=500_000.0,
                            daily_loss_remaining=0.0)

    assert size.allowed is False
    assert size.quantity == 0
    assert size.capped_by == "daily_loss"


def test_position_size_capped_by_remaining_daily_loss():
    size = re.size_position(entry=100.0, atr=2.0, spec=_spec(), equity=500_000.0,
                            max_position_size=1000, daily_loss_remaining=300.0)

    # budget 300 / stop 3 = 100 units
    assert size.quantity == 100
    assert size.capped_by == "daily_loss"


def test_position_size_refuses_without_atr():
    size = re.size_position(entry=100.0, atr=None, spec=_spec(), equity=500_000.0)

    assert size.allowed is False
    assert "ATR" in size.reason


def test_position_size_refuses_no_trade_spec():
    size = re.size_position(entry=100.0, atr=2.0, spec=re.NO_TRADE_SPEC, equity=500_000.0)

    assert size.allowed is False


def test_position_size_respects_lot_size():
    size = re.size_position(entry=100.0, atr=2.0, spec=_spec(), equity=500_000.0,
                            max_position_size=1000, lot_size=75)

    assert size.quantity % 75 == 0


# --------------------------------------------------------------- stop/target
def test_stop_and_target_long():
    levels = re.stop_and_target(entry=100.0, atr=2.0, spec=_spec(), direction="long")

    assert levels["stop_loss"] == pytest.approx(97.0)
    assert levels["target_1"] == pytest.approx(106.0)
    assert levels["risk_reward"] == pytest.approx(2.0)


def test_stop_and_target_short_is_inverted():
    levels = re.stop_and_target(entry=100.0, atr=2.0, spec=_spec(), direction="short")

    assert levels["stop_loss"] == pytest.approx(103.0)
    assert levels["target_1"] == pytest.approx(94.0)


def test_stop_and_target_without_atr_returns_none():
    levels = re.stop_and_target(entry=100.0, atr=None, spec=_spec(), direction="long")

    assert levels["stop_loss"] is None
    assert levels["target_1"] is None


def test_playbook_covers_every_regime():
    for regime in re.REGIME_LABELS:
        assert regime in re.PLAYBOOK, f"missing playbook for {regime}"
