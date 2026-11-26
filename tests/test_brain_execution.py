"""Execution service tests: idempotency, sizing, partial fills, reconciliation."""

from __future__ import annotations

import pytest

from app.core.brain_models import OrderFill, OrderRecord
from app.core.database import SessionLocal
from app.services.brain.execution_service import ExecutionService


ALLOWED = {"allowed": True, "limits": {
    "max_risk_per_trade_pct": 2.0,
    "max_portfolio_exposure": 200000.0,
    "max_position_size": 50,
}}

DENIED = {"allowed": False, "reasons": ["risk_engine_denied"]}


def _proposal(**overrides):
    base = {
        "symbol": "NSE:NIFTY50-INDEX",
        "side": "BUY",
        "price": 100.0,
        "stop_loss": 95.0,
        "target": 110.0,
        "quantity": 10,
        "decision_id": "dec_exec_1",
        "client_order_id": "co_exec_1",
    }
    base.update(overrides)
    return base


@pytest.fixture()
def service():
    return ExecutionService()


def test_risk_denied_never_creates_order(service, clean_db):
    import asyncio

    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(service.submit(_proposal(), DENIED))
    loop.close()
    assert result["accepted"] is False
    assert result["rejection_reason"] == "risk_engine_denied"
    with SessionLocal() as db:
        assert db.query(OrderRecord).count() == 0


def test_duplicate_submit_is_idempotent(service, clean_db):
    import asyncio

    loop = asyncio.new_event_loop()
    first = loop.run_until_complete(service.submit(_proposal(), ALLOWED))
    second = loop.run_until_complete(service.submit(_proposal(), ALLOWED))
    loop.close()
    assert first["accepted"] is True
    assert second.get("duplicate") is True
    with SessionLocal() as db:
        assert db.query(OrderRecord).count() == 1


def test_sizing_respects_risk_cap(service, clean_db):
    quantity = service._size(
        {"price": 100.0, "stop_loss": 95.0, "quantity": 50}, ALLOWED
    )
    # risk cap = 2% of 200000 = 4000; risk per unit = 5 → 800 units, capped at 50
    assert quantity == 50
    tight = service._size({"price": 100.0, "stop_loss": 1.0, "quantity": 50}, ALLOWED)
    assert tight == 40  # 4000 / 99 = 40.4 → 40


def test_sizing_zero_without_risk_budget(service):
    assert service._size({"price": 100.0, "stop_loss": 95.0, "quantity": 10}, {"limits": {}}) == 0


def test_partial_fill_tracked(service, clean_db):
    with SessionLocal() as db:
        record = OrderRecord(
            decision_id="dec_partial",
            client_order_id="co_partial",
            symbol="NSE:NIFTY50-INDEX",
            side="BUY",
            quantity=10,
            status="PENDING",
            pending_quantity=10,
            is_paper=False,
        )
        db.add(record)
        db.commit()
        record_id = record.id
    result = service._apply_broker_response(
        record_id,
        "co_partial",
        {"status": "PARTIAL", "broker_order_id": "B1", "filled_quantity": 4, "filled_price": 100.5,
         "fills": [{"quantity": 4, "price": 100.5, "charges": 2.0}]},
    )
    assert result["status"] == "partial"
    assert result["pending_quantity"] == 6
    with SessionLocal() as db:
        stored = db.query(OrderRecord).filter(OrderRecord.client_order_id == "co_partial").first()
        assert stored.filled_quantity == 4
        assert db.query(OrderFill).filter(OrderFill.order_id == stored.id).count() == 1


def test_broker_rejection_is_recorded(service, clean_db):
    with SessionLocal() as db:
        record = OrderRecord(
            decision_id="dec_rej",
            client_order_id="co_rej",
            symbol="NSE:NIFTY50-INDEX",
            side="BUY",
            quantity=10,
            status="PENDING",
            pending_quantity=10,
            is_paper=False,
        )
        db.add(record)
        db.commit()
        record_id = record.id
    result = service._apply_broker_response(
        record_id, "co_rej", {"status": "REJECTED", "message": "insufficient margin"}
    )
    assert result["accepted"] is False
    assert result["rejection_reason"] == "insufficient margin"


def test_live_mode_without_adapter_is_rejected(service, clean_db):
    """No live order can be reported as filled while the adapter is absent."""
    import asyncio

    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(
        service.submit(_proposal(client_order_id="co_live"), ALLOWED, mode="live", paper=False)
    )
    loop.close()
    assert result["accepted"] is False
    assert result["rejection_reason"] in {"live_broker_adapter_not_configured"}


def test_close_position_computes_net_pnl(service, clean_db):
    import asyncio

    loop = asyncio.new_event_loop()
    loop.run_until_complete(service.submit(_proposal(), ALLOWED))
    closed = service.close_position("dec_exec_1", exit_price=110.0, exit_reason="target")
    loop.close()
    assert closed["closed"] is True
    # gross = (110-100)*10 = 100, minus entry charges (>=0) and exit charges (>=0)
    assert closed["gross_pnl"] == 100.0
    assert closed["net_pnl"] <= 100.0


def test_reconcile_reports_paper_positions(service, clean_db):
    import asyncio

    loop = asyncio.new_event_loop()
    loop.run_until_complete(service.submit(_proposal(), ALLOWED))
    report = loop.run_until_complete(service.reconcile())
    loop.close()
    assert report["local_count"] == 1
    # Paper positions have no broker counterpart by design and must not be
    # reported as a discrepancy.
    assert report["discrepancies"] == []


def test_open_positions_listing(service, clean_db):
    import asyncio

    loop = asyncio.new_event_loop()
    loop.run_until_complete(service.submit(_proposal(), ALLOWED))
    rows = service.open_positions()
    loop.close()
    assert len(rows) == 1
    assert rows[0]["symbol"] == "NSE:NIFTY50-INDEX"
