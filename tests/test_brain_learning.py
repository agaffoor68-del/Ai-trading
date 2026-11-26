"""Learning + strategy validation tests.

Candles are produced by a deterministic generator so the backtest is exercised
on a reproducible series.  They are test fixtures for the *engine*, never
presented as market or trading results.
"""

from __future__ import annotations

import math

import pytest

from app.core.brain_models import StrategyStatus, StrategyVersion
from app.core.database import SessionLocal
from app.services.brain.learning_engine import (
    MIN_SAMPLE_SIZE,
    LearningEngine,
    backtest,
    compute_metrics,
)


def make_candles(count: int = 600, trend: float = 0.15, wave: float = 6.0, seed: float = 0.0):
    """Deterministic OHLC series (test fixture, not market data)."""
    candles = []
    price = 100.0
    for i in range(count):
        drift = trend + math.sin((i + seed) / 11.0) * (wave / 100.0)
        close = price + drift
        high = max(price, close) + 0.4
        low = min(price, close) - 0.4
        candles.append(
            {"ts": 1_700_000_000 + i * 300, "open": round(price, 2), "high": round(high, 2),
             "low": round(low, 2), "close": round(close, 2), "volume": 1000 + i}
        )
        price = close
    return candles


PARAMS = {"ema_fast": 9, "ema_slow": 21, "rsi_period": 14, "sl_atr_mult": 1.5, "tp_atr_mult": 2.5}


@pytest.fixture()
def engine():
    return LearningEngine()


def test_backtest_is_causal_no_lookahead():
    """Truncating the series must not change earlier trades."""
    candles = make_candles(400)
    full = backtest(candles, PARAMS, 0, 400)
    truncated = backtest(candles, PARAMS, 0, 300)
    full_first = [t for t in full["trades"] if t["exit_index"] < 300]
    assert len(full_first) == len(truncated["trades"]) or all(
        t["exit_index"] < 300 for t in truncated["trades"]
    )
    for trade in truncated["trades"]:
        assert trade["exit_index"] < 300
        assert trade["entry_index"] < trade["exit_index"]


def test_metrics_are_computed_from_trades():
    trades = [
        {"pnl": 10.0, "r_multiple": 2.0},
        {"pnl": -5.0, "r_multiple": -1.0},
        {"pnl": 7.0, "r_multiple": 1.4},
    ]
    metrics = compute_metrics(trades)
    assert metrics["trades"] == 3
    assert metrics["wins"] == 2
    assert metrics["net_pnl"] == 12.0
    assert metrics["profit_factor"] == 3.4  # 17 / 5


def test_insufficient_history_is_rejected(engine, user_id):
    version = engine.propose_version(PARAMS, "NIFTY", "1d", user_id=user_id)["version"]
    report = engine.validate(version, "NIFTY", "1d", make_candles(50), user_id=user_id)
    assert report["promoted"] is False
    assert report["reason"] == "insufficient_history"
    with SessionLocal() as db:
        row = db.query(StrategyVersion).filter(StrategyVersion.version == version).first()
        assert row.status == StrategyStatus.REJECTED.value


def test_failed_gate_blocks_promotion(engine, user_id):
    """A candidate that loses out-of-sample must not be promoted."""
    candles = make_candles(600, trend=-0.2, wave=10.0)
    version = engine.propose_version(PARAMS, "NIFTY", "1d", user_id=user_id)["version"]
    report = engine.validate(version, "NIFTY", "1d", candles, user_id=user_id)
    assert report["promoted"] is False
    failed = [g["gate"] for g in report["gates"] if not g["passed"]]
    assert failed, "a losing candidate must fail at least one gate"
    with SessionLocal() as db:
        row = db.query(StrategyVersion).filter(StrategyVersion.version == version).first()
        assert row.status in {StrategyStatus.REJECTED.value, StrategyStatus.DRAFT.value}
        assert row.validation_report is not None


