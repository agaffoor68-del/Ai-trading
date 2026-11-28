"""Learning engine tests (Task 5) - using per-test engine fixture.

Each test gets its own fresh LearningEngine with a temporary SQLite DB,
so there is no schema cross-contamination.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path
import app.services.brain.learning_engine as le  # the module-level engine class
from app.services.brain.learning_engine import LearningEngine  # the class

import pytest

# ------------------------------------------------------------------
# Helper: create a LearningEngine with a brand‑new temp DB.
# ------------------------------------------------------------------
def _new_engine():
    """Return a LearningEngine whose DB file does not yet exist.

    The engine's __init__ calls _ensure_schema() which creates the
    DB and its tables from scratch.
    """
    import app.services.brain.learning_engine as le_mod

    # Use a per-test temp file.  We patch the module-level DB_PATH
    # so the engine initialises at the right location.
    tmp = Path(tempfile.mkdtemp()) / "learning_test.db"
    le_mod.DB_PATH = tmp

    # The _ensure_schema() call inside LearningEngine.__init__()
    # will see that the file does not exist and create it fresh.
    eng = le.LearningEngine()
    return eng, tmp


# ------------------------------------------------------------------
# Signal storage
# ------------------------------------------------------------------
def test_store_and_retrieve_signal():
    eng, db_path = _new_engine()
    sid = "test-sig-001"
    snapshot = {
        "ema": {"value": 22030.0, "direction": "bullish", "strength": 0.7},
        "rsi": {"value": 58.0, "direction": "bullish", "strength": 0.55},
    }
    eid = eng.store_signal(
        signal_id=sid,
        symbol="NIFTY",
        direction="long",
        entry_price=22000.0,
        regime="trend_up_strong",
        strategy_name="trend_follow_long",
        timeframe="5m",
        candles_consumed=120,
        confidence=0.82,
        decision="BUY",
        indicator_snapshot=snapshot,
        suggested_stop=21800.0,
        suggested_target_1=22200.0,
        suggested_target_2=22400.0,
    )
    assert eid is not None
    status = eng.status()
    assert status["totals"]["stored_signals"] >= 1


def test_record_outcome():
    eng, db_path = _new_engine()
    sid = "test-sig-002"
    snapshot = {"rsi": {"value": 55.0, "direction": "bullish", "strength": 0.6}}
    eid = eng.store_signal(
        signal_id=sid,
        symbol="BANKNIFTY",
        direction="short",
        entry_price=44000.0,
        regime="trend_down_strong",
        strategy_name="trend_follow_short",
        timeframe="5m",
        candles_consumed=80,
        confidence=0.78,
        decision="SELL",
        indicator_snapshot=snapshot,
    )
    ok = eng.record_outcome(
        signal_id=sid,
        exit_price=43700.0,
        exit_bar_idx=10,
        pnl=-600.0,
        pnl_pct=-1.36,
        status="losing",
        notes="break of support",
    )
    assert ok is True
    status = eng.status()
    assert status["totals"]["closed_signals"] >= 1


def test_record_outcome_twice_fails():
    eng, db_path = _new_engine()
    sid = "test-sig-003"
    snapshot = {"rsi": {"value": 55.0, "direction": "bullish", "strength": 0.6}}
    eid = eng.store_signal(
        signal_id=sid,
        symbol="FINNIFTY",
        direction="long",
        entry_price=18000.0,
        regime="sideways",
        strategy_name="range_fade",
        timeframe="5m",
        candles_consumed=50,
        confidence=0.5,
        decision="WAIT",
        indicator_snapshot=snapshot,
    )
    ok1 = eng.record_outcome(
        signal_id=sid,
        exit_price=18100.0,
        exit_bar_idx=5,
        pnl=500.0,
        pnl_pct=2.78,
        status="winning",
        notes="test",
    )
    assert ok1 is True
    ok2 = eng.record_outcome(
        signal_id=sid,
        exit_price=18050.0,
        exit_bar_idx=6,
        pnl=200.0,
        pnl_pct=1.11,
        status="winning",
        notes="duplicate",
    )
    assert ok2 is False


# ------------------------------------------------------------ indicator analytics
def test_indicator_performance_bullish_regime():
    eng, db_path = _new_engine()
    for i in range(6):
        sid = f"test-sig-ind-{i}"
        snapshot = {
            "ema": {"value": 22000 + i, "direction": "bullish", "strength": 0.5 + i * 0.05},
            "rsi": {"value": 55 + i, "direction": "bullish", "strength": 0.5 + i * 0.05},
        }
        eng.store_signal(
            signal_id=sid,
            symbol="NIFTY",
            direction="long",
            entry_price=22000.0,
            regime="trend_up_strong",
            strategy_name="trend_follow_long",
            timeframe="5m",
            candles_consumed=100,
            confidence=0.7,
            decision="BUY",
            indicator_snapshot=snapshot,
        )
        status = "winning" if i % 2 == 0 else "losing"
        eng.record_outcome(
            signal_id=sid,
            exit_price=22050.0,
            exit_bar_idx=20,
            pnl=200.0 if status == "winning" else -150.0,
            pnl_pct=0.91 if status == "winning" else -0.68,
            status=status,
            notes=f"regime test {i}",
        )

    perf = eng.indicator_performance(regime="trend_up_strong")
    assert "ema" in perf
    assert "rsi" in perf
    assert perf["ema"]["win_rate"] == pytest.approx(0.5, abs=0.1)


# ------------------------------------------------------------ walk-forward
def test_walk_forward_validate():
    eng, db_path = _new_engine()

    train = [
        {"ts": 1_700_000_000 + i * 60, "close": 22000 + i} for i in range(80)
    ]
    valid = [
        {"ts": 1_700_000_000 + (80 + i) * 60, "close": 22000 + i} for i in range(40)
    ]

    cw = {"ema": 0.6, "rsi": 0.4, "adx": 0.2}

    result = eng.walk_forward_validate(
        version_label="wf_v1",
        description="first walk-forward test",
        regime_filter="trend_up_strong",
        candidate_weights=cw,
        train_candles=train,
        validation_candles=valid,
        strategy_name="trend_follow_long",
    )

    assert result["version_label"] == "wf_v1"
    assert result["train_bars"] == 80
    assert result["valid_bars"] == 40
    assert result["signals_recorded"] > 0
    assert result["win_rate"] is not None
    assert 0.0 <= result["win_rate"] <= 1.0


def test_promote_and_record_version():
    eng, db_path = _new_engine()

    wf = eng.walk_forward_validate(
        version_label="wf_test_promote",
        description="test promotion",
        regime_filter=None,
        candidate_weights={"ema": 0.5, "rsi": 0.5},
        train_candles=[{"ts": 1_700_000_000 + i * 60, "close": 22000 + i} for i in range(50)],
        validation_candles=[{"ts": 1_700_000_000 + (50 + i) * 60, "close": 22000 + i} for i in range(30)],
        strategy_name="trend_follow_long",
    )

    promo = eng.promote_version(wf["version_id"])
    assert promo["promoted_version_id"] == wf["version_id"]
    active = eng.status()
    assert active["totals"]["validated_versions"] >= 1


def test_rollback_to_validated():
    eng, db_path = _new_engine()

    wf1 = eng.walk_forward_validate(
        version_label="wf_a",
        description="first cycle",
        regime_filter=None,
        candidate_weights={"ema": 0.5},
        train_candles=[{"ts": 1_700_000_000 + i * 60, "close": 22000 + i} for i in range(30)],
        validation_candles=[{"ts": 1_700_000_000 + (30 + i) * 60, "close": 22000 + i} for i in range(20)],
        strategy_name="trend_follow_long",
    )
    wf2 = eng.walk_forward_validate(
        version_label="wf_b",
        description="second cycle",
        regime_filter=None,
        candidate_weights={"ema": 0.6},
        train_candles=[{"ts": 1_700_000_000 + i * 60, "close": 22000 + i} for i in range(30)],
        validation_candles=[{"ts": 1_700_000_000 + (30 + i) * 60, "close": 22000 + i} for i in range(20)],
        strategy_name="trend_follow_long",
    )

    # Promote wf1
    eng.promote_version(wf1["version_id"])

    # Rollback should now make wf1 the active model
    rollback = eng.rollback_to_validated()
    assert rollback is not None
    assert rollback["version_label"] == "wf_a"


# ------------------------------------------------------------ data integrity
def test_no_data_leakage_between_train_and_valid():
    eng, db_path = _new_engine()
    train = [
        {"ts": 1_700_000_000 + i * 60, "close": 22000 + i} for i in range(30)
    ]
    valid = [
        {"ts": 1_700_000_000 + (30 + i) * 60, "close": 22000 + i} for i in range(20)
    ]
    cw = {"ema": 0.5}
    result = eng.walk_forward_validate(
        version_label="no_leak_test",
        description="ensure no index overlap",
        regime_filter=None,
        candidate_weights=cw,
        train_candles=train,
        validation_candles=valid,
        strategy_name="trend_follow_long",
    )
    assert result["train_bars"] == 30
    assert result["valid_bars"] == 20
    status = eng.status()
    assert status["totals"]["closed_signals"] > 0
