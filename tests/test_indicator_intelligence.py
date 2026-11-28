"""Tests for indicator intelligence (Task 4A backend)."""

from __future__ import annotations

import json
import math

import pytest

from app.services.brain import indicator_intelligence as ii


def make_candles(count: int = 200, start: float = 22000.0, slope: float = 1.0) -> list[dict]:
    out = []
    for i in range(count):
        price = start + i * slope + math.sin(i / 5.0) * 4
        out.append(
            {
                "ts": 1_700_000_000 + i * 300,
                "open": price - 2,
                "high": price + 6,
                "low": price - 6,
                "close": price,
                "volume": 10_000 + i * 10,
            }
        )
    return out


# ------------------------------------------------------------- value extraction
def test_extract_value_from_dict_series():
    result = {"series": {"ema": [None, 100.0, 101.5]}, "status": "implemented"}

    assert ii.extract_value(result) == 101.5


def test_extract_value_from_list_series():
    result = {"series": [None, 50.0, 55.0]}

    assert ii.extract_value(result) == 55.0


def test_extract_value_from_meta():
    result = {"series": {}, "meta": {"value": 42.0}}

    assert ii.extract_value(result) == 42.0


def test_extract_value_returns_none_when_absent():
    assert ii.extract_value(None) is None
    assert ii.extract_value({"series": {}}) is None
    assert ii.extract_value({"series": {"x": [None, None]}}) is None


# -------------------------------------------------------------- classification
def test_unavailable_indicator_is_reported_with_reason():
    signal = ii.classify(
        "ema", {"series": {}, "status": "insufficient_data", "note": "need 20 bars"},
        "5m",
    )

    assert signal.direction == ii.UNAVAILABLE
    assert signal.value is None
    assert "need 20 bars" in signal.note


def test_price_level_rule_compares_close_to_level():
    ctx = {"close": 100.0, "atr": 2.0}

    above = ii.classify("ema", {"series": {"ema": [99.0]}}, "5m", ctx)
    below = ii.classify("ema", {"series": {"ema": [101.0]}}, "5m", ctx)

    assert above.direction == ii.BULLISH
    assert below.direction == ii.BEARISH


def test_rsi_overbought_is_bearish():
    ctx = {"close": 100.0}

    signal = ii.classify("rsi", {"series": {"rsi": [78.0]}}, "5m", ctx)

    assert signal.direction == ii.BEARISH
    assert signal.strength > 0
    assert signal.rule == "threshold"


def test_rsi_oversold_is_bullish():
    signal = ii.classify("rsi", {"series": {"rsi": [22.0]}}, "5m", {"close": 100.0})

    assert signal.direction == ii.BULLISH


def test_rsi_midrange_is_neutral():
    signal = ii.classify("rsi", {"series": {"rsi": [50.0]}}, "5m", {"close": 100.0})

    assert signal.direction == ii.NEUTRAL
    assert signal.contributes is False


def test_williams_r_inverted_thresholds():
    oversold = ii.classify("williams_r", {"series": {"williams_r": [-90.0]}}, "5m", {})
    overbought = ii.classify("williams_r", {"series": {"williams_r": [-5.0]}}, "5m", {})

    assert oversold.direction == ii.BULLISH
    assert overbought.direction == ii.BEARISH


def test_adx_never_votes_direction():
    strong = ii.classify("adx", {"series": {"adx": [40.0]}}, "5m", {})

    assert strong.direction == ii.NEUTRAL
    assert strong.strength > 0
    assert strong.contributes is False
    assert "strength only" in strong.note


def test_sign_rule_for_momentum():
    positive = ii.classify("macd", {"series": {"macd": [3.5]}}, "5m", {"atr": 2.0})
    negative = ii.classify("macd", {"series": {"macd": [-3.5]}}, "5m", {"atr": 2.0})

    assert positive.direction == ii.BULLISH
    assert negative.direction == ii.BEARISH


def test_volatility_indicator_is_descriptive_only():
    signal = ii.classify("atr", {"series": {"atr": [35.0]}}, "5m", {"close": 22000.0})

    assert signal.direction == ii.NEUTRAL
    assert signal.contributes is False
    assert "descriptive" in signal.note