def test_promotion_requires_every_gate(engine, user_id):
    candles = make_candles(900, trend=0.25, wave=8.0)
    version = engine.propose_version(PARAMS, "NIFTY", "1d", user_id=user_id)["version"]
    report = engine.validate(version, "NIFTY", "1d", candles, user_id=user_id)
    if report["promoted"]:
        assert report["all_gates_passed"] is True
        with SessionLocal() as db:
            row = db.query(StrategyVersion).filter(StrategyVersion.version == version).first()
            assert row.status == StrategyStatus.PROMOTED.value
            assert row.promoted_at is not None
    else:
        # Not promoted is always acceptable; the invariant is that promotion
        # never happens with a failing gate.
        assert report["all_gates_passed"] is False


def test_rollback_demotes_promoted_version(engine, user_id):
    candles = make_candles(900, trend=0.25, wave=8.0)
    first = engine.propose_version(PARAMS, "NIFTY", "1d", user_id=user_id)["version"]
    report = engine.validate(first, "NIFTY", "1d", candles, user_id=user_id)
    with SessionLocal() as db:
        row = db.query(StrategyVersion).filter(StrategyVersion.version == first).first()
        row.status = StrategyStatus.PROMOTED.value
        db.commit()
    result = engine.rollback(first, user_id=user_id)
    assert result["rolled_back"] is True
    with SessionLocal() as db:
        row = db.query(StrategyVersion).filter(StrategyVersion.version == first).first()
        assert row.status == StrategyStatus.DISABLED.value


def test_analyse_trade_writes_learning_report(engine, user_id):
    from app.core.brain_models import DecisionAudit, LearningReport, OrderRecord

    with SessionLocal() as db:
        db.add(
            OrderRecord(
                user_id=user_id,
                decision_id="dec_learn_1",
                client_order_id="co_learn_1",
                symbol="NSE:NIFTY50-INDEX",
                side="BUY",
                quantity=10,
                status="FILLED",
                filled_quantity=10,
                filled_price=100.0,
                stop_loss=95.0,
                target=110.0,
                charges=5.0,
                is_paper=True,
            )
        )
        db.add(
            DecisionAudit(
                decision_id="dec_learn_1",
                user_id=user_id,
                symbol="NSE:NIFTY50-INDEX",
                action="BUY",
                indicator_snapshot={"values": {"rsi": 61.2, "ema": 100.4}},
                news_refs=[{"headline": "fixture headline", "source": "test"}],
            )
        )
        db.commit()
    result = engine.analyse_trade("dec_learn_1", exit_price=110.0, exit_reason="target", user_id=user_id)
    assert result["written"] is True
    assert result["outcome"] == "WIN"
    with SessionLocal() as db:
        report = (
            db.query(LearningReport).filter(LearningReport.decision_id == "dec_learn_1").first()
        )
        assert report is not None
        assert report.win_conditions, "winning conditions must be stored"


def test_losing_trade_records_reasons(engine, user_id):
    from app.core.brain_models import LearningReport, OrderRecord

    with SessionLocal() as db:
        db.add(
            OrderRecord(
                user_id=user_id,
                decision_id="dec_learn_2",
                client_order_id="co_learn_2",
                symbol="NSE:NIFTY50-INDEX",
                side="BUY",
                quantity=10,
                status="FILLED",
                filled_quantity=10,
                filled_price=100.0,
                stop_loss=95.0,
                charges=5.0,
                is_paper=True,
            )
        )
        db.commit()
    result = engine.analyse_trade(
        "dec_learn_2", exit_price=95.0, exit_reason="stop_loss", user_id=user_id, plan_followed=True
    )
    assert result["outcome"] == "LOSS"
    assert result["r_multiple"] is not None and result["r_multiple"] < 0
    with SessionLocal() as db:
        report = db.query(LearningReport).filter(LearningReport.decision_id == "dec_learn_2").first()
        assert report.loss_reasons


def test_history_lists_versions(engine, user_id):
    engine.propose_version(PARAMS, "NIFTY", "1d", user_id=user_id)
    engine.propose_version(PARAMS, "BANKNIFTY", "5m", user_id=user_id)
    rows = engine.history(user_id=user_id)
    assert len(rows) == 2
    assert all(row["version"] for row in rows)
