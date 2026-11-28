"""Tests for the synchronised multi-timeframe pipeline (Task 1).

These tests use deterministic synthetic candles only as *fixtures* for the
normalisation/quality logic — they never assert on market behaviour and never
replace a provider response in application code.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytest

from app.core import market_time as mt
from app.services.brain import multi_timeframe as mtf


IST = mt.IST


def _session_start(day_offset: int = 0) -> datetime:
    """09:15 IST on a recent weekday (fixture anchor)."""
    base = datetime(2024, 3, 4, 9, 15, tzinfo=IST) + timedelta(days=day_offset)
    return base


def make_candles(count: int, timeframe: str = "5m", start: datetime | None = None) -> list[dict]:
    """Build ``count`` clean candles starting at a session open."""
    step = mtf.bar_seconds(timeframe)
    begin = start or _session_start()
    out = []
    for i in range(count):
        ts = int((begin + timedelta(seconds=step * i)).timestamp())
        price = 22000.0 + i
        out.append(
            {
                "ts": ts,
                "open": price,
                "high": price + 5,
                "low": price - 5,
                "close": price + 2,
                "volume": 1000 + i,
            }
        )
    return out


# ---------------------------------------------------------------- normalisation
def test_duplicate_candles_are_dropped_and_counted():
    candles = make_candles(10, "5m")
    candles.append(dict(candles[4]))  # duplicate ts

    clean, report = mtf.normalize_candles(candles, "5m", reference=datetime.now(IST))

    assert len(clean) == 10
    assert report.duplicates == 1
    assert report.received == 11


def test_invalid_candles_are_rejected():
    candles = make_candles(5, "5m")
    broken = dict(candles[2])
    broken["high"] = broken["low"] - 10  # high < low
    candles.append(broken)

    clean, report = mtf.normalize_candles(candles, "5m", reference=datetime.now(IST))

    assert len(clean) == 5
    assert report.invalid == 1


def test_out_of_order_candles_are_sorted():
    candles = make_candles(6, "5m")
    shuffled = [candles[3], candles[0], candles[5], candles[1], candles[4], candles[2]]

    clean, report = mtf.normalize_candles(shuffled, "5m", reference=datetime.now(IST))

    stamps = [c["ts"] for c in clean]
    assert stamps == sorted(stamps)
    assert report.out_of_order >= 1


def test_incomplete_bar_is_dropped_to_prevent_look_ahead():
    """The still-forming bar must never be exposed as a completed candle."""
    now = datetime.now(IST)
    # Bar that started 10 seconds ago: nowhere near closed for a 5m timeframe.
    forming = {
        "ts": int((now - timedelta(seconds=10)).timestamp()),
        "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 10,
    }
    closed = make_candles(3, "5m", start=now - timedelta(hours=2))

    clean, report = mtf.normalize_candles(closed + [forming], "5m", reference=now)

    assert report.incomplete_dropped == 1
    assert forming["ts"] not in [c["ts"] for c in clean]


def test_keep_incomplete_is_explicit_opt_in():
    now = datetime.now(IST)
    forming = {
        "ts": int((now - timedelta(seconds=10)).timestamp()),
        "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 10,
    }

    clean, report = mtf.normalize_candles([forming], "5m", reference=now, keep_incomplete=True)

    assert len(clean) == 1
    assert report.incomplete_dropped == 0


# ---------------------------------------------------------------------- gaps
def test_detect_gaps_finds_missing_bars_within_a_session():
    # Three consecutive sessions: only interior days can be judged for gaps.
    candles = []
    for offset in range(3):
        candles.extend(make_candles(75, "5m", start=_session_start(offset)))
    del candles[80:85]  # remove 5 bars from the middle (interior) day

    gaps = mtf.detect_gaps(candles, "5m")

    assert gaps["expected_per_session"] == 75
    assert gaps["missing_bars"] == 5
    assert gaps["gap_days"]


def test_detect_gaps_clean_series_reports_none():
    candles = []
    for offset in range(3):
        candles.extend(make_candles(75, "5m", start=_session_start(offset)))

    gaps = mtf.detect_gaps(candles, "5m")

    assert gaps["missing_bars"] == 0


def test_detect_gaps_ignores_partial_edge_days():
    """A window that starts mid-session must not report phantom gaps."""
    candles = make_candles(60, "5m")  # single, partial day

    gaps = mtf.detect_gaps(candles, "5m")

    assert gaps["missing_bars"] == 0
    assert gaps["days_covered"] == 1


# --------------------------------------------------------------- assessment
def test_assess_timeframe_reports_no_data():
    series = mtf.assess_timeframe("NIFTY", "5m", [], market_open=True)

    assert series.quality.status == "no_data"
    assert series.quality.usable is False
    assert series.candles == []


def test_assess_timeframe_flags_insufficient_history():
    candles = make_candles(5, "5m")

    series = mtf.assess_timeframe(
        "NIFTY", "5m", candles, reference=datetime.now(IST), min_candles=20, market_open=True
    )

    assert series.quality.status == "insufficient"
    assert "required" in (series.quality.reason or "")


def test_assess_timeframe_flags_stale_feed():
    """A feed whose last bar closed long ago must be rejected while open."""
    now = datetime.now(IST)
    candles = make_candles(60, "5m", start=now - timedelta(hours=6))

    series = mtf.assess_timeframe(
        "NIFTY", "5m", candles, reference=now, min_candles=20, market_open=True
    )

    assert series.quality.status == "stale"
    assert series.quality.usable is False


def test_assess_timeframe_accepts_fresh_series():
    now = datetime.now(IST)
    # 60 bars ending with a bar that closed ~1 minute ago.
    start = now - timedelta(minutes=5 * 60 + 1)
    candles = make_candles(60, "5m", start=start)

    series = mtf.assess_timeframe(
        "NIFTY", "5m", candles, reference=now, min_candles=20, market_open=True
    )

    assert series.quality.status == "ok"
    assert series.quality.usable is True


def test_market_closed_series_is_usable_not_stale():
    now = datetime.now(IST)
    candles = make_candles(60, "5m", start=now - timedelta(hours=10))

    series = mtf.assess_timeframe(
        "NIFTY", "5m", candles, reference=now, min_candles=20, market_open=False
    )

    assert series.quality.status == "market_closed"
    assert series.quality.usable is True


# ---------------------------------------------------------- synchronisation
def _series(tf: str, count: int, start: datetime) -> mtf.TimeframeSeries:
    candles = make_candles(count, tf, start=start)
    return mtf.assess_timeframe(
        "NIFTY", tf, candles, reference=datetime.now(IST), min_candles=5, market_open=False
    )


def test_synchronize_detects_aligned_timeframes():
    start = _session_start()
    series = {
        "5m": _series("5m", 30, start),
        "15m": _series("15m", 30, start),
    }

    report = mtf.synchronize(series)

    assert report.usable_timeframes
    assert report.skew_seconds is not None


def test_synchronize_reports_blocked_timeframes_with_reason():
    start = _session_start()
    series = {
        "5m": _series("5m", 30, start),
        "15m": mtf.assess_timeframe("NIFTY", "15m", [], market_open=True),
    }

    report = mtf.synchronize(series)

    assert "15m" in report.blocked_timeframes
    assert report.reasons["15m"]
    assert report.aligned is False


def test_synchronize_handles_no_usable_timeframes():
    series = {"5m": mtf.assess_timeframe("NIFTY", "5m", [], market_open=True)}

    report = mtf.synchronize(series)

    assert report.aligned is False
    assert report.usable_timeframes == []
    assert report.as_of is None


# -------------------------------------------------------------- snapshot IO
def test_build_snapshot_uses_injected_loader():
    """The pipeline must be testable without touching the network."""
    start = _session_start()

    async def fake_loader(symbol, timeframe, limit):
        return make_candles(60, timeframe, start=start)

    snapshot = asyncio.run(
        mtf.build_snapshot(
            "NIFTY",
            timeframes=["5m", "15m"],
            loader=fake_loader,
            reference=datetime.now(IST),
            min_candles=5,
            market_open=False,
        )
    )

    assert snapshot.symbol == "NIFTY"
    assert set(snapshot.timeframes) == {"5m", "15m"}
    assert snapshot.usable is True


def test_build_snapshot_survives_provider_exception():
    async def failing_loader(symbol, timeframe, limit):
        raise RuntimeError("token expired")

    snapshot = asyncio.run(
        mtf.build_snapshot(
            "NIFTY",
            timeframes=["5m"],
            loader=failing_loader,
            reference=datetime.now(IST),
            market_open=True,
        )
    )

    item = snapshot.timeframes["5m"]
    assert item.quality.status == "no_data"
    assert "token expired" in (item.quality.reason or "")
    assert snapshot.usable is False


def test_data_quality_report_is_json_safe():
    start = _session_start()

    async def fake_loader(symbol, timeframe, limit):
        return make_candles(40, timeframe, start=start)

    snapshot = asyncio.run(
        mtf.build_snapshot(
            "NIFTY",
            timeframes=["5m"],
            loader=fake_loader,
            reference=datetime.now(IST),
            min_candles=5,
            market_open=False,
        )
    )
    report = mtf.data_quality_report(snapshot)

    import json

    encoded = json.dumps(report)  # must not raise
    assert "sync" in encoded


def test_bar_helpers():
    assert mtf.bar_seconds("5m") == 300
    assert mtf.bar_seconds("1d") == 86400
    ts = int(datetime(2024, 3, 4, 9, 15, tzinfo=IST).timestamp())
    assert mtf.bar_close_ts(ts, "15m") == ts + 900
    assert mtf.expected_bars_per_session("5m") == 75
    assert mtf.expected_bars_per_session("15m") == 25
    assert mtf.expected_bars_per_session("1d") == 1
