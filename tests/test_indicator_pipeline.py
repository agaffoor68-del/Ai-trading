"""Tests for candle validation and indicator assembly (Parts 1, 3, 5).

The engine itself is covered by ``test_indicators.py``.  These tests cover the
layer between the provider and the engine: malformed candles must be dropped,
never smoothed over, and a symbol with no history must be reported as
``data_available: false`` rather than producing numbers.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import indicator_service as isvc  # noqa: E402
from app.services.indicators import get_engine  # noqa: E402

ENGINE = get_engine()


def candle(ts, o=100.0, h=101.0, l=99.0, c=100.5, v=1000):
    return {"ts": ts, "open": o, "high": h, "low": l, "close": c, "volume": v}


def series(n=120, start=1_700_000_000, step=900):
    """A gently rising series so RSI/EMAs are well defined."""
    out = []
    price = 100.0
    for i in range(n):
        price += 0.25 if i % 3 else -0.1
        out.append(candle(start + i * step, price, price * 1.004, price * 0.996, price, 1500))
    return out


# ------------------------------------------------------------ candle validation
def test_valid_candle_is_accepted():
    assert isvc.validate_candle(candle(1)) is True


def test_candle_with_inverted_high_low_is_rejected():
    assert isvc.validate_candle(candle(1, o=100, h=99, l=101, c=100)) is False


def test_candle_with_close_outside_range_is_rejected():
    assert isvc.validate_candle(candle(1, o=100, h=101, l=99, c=150)) is False


def test_candle_with_nan_is_rejected():
    assert isvc.validate_candle(candle(1, c=float("nan"))) is False


def test_candle_with_infinity_is_rejected():
    assert isvc.validate_candle(candle(1, h=float("inf"))) is False


def test_candle_with_non_positive_price_is_rejected():
    assert isvc.validate_candle(candle(1, o=0, h=0, l=0, c=0)) is False


def test_candle_with_bad_timestamp_is_rejected():
    assert isvc.validate_candle(candle(0)) is False


def test_candle_with_negative_volume_is_rejected():
    assert isvc.validate_candle(candle(1, v=-5)) is False


def test_non_dict_candle_is_rejected():
    assert isvc.validate_candle([1, 2, 3]) is False
    assert isvc.validate_candle(None) is False


# -------------------------------------------------------------- assemble output
def test_assemble_reports_data_unavailable_without_candles():
    result = isvc.assemble(ENGINE, "NSE:NIFTY50-INDEX", "5m", ["rsi"], None, [])

    assert result["data_available"] is False
    assert result["candles"] == 0
    assert result["results"] == {}
    assert "unavailable" in result["message"].lower()


def test_assemble_drops_invalid_candles_and_counts_them():
    candles = series(60) + [candle(1_700_999_999, c=float("nan"))]

    result = isvc.assemble(ENGINE, "NSE:NIFTY50-INDEX", "5m", ["rsi"], None, candles)

    assert result["data_available"] is True
    assert result["candles"] == 60
    assert result["rejected_candles"] == 1


def test_assemble_reports_unavailable_when_every_candle_is_invalid():
    bad = [candle(i, c=float("nan")) for i in range(5)]

    result = isvc.assemble(ENGINE, "NSE:NIFTY50-INDEX", "5m", ["rsi"], None, bad)

    assert result["data_available"] is False
    assert result["results"] == {}
    assert "failed validation" in result["message"]


def test_assemble_returns_real_indicator_values():
    candles = series(150)

    result = isvc.assemble(ENGINE, "NSE:NIFTY50-INDEX", "15m", ["rsi", "ema"], None, candles)

    rsi = result["results"]["rsi"]["series"]["rsi"][-1]
    ema = result["results"]["ema"]["series"]["ema"][-1]
    assert rsi is not None and 0.0 <= rsi <= 100.0
    assert ema is not None and ema > 0
    assert result["last_close"] == candles[-1]["close"]


def test_assemble_stamps_calculation_time_and_as_of():
    result = isvc.assemble(ENGINE, "NSE:NIFTY50-INDEX", "5m", ["rsi"], None, series(40))

    assert result["calculated_at"]
    assert result["as_of"] == result["as_of"]
    assert isinstance(result["as_of"], int)


def test_unknown_indicator_is_reported_not_raised():
    result = isvc.assemble(ENGINE, "NSE:NIFTY50-INDEX", "5m", ["not_an_indicator"], None, series(40))

    assert "error" in result["results"]["not_an_indicator"]
    assert result["results"]["not_an_indicator"]["status"] == "not_implemented"


# --------------------------------------------------------------- interval mapping
def test_interval_normalisation_rejects_unknown():
    try:
        isvc.normalize_interval("7m")
    except ValueError as exc:
        assert "Unsupported interval" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("7m must not be accepted")


def test_supported_intervals_map_to_fyers_resolutions():
    for interval in ("1m", "5m", "15m", "1h", "4h", "1d", "1wk", "1mo"):
        assert isvc.normalize_interval(interval) in isvc.RESOLUTION_BY_INTERVAL


# ------------------------------------------------- brain indicator set is present
def test_brain_default_indicators_all_exist():
    from app.services.brain.data_intelligence import DEFAULT_BRAIN_INDICATORS

    missing = [i for i in DEFAULT_BRAIN_INDICATORS if i not in isvc.REGISTRY]
    assert missing == []


def test_documented_indicator_list_is_available():
    """Every indicator named in the requirements must be in the registry."""
    required = [
        "rsi", "macd", "ema", "sma", "vwap", "bollinger", "atr", "adx",
        "supertrend", "stochrsi", "obv", "mfi", "volume_profile",
        "ichimoku", "fibonacci_retracement", "pivot_points",
    ]
    missing = [name for name in required if name not in isvc.REGISTRY]
    assert missing == [], f"missing indicators: {missing}"


def test_indicator_results_are_json_serialisable():
    import json

    result = isvc.assemble(ENGINE, "NSE:NIFTY50-INDEX", "5m", ["rsi", "macd"], None, series(80))
    encoded = json.dumps(result, default=str)
    assert "rsi" in encoded
