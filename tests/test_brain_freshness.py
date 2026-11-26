"""Decision-pipeline data gates: unusable data must produce NO_TRADE."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core import market_time as mt
from app.services.brain.data_intelligence import (
    UNAVAILABLE_WITHOUT_FEED,
    _latest_value,
)
from app.services.brain.decision_engine import NO_TRADE, DecisionEngine


@pytest.fixture()
def engine():
    return DecisionEngine()


def _snapshot(**overrides):
    base = {
        "symbol": "NIFTY",
        "interval": "5m",
        "data_complete": True,
        "freshness": {"stale": False, "stale_blocks": [], "blocks": []},
        "candle_meta": {"count": 200, "interval": "5m", "source": "fyers_v3", "last_ts": 1},
        "indicators": {"available": True, "values": {"ema": 1, "rsi": 2, "atr": 3}, "missing": []},
        "quote": {"ltp": 100.0, "timestamp": mt.ist_now().isoformat(), "source": "redis"},
        "options": {"available": False},
        "news": [],
    }
    base.update(overrides)
    return base


def test_fresh_snapshot_has_no_gate(engine):
    assert engine._data_gate(_snapshot()) is None


def test_stale_freshness_blocks(engine):
    gate = engine._data_gate(
        _snapshot(freshness={"stale": True, "stale_blocks": ["quote"], "blocks": []})
    )
    assert gate is not None and gate.startswith("stale_data")


def test_insufficient_candles_blocks(engine):
    gate = engine._data_gate(_snapshot(candle_meta={"count": 10}))
    assert gate == "insufficient_candles:10"


def test_missing_indicators_block(engine):
    gate = engine._data_gate(
        _snapshot(indicators={"available": False, "values": {}, "missing": ["ema"]})
    )
    assert gate == "indicators_unavailable"


def test_low_indicator_coverage_blocks(engine):
    snapshot = _snapshot(
        indicators={
            "available": True,
            "values": {"ema": 1},
            "missing": ["rsi", "atr", "macd", "adx"],
        }
    )
    gate = engine._data_gate(snapshot)
    assert gate is not None and gate.startswith("indicator_coverage")


def test_critical_indicator_missing_blocks(engine):
    snapshot = _snapshot(
        indicators={
            "available": True,
            "values": {"ema": 1, "rsi": 2, "atr": 3, "macd": 4},
            "missing": [],
            "critical_missing": ["atr"],
        }
    )
    assert engine._data_gate(snapshot) == "critical_indicators_missing"


def test_quote_missing_blocks(engine):
    gate = engine._data_gate(_snapshot(quote={"ltp": None, "timestamp": mt.ist_now().isoformat()}))
    assert gate == "quote_missing"


def test_stale_quote_blocks(engine):
    old = (mt.ist_now() - timedelta(minutes=10)).isoformat()
    gate = engine._data_gate(_snapshot(quote={"ltp": 100.0, "timestamp": old}))
    assert gate == "quote_stale"


def test_latest_value_extraction():
    assert _latest_value({"series": {"x": [1.0, None, 3.0]}}) == 3.0
    assert _latest_value({"levels": {"s1": 5}, "meta": {}}) == 5
    assert _latest_value({"status": "insufficient_data", "series": {}}) is None
    assert _latest_value(None) is None
    assert _latest_value(7) == 7.0


def test_unavailable_indicators_are_declared_not_guessed():
    """Indicators without a provider feed must be listed, never computed."""
    assert "volume_profile" in UNAVAILABLE_WITHOUT_FEED
    assert UNAVAILABLE_WITHOUT_FEED.isdisjoint({"ema", "rsi", "atr"})


def test_no_trade_reason_is_recorded_when_gate_fires():
    engine = DecisionEngine()
    gate = engine._data_gate(_snapshot(quote={"ltp": None, "timestamp": mt.ist_now().isoformat()}))
    assert gate == "quote_missing"
    assert NO_TRADE == "NO_TRADE"
