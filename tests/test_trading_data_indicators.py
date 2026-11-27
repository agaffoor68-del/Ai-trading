"""Tests for TradingDataService.calculate_indicators.

The AI Brain builds its Grok context from this method.  It previously imported
``pandas_ta`` and ``app.services.indicator_engine`` — neither of which exists in
this repository — so every call raised ``ModuleNotFoundError`` and the context
was assembled with no technical indicators.  ``build_context`` uses
``asyncio.gather(return_exceptions=True)``, so the failure was silent.

These tests drive the real method with a stubbed candle source and assert that
real indicator values come back.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.trading_data_service import (  # noqa: E402
    CandleData,
    TradingDataService,
)


def make_candles(count=120, start=1_700_000_000, step=900):
    candles = []
    price = 100.0
    for i in range(count):
        price += 0.25 if i % 3 else -0.1
        candles.append(
            CandleData(
                time=start + i * step,
                open=price,
                high=price * 1.004,
                low=price * 0.996,
                close=price,
                volume=1500,
            )
        )
    return candles


@pytest.fixture()
def service(monkeypatch):
    svc = TradingDataService()
    supplied = {"candles": make_candles()}

    async def _get_candles(symbol, interval="5m", lookback=100):
        return supplied["candles"]

    monkeypatch.setattr(svc, "get_candles", _get_candles)
    svc.supplied = supplied
    return svc


def test_calculate_indicators_returns_real_values(service):
    results = asyncio.run(service.calculate_indicators("NSE:NIFTY50-INDEX", "15m"))

    assert results, "the engine must produce values, not raise ModuleNotFoundError"
    by_name = {r.name for r in results}
    # A few well-known indicators must be present with a numeric value.
    for expected in ("RSI", "MACD", "EMA"):
        assert expected in by_name, expected
    rsi = next(r for r in results if r.name == "RSI")
    assert rsi.value is not None and 0.0 <= rsi.value <= 100.0
    assert rsi.category == "momentum"
    assert rsi.timestamp


def test_indicator_names_filter_is_honoured(service):
    results = asyncio.run(
        service.calculate_indicators(
            "NSE:NIFTY50-INDEX", "15m", indicator_names=["rsi", "atr"]
        )
    )

    assert {r.name for r in results} == {"RSI", "ATR"}


def test_unknown_indicator_name_is_ignored_not_fatal(service):
    results = asyncio.run(
        service.calculate_indicators(
            "NSE:NIFTY50-INDEX", "15m", indicator_names=["rsi", "no_such_indicator"]
        )
    )

    assert {r.name for r in results} == {"RSI"}


def test_category_filter_is_honoured(service):
    results = asyncio.run(
        service.calculate_indicators("NSE:NIFTY50-INDEX", "15m", category="momentum")
    )

    assert results
    assert all(r.category == "momentum" for r in results)


def test_insufficient_history_returns_empty_list(service):
    service.supplied["candles"] = make_candles(count=5)

    assert asyncio.run(service.calculate_indicators("NSE:NIFTY50-INDEX", "15m")) == []


def test_no_candles_returns_empty_list(service):
    service.supplied["candles"] = []

    assert asyncio.run(service.calculate_indicators("NSE:NIFTY50-INDEX", "15m")) == []


def test_values_dict_carries_every_series(service):
    results = asyncio.run(
        service.calculate_indicators(
            "NSE:NIFTY50-INDEX", "15m", indicator_names=["macd"]
        )
    )

    macd = results[0]
    assert macd.value is not None
    # MACD is multi-output; the series must be exposed, not just one number.
    assert set(macd.values) >= {"macd", "signal"}


def test_no_pandas_ta_or_phantom_module_is_imported(service):
    """Guards the regression: the method must not depend on pandas_ta."""
    source = (ROOT / "app" / "services" / "trading_data_service.py").read_text()
    body = source.split("async def calculate_indicators", 1)[1].split(
        "async def ", 1
    )[0]
    assert "import pandas_ta" not in body
    assert "from app.services.indicator_engine import" not in body
