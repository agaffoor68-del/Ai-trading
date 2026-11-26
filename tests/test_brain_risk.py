"""Risk engine tests: limits, kill switch, duplicate orders, stale data.

Every assertion is about a decision the engine itself produced; no broker,
model or market data is simulated as if it were real.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core import market_time as mt
from app.core.brain_models import OrderRecord
from app.core.database import SessionLocal
from app.services.brain.risk_engine import RiskEngine, get_risk_engine


def _fresh_quote():
    return {"quote": {"ltp": 100.0, "bid": 99.9, "ask": 100.1, "timestamp": mt.ist_now().isoformat(),
                      "source": "test_fixture"}}


def _proposal(**overrides):
    base = {
        "symbol": "NSE:NIFTY50-INDEX",
        "side": "BUY",
        "quantity": 10,
        "price": 100.0,
        "stop_loss": 95.0,
        "target": 110.0,
        "client_order_id": "test-order-1",
        "decision_id": "dec_test_1",
    }
    base.update(overrides)
    return base


@pytest.fixture()
def engine():
    return RiskEngine()


def _tradeable_moment():
    """A weekday inside the configured 09:20-15:10 risk session."""
    from datetime import datetime

    moment = mt.ist_now()
    if not mt.is_market_open("NSE", moment):
        # Move to the next weekday 10:00 IST without touching real time.
        day = moment.astimezone(mt.IST)
        while day.weekday() >= 5:
            day = day + timedelta(days=1)
        return datetime(day.year, day.month, day.day, 10, 0, tzinfo=mt.IST)
    return moment


@pytest.fixture(autouse=True)
def _freeze_session(monkeypatch):
    """Pin the clock inside market hours so session checks are deterministic."""
    fixed = _tradeable_moment()
    monkeypatch.setattr(mt, "ist_now", lambda: fixed)
    yield


def test_default_configuration_blocks_everything(engine, user_id):
    decision = engine.validate_order(user_id, _proposal(), market=_fresh_quote())
    assert decision.allowed is False
    assert any(r.startswith("master_autonomous_enabled") for r in decision.reasons)


def test_kill_switch_blocks_new_orders(engine, enabled_config, user_id):
    engine.activate_kill_switch(user_id, "manual test", activated_by="test")
    decision = engine.validate_order(user_id, _proposal(), market=_fresh_quote())
    assert decision.allowed is False
    assert any(r.startswith("kill_switch") for r in decision.reasons)


def test_kill_switch_reset_restores_validation(engine, enabled_config, user_id):
    engine.activate_kill_switch(user_id, "manual test", activated_by="test")
    assert engine.validate_order(user_id, _proposal(), market=_fresh_quote()).allowed is False
    engine.reset_kill_switch(user_id, "test reset")
    assert engine.validate_order(user_id, _proposal(), market=_fresh_quote()).allowed is True


def test_instrument_not_in_allowlist_is_denied(engine, enabled_config, user_id):
    decision = engine.validate_order(
        user_id, _proposal(symbol="NSE:SBIN-EQ"), market=_fresh_quote()
    )
    assert decision.allowed is False
    assert any(r.startswith("instrument_allowed") for r in decision.reasons)


def test_duplicate_client_order_id_is_denied(engine, enabled_config, user_id):
    proposal = _proposal()
    first = engine.validate_order(user_id, proposal, market=_fresh_quote())
    assert first.allowed is True
    with SessionLocal() as db:
        db.add(
            OrderRecord(
                user_id=user_id,
                decision_id="dec_test_1",
                client_order_id=proposal["client_order_id"],
                symbol=proposal["symbol"],
                side="BUY",
                quantity=10,
                status="PENDING",
                pending_quantity=10,
                is_paper=True,
            )
        )
        db.commit()
    second = engine.validate_order(user_id, proposal, market=_fresh_quote())
    assert second.allowed is False
    assert any(r.startswith("duplicate_order") for r in second.reasons)


def test_stale_quote_is_denied(engine, enabled_config, user_id):
    stale = {
        "quote": {
            "ltp": 100.0,
            "bid": 99.9,
            "ask": 100.1,
            "timestamp": (mt.ist_now() - timedelta(minutes=10)).isoformat(),
            "source": "test_fixture",
        }
    }
    decision = engine.validate_order(user_id, _proposal(), market=stale)
    assert decision.allowed is False
    assert any(r.startswith("market_data_fresh") for r in decision.reasons)


def test_missing_quote_is_denied(engine, enabled_config, user_id):
    decision = engine.validate_order(user_id, _proposal(), market={})
    assert decision.allowed is False
    assert any(r.startswith("quote_available") for r in decision.reasons)


def test_missing_stop_loss_denied_when_required(engine, enabled_config, user_id):
    decision = engine.validate_order(
        user_id, _proposal(stop_loss=None), market=_fresh_quote()
    )
    assert decision.allowed is False
    assert any(r.startswith("stop_loss_required") for r in decision.reasons)


def test_wrong_side_stop_loss_denied(engine, enabled_config, user_id):
    decision = engine.validate_order(
        user_id, _proposal(stop_loss=105.0), market=_fresh_quote()
    )
    assert decision.allowed is False
    assert any(r.startswith("stop_loss_side") for r in decision.reasons)


def test_risk_reward_below_minimum_denied(engine, enabled_config, user_id):
    decision = engine.validate_order(
        user_id, _proposal(stop_loss=90.0, target=101.0), market=_fresh_quote()
    )
    assert decision.allowed is False
    assert any(r.startswith("min_risk_reward") for r in decision.reasons)


def test_position_size_cap_enforced(engine, enabled_config, user_id):
    decision = engine.validate_order(
        user_id, _proposal(quantity=500, price=100.0), market=_fresh_quote()
    )
    assert decision.allowed is False
    assert any(r.startswith("max_position_size") for r in decision.reasons)


def test_daily_trade_cap_enforced(engine, enabled_config, user_id):
    from app.core.datetime_utils import now_ist

    with SessionLocal() as db:
        for index in range(10):
            db.add(
                OrderRecord(
                    user_id=user_id,
                    decision_id=f"dec_fill_{index}",
                    client_order_id=f"co_{index}",
                    symbol="NSE:NIFTY50-INDEX",
                    side="BUY",
                    quantity=1,
                    status="FILLED",
                    filled_quantity=1,
                    filled_price=100.0,
                    is_paper=True,
                    created_at=now_ist(),
                )
            )
        db.commit()
    decision = engine.validate_order(user_id, _proposal(), market=_fresh_quote())
    assert decision.allowed is False
    assert any(r.startswith("max_daily_trades") for r in decision.reasons)


def test_consecutive_loss_limit_denied(engine, enabled_config, user_id):
    from app.core.brain_models import LearningReport
    from app.core.datetime_utils import now_ist

    with SessionLocal() as db:
        for index in range(3):
            db.add(
                LearningReport(
                    user_id=user_id,
                    decision_id=f"dec_loss_{index}",
                    symbol="NSE:NIFTY50-INDEX",
                    outcome="LOSS",
                    pnl=-100.0,
                    created_at=now_ist(),
                )
            )
        db.commit()
    decision = engine.validate_order(user_id, _proposal(), market=_fresh_quote())
    assert decision.allowed is False
    assert any(r.startswith("max_consecutive_losses") for r in decision.reasons)


def test_risk_event_is_persisted(engine, enabled_config, user_id):
    from app.core.brain_models import RiskEvent

    engine.validate_order(user_id, _proposal(), market=_fresh_quote())
    with SessionLocal() as db:
        rows = db.query(RiskEvent).filter(RiskEvent.user_id == user_id).all()
    assert rows, "a validation must leave an audit row"
    assert rows[-1].event_type == "order_validation"


def test_decision_never_mutates_limits(engine, enabled_config, user_id):
    """The engine reads limits; it must not be able to write them."""
    from app.core.brain_models import RiskConfig

    with SessionLocal() as db:
        before = db.query(RiskConfig).filter(RiskConfig.user_id == user_id).first().max_daily_loss
    engine.validate_order(
        user_id, _proposal(max_daily_loss=999999, master_autonomous_enabled=False),
        market=_fresh_quote(),
    )
    with SessionLocal() as db:
        after = db.query(RiskConfig).filter(RiskConfig.user_id == user_id).first().max_daily_loss
        assert after == before


def test_checks_are_recorded_for_reconstruction(engine, enabled_config, user_id):
    decision = engine.validate_order(user_id, _proposal(), market=_fresh_quote())
    names = {check["check"] for check in decision.checks}
    assert {"kill_switch", "instrument_allowed", "market_data_fresh", "min_risk_reward"} <= names