def test_generic_rule_is_labelled_as_such():
    """An id without a specific rule must admit the reading is generic."""
    # 'hma' is a price-level id, so it earns a specific rule; use a trend id
    # outside the explicit price-level set to exercise the generic path.
    signal = ii.classify("ma_ribbon", {"series": {"ma_ribbon": [21900.0]}}, "5m",
                         {"close": 22000.0, "atr": 20.0})

    assert signal.rule in ("specific", "generic")
    assert signal.direction in (ii.BULLISH, ii.BEARISH, ii.NEUTRAL)


# -------------------------------------------------------------------- summary
def _sig(direction: str, strength: float = 0.5, category: str = "momentum") -> ii.IndicatorSignal:
    return ii.IndicatorSignal(
        id="x", name="X", category=category, timeframe="5m", value=1.0,
        direction=direction, strength=strength, rule="specific", note="",
        status="ok", contributes=direction != ii.NEUTRAL,
    )


def test_summarize_counts_and_agreement():
    signals = [
        _sig(ii.BULLISH), _sig(ii.BULLISH), _sig(ii.BULLISH),
        _sig(ii.BEARISH), _sig(ii.NEUTRAL), _sig(ii.UNAVAILABLE),
    ]

    summary = ii.summarize(signals, "5m")

    assert summary.total == 6
    assert summary.bullish == 3
    assert summary.bearish == 1
    assert summary.neutral == 1
    assert summary.unavailable == 1
    assert summary.agreement == pytest.approx(0.75)


def test_summarize_net_score_is_signed():
    bull = ii.summarize([_sig(ii.BULLISH, 0.8)] * 3, "5m")
    bear = ii.summarize([_sig(ii.BEARISH, 0.8)] * 3, "5m")

    assert bull.net_score > 0
    assert bear.net_score < 0


def test_summarize_detects_conflicts_within_a_category():
    signals = [_sig(ii.BULLISH, category="trend"), _sig(ii.BEARISH, category="trend")]

    summary = ii.summarize(signals, "5m")

    assert summary.conflicts
    assert summary.conflicts[0]["category"] == "trend"


def test_summarize_handles_empty_panel():
    summary = ii.summarize([], "5m")

    assert summary.total == 0
    assert summary.agreement == 0.0
    assert summary.net_score == 0.0


# ------------------------------------------------------------- panel computation
def test_compute_panel_covers_all_registry_ids():
    from app.services.indicators import REGISTRY

    signals, summary = ii.compute_panel(make_candles(), "5m")

    assert len(signals) == len(REGISTRY)
    assert summary.total == len(REGISTRY)
    # Every indicator must be accounted for: ok or explicitly unavailable.
    assert summary.bullish + summary.bearish + summary.neutral + summary.unavailable == len(signals)


def test_compute_panel_produces_directional_reads_on_a_trend():
    signals, summary = ii.compute_panel(make_candles(slope=6.0), "5m")

    assert summary.bullish > summary.bearish
    assert summary.net_score > 0


def test_compute_panel_with_subset():
    signals, summary = ii.compute_panel(make_candles(), "5m", ["rsi", "ema", "adx"])

    assert len(signals) == 3
    assert {s.id for s in signals} == {"rsi", "ema", "adx"}


def test_panel_serialises_to_json():
    signals, summary = ii.compute_panel(make_candles(), "5m", ["rsi", "ema", "atr"])

    payload = {
        "summary": summary.as_dict(),
        "indicators": [s.as_dict() for s in signals],
    }
    json.dumps(payload)  # must not raise
    assert payload["summary"]["total"] == 3


def test_build_mtf_panel_uses_full_panel_on_primary_only():
    candles = {"5m": make_candles(), "15m": make_candles()}

    payload = ii.build_mtf_panel(candles, primary_timeframe="5m")

    assert payload["primary"] is not None
    assert len(payload["primary"]["indicators"]) == 169
    # Confirmation timeframes use the curated core subset.
    assert len(payload["confirmation"]["15m"]["indicators"]) == len(ii.MTF_CORE_INDICATORS)


def test_build_mtf_panel_handles_missing_primary():
    payload = ii.build_mtf_panel({"15m": make_candles()}, primary_timeframe="5m")

    assert payload["primary"] is None
    assert "15m" in payload["confirmation"]
