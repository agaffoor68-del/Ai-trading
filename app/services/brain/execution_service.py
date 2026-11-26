"""Order execution, idempotency and broker reconciliation (Part 4C/D).

Responsibilities:

* size the order from the approved risk cap (never larger);
* guarantee **exactly-once** submission through the unique ``client_order_id``;
* record every fill, including partial fills, and keep ``pending_quantity``
  consistent;
* verify the broker's *actual* response (acceptance, rejection, fill price) and
  store it — a local success is never reported as a broker fill;
* reconcile local state against broker positions and log the differences.

Live broker submission is intentionally gated: ``LIVE_BROKER_ADAPTER_ENABLED``
defaults to false and the adapter must be supplied by the deployment.  Until a
verified adapter exists the engine reports ``paper`` and never pretends a live
order happened.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from app.core import market_time as mt
from app.core.brain_models import (
    LearningReport,
    OrderFill,
    OrderRecord,
    ReconciliationRun,
)
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.datetime_utils import now_ist

logger = logging.getLogger(__name__)

# Set to true only when a real broker adapter has been implemented and verified.
LIVE_BROKER_ADAPTER_ENABLED = getattr(settings, "LIVE_BROKER_ADAPTER_ENABLED", False)

TERMINAL_STATES = {"FILLED", "CLOSED", "CANCELLED", "REJECTED"}


class DuplicateOrderError(RuntimeError):
    """Raised when an idempotency key is reused."""


class BrokerAdapterUnavailable(RuntimeError):
    """Raised when a live order is requested without a verified adapter."""


class ExecutionService:
    """Paper-first order lifecycle with duplicate protection."""

    def __init__(self, broker_adapter: Optional[Any] = None) -> None:
        self.broker_adapter = broker_adapter

    # ------------------------------------------------------------------ submit
    async def submit(
        self,
        proposal: Dict[str, Any],
        risk_decision: Dict[str, Any],
        mode: str = "paper",
        paper: bool = True,
    ) -> Dict[str, Any]:
        """Execute an already risk-approved proposal exactly once."""
        if not (risk_decision or {}).get("allowed"):
            return {
                "accepted": False,
                "status": "rejected",
                "rejection_reason": "risk_engine_denied",
                "client_order_id": proposal.get("client_order_id"),
            }

        client_order_id = proposal.get("client_order_id") or f"ord_{uuid.uuid4().hex[:20]}"
        with SessionLocal() as db:
            existing = db.query(OrderRecord).filter(OrderRecord.client_order_id == client_order_id).first()
            if existing is not None:
                # Idempotent replay: return the original outcome, never resubmit.
                logger.info("Duplicate submit suppressed for %s", client_order_id)
                return {
                    "accepted": existing.status not in {"REJECTED", "CANCELLED"},
                    "status": existing.status.lower(),
                    "client_order_id": client_order_id,
                    "broker_order_id": existing.broker_order_id,
                    "filled_price": existing.filled_price,
                    "filled_quantity": existing.filled_quantity,
                    "mode": "paper" if existing.is_paper else "live",
                    "duplicate": True,
                    "rejection_reason": existing.rejection_reason,
                }

            quantity = self._size(proposal, risk_decision)
            if quantity <= 0:
                return self._reject(db, client_order_id, proposal, "sized_to_zero")

            record = OrderRecord(
                user_id=proposal.get("user_id"),
                decision_id=proposal.get("decision_id") or client_order_id,
                client_order_id=client_order_id,
                symbol=proposal["symbol"],
                side=str(proposal["side"]).upper(),
                quantity=quantity,
                order_type=proposal.get("order_type", "MARKET"),
                product_type=proposal.get("product_type", "INTRADAY"),
                status="PENDING",
                requested_price=proposal.get("price"),
                pending_quantity=quantity,
                broker="paper" if paper else "kotak",
                stop_loss=proposal.get("stop_loss"),
                target=proposal.get("target"),
                is_paper=paper,
            )
            db.add(record)
            db.commit()
            record_id = record.id

        if paper:
            return self._paper_fill(record_id, client_order_id, proposal, quantity)
        return await self._live_submit(record_id, client_order_id, proposal, quantity, mode)

    # ------------------------------------------------------------- paper fills
    def _paper_fill(
        self,
        record_id: int,
        client_order_id: str,
        proposal: Dict[str, Any],
        quantity: int,
    ) -> Dict[str, Any]:
        """Simulated fill at the snapshot price, with charges from the engine."""
        with SessionLocal() as db:
            record = db.query(OrderRecord).filter(OrderRecord.id == record_id).first()
            if record is None:
                return {"accepted": False, "status": "missing", "client_order_id": client_order_id}
            price = float(record.requested_price or 0.0)
            if price <= 0:
                record.status = "REJECTED"
                record.rejection_reason = "no reference price for paper fill"
                db.commit()
                return {
                    "accepted": False,
                    "status": "rejected",
                    "client_order_id": client_order_id,
                    "rejection_reason": "no_reference_price",
                }
            charges = _charges(price, quantity)
            record.status = "FILLED"
            record.filled_price = price
            record.filled_quantity = quantity
            record.pending_quantity = 0
            record.broker_order_id = f"PAPER-{uuid.uuid4().hex[:12]}"
            record.charges = charges
            record.slippage = 0.0
            db.add(OrderFill(order_id=record.id, quantity=quantity, price=price, charges=charges, source="paper"))
            db.commit()
            return {
                "accepted": True,
                "status": "filled",
                "client_order_id": client_order_id,
                "broker_order_id": record.broker_order_id,
                "filled_price": price,
                "filled_quantity": quantity,
                "charges": charges,
                "mode": "paper",
                "note": "simulated fill; no broker order was sent",
            }

    # -------------------------------------------------------------- live orders
    async def _live_submit(
        self,
        record_id: int,
        client_order_id: str,
        proposal: Dict[str, Any],
        quantity: int,
        mode: str,
    ) -> Dict[str, Any]:
        if not LIVE_BROKER_ADAPTER_ENABLED or self.broker_adapter is None:
            with SessionLocal() as db:
                record = db.query(OrderRecord).filter(OrderRecord.id == record_id).first()
                if record is not None:
                    record.status = "REJECTED"
                    record.rejection_reason = "live_broker_adapter_not_configured"
                    db.commit()
            return {
                "accepted": False,
                "status": "rejected",
                "client_order_id": client_order_id,
                "rejection_reason": "live_broker_adapter_not_configured",
                "mode": mode,
            }
        try:
            response = await self.broker_adapter.place_order(
                symbol=proposal["symbol"],
                side=proposal["side"],
                quantity=quantity,
                price=proposal.get("price"),
                order_type=proposal.get("order_type", "MARKET"),
                product_type=proposal.get("product_type", "INTRADAY"),
                stop_loss=proposal.get("stop_loss"),
                client_order_id=client_order_id,
            )
        except Exception as exc:
            logger.exception("Broker submission failed for %s", client_order_id)
            return self._reject_by_id(record_id, client_order_id, f"broker_error:{exc}")
        return self._apply_broker_response(record_id, client_order_id, response or {})

    def _apply_broker_response(
        self, record_id: int, client_order_id: str, response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Store the broker's real answer; never assume success."""
        status = str(response.get("status") or "UNKNOWN").upper()
        with SessionLocal() as db:
            record = db.query(OrderRecord).filter(OrderRecord.id == record_id).first()
            if record is None:
                return {"accepted": False, "status": "missing", "client_order_id": client_order_id}
            record.broker_order_id = response.get("broker_order_id") or record.broker_order_id
            record.rejection_reason = response.get("message")
            if status in {"REJECTED", "CANCELLED"}:
                record.status = status
                record.pending_quantity = 0
            else:
                filled_qty = int(response.get("filled_quantity") or 0)
                fill_price = response.get("filled_price")
                record.filled_quantity = filled_qty
                record.pending_quantity = max(0, record.quantity - filled_qty)
                if fill_price is not None:
                    record.filled_price = float(fill_price)
                if filled_qty > 0 and record.pending_quantity == 0:
                    record.status = "FILLED"
                elif filled_qty > 0:
                    record.status = "PARTIAL"
                else:
                    record.status = "PENDING"
                for fill in response.get("fills") or []:
                    db.add(
                        OrderFill(
                            order_id=record.id,
                            quantity=int(fill.get("quantity") or 0),
                            price=float(fill.get("price") or 0.0),
                            charges=float(fill.get("charges") or 0.0),
                            source="broker",
                        )
                    )
            db.commit()
            return {
                "accepted": record.status not in {"REJECTED", "CANCELLED"},
                "status": record.status.lower(),
                "client_order_id": client_order_id,
                "broker_order_id": record.broker_order_id,
                "filled_price": record.filled_price,
                "filled_quantity": record.filled_quantity,
                "pending_quantity": record.pending_quantity,
                "rejection_reason": record.rejection_reason,
                "mode": "live",
            }

    # ------------------------------------------------------------- maintenance
    def _reject(self, db, client_order_id: str, proposal: Dict[str, Any], reason: str) -> Dict[str, Any]:
        db.add(
            OrderRecord(
                user_id=proposal.get("user_id"),
                decision_id=proposal.get("decision_id") or client_order_id,
                client_order_id=client_order_id,
                symbol=proposal.get("symbol", "UNKNOWN"),
                side=str(proposal.get("side") or "BUY").upper(),
                quantity=int(proposal.get("quantity") or 0),
                status="REJECTED",
                pending_quantity=0,
                broker="paper",
                is_paper=True,
                rejection_reason=reason,
            )
        )
        db.commit()
        return {
            "accepted": False,
            "status": "rejected",
            "client_order_id": client_order_id,
            "rejection_reason": reason,
        }

    def _reject_by_id(self, record_id: int, client_order_id: str, reason: str) -> Dict[str, Any]:
        with SessionLocal() as db:
            record = db.query(OrderRecord).filter(OrderRecord.id == record_id).first()
            if record is not None:
                record.status = "REJECTED"
                record.rejection_reason = reason
                record.pending_quantity = 0
                db.commit()
        return {
            "accepted": False,
            "status": "rejected",
            "client_order_id": client_order_id,
            "rejection_reason": reason,
        }

    def _size(self, proposal: Dict[str, Any], risk_decision: Dict[str, Any]) -> int:
        """Largest whole quantity whose stop distance fits the per-trade cap."""
        limits = (risk_decision or {}).get("limits") or {}
        price = float(proposal.get("price") or 0.0)
        stop = float(proposal.get("stop_loss") or 0.0)
        if price <= 0 or stop <= 0:
            return 0
        per_trade_pct = float(limits.get("max_risk_per_trade_pct") or 0.0)
        exposure_cap = float(limits.get("max_portfolio_exposure") or 0.0)
        max_qty = int(limits.get("max_position_size") or 0)
        if per_trade_pct <= 0 or exposure_cap <= 0 or max_qty <= 0:
            return 0
        risk_cap = per_trade_pct / 100.0 * exposure_cap
        risk_per_unit = abs(price - stop)
        if risk_per_unit <= 0:
            return 0
        by_risk = int(risk_cap // risk_per_unit)
        by_exposure = int(exposure_cap // price)
        quantity = min(by_risk, by_exposure, max_qty, int(proposal.get("quantity") or max_qty))
        lot = proposal.get("lot_size")
        if lot:
            quantity = (quantity // int(lot)) * int(lot)
        return max(0, quantity)

    def close_position(
        self,
        decision_id: str,
        exit_price: float,
        exit_reason: str,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Mark the position closed and compute net P&L after charges."""
        with SessionLocal() as db:
            stmt = db.query(OrderRecord).filter(
                OrderRecord.decision_id == decision_id,
                OrderRecord.status.in_(["FILLED", "PARTIAL", "OPEN"]),
            )
            if user_id is not None:
                stmt = stmt.filter(OrderRecord.user_id == user_id)
            record = stmt.order_by(OrderRecord.created_at.desc()).first()
            if record is None:
                return {"closed": False, "reason": "no open position for decision"}
            quantity = record.filled_quantity or record.quantity
            entry = record.filled_price or record.requested_price or 0.0
            direction = 1 if record.side == "BUY" else -1
            gross = (float(exit_price) - entry) * quantity * direction
            exit_charges = _charges(float(exit_price), quantity)
            net = gross - float(record.charges or 0.0) - exit_charges
            record.status = "CLOSED"
            record.filled_price = float(exit_price)
            record.pending_quantity = 0
            record.updated_at = now_ist()
            db.add(
                OrderFill(
                    order_id=record.id,
                    quantity=quantity,
                    price=float(exit_price),
                    charges=exit_charges,
                    source="exit",
                )
            )
            db.commit()
            return {
                "closed": True,
                "decision_id": decision_id,
                "exit_price": float(exit_price),
                "exit_reason": exit_reason,
                "gross_pnl": round(gross, 2),
                "charges": round(float(record.charges or 0.0) + exit_charges, 2),
                "net_pnl": round(net, 2),
                "quantity": quantity,
                "entry": entry,
            }

    async def reconcile(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Compare local order state with the broker position snapshot."""
        local: List[Dict[str, Any]] = []
        with SessionLocal() as db:
            stmt = db.query(OrderRecord).filter(OrderRecord.status.in_(["FILLED", "PARTIAL", "OPEN"]))
            if user_id is not None:
                stmt = stmt.filter(OrderRecord.user_id == user_id)
            for row in stmt.all():
                local.append(
                    {
                        "symbol": row.symbol,
                        "side": row.side,
                        "quantity": row.filled_quantity or row.quantity,
                        "broker_order_id": row.broker_order_id,
                        "is_paper": row.is_paper,
                    }
                )
        broker: List[Dict[str, Any]] = []
        if self.broker_adapter is not None and LIVE_BROKER_ADAPTER_ENABLED:
            try:
                broker = list(await self.broker_adapter.positions() or [])
            except Exception as exc:
                logger.warning("Broker position fetch failed: %s", exc)
                broker = []
        discrepancies = _diff_positions(local, broker)
        with SessionLocal() as db:
            db.add(
                ReconciliationRun(
                    user_id=user_id,
                    broker="paper" if all(p["is_paper"] for p in local) else "kotak",
                    matched=not discrepancies,
                    discrepancies=discrepancies,
                    local_positions=local,
                    broker_positions=broker,
                )
            )
            db.commit()
        return {
            "matched": not discrepancies,
            "discrepancies": discrepancies,
            "local_count": len(local),
            "broker_count": len(broker),
            "note": "paper positions have no broker counterpart by design" if not broker else None,
        }

    def open_positions(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with SessionLocal() as db:
            stmt = db.query(OrderRecord).filter(OrderRecord.status.in_(["FILLED", "PARTIAL", "OPEN"]))
            if user_id is not None:
                stmt = stmt.filter(OrderRecord.user_id == user_id)
            return [
                {
                    "decision_id": r.decision_id,
                    "symbol": r.symbol,
                    "side": r.side,
                    "quantity": r.filled_quantity or r.quantity,
                    "entry": r.filled_price or r.requested_price,
                    "stop_loss": r.stop_loss,
                    "target": r.target,
                    "is_paper": r.is_paper,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in stmt.all()
            ]

    async def emergency_exit(self, user_id: Optional[int], policy: str) -> Dict[str, Any]:
        """Kill-switch exit policy: flatten, or hold and alert."""
        positions = self.open_positions(user_id)
        if policy == "flatten":
            closed = []
            for position in positions:
                quote = await _ltp(position["symbol"])
                if quote is None:
                    closed.append({"symbol": position["symbol"], "closed": False, "reason": "no quote"})
                    continue
                closed.append(
                    self.close_position(
                        decision_id=position["decision_id"],
                        exit_price=quote,
                        exit_reason="emergency_exit",
                        user_id=user_id,
                    )
                )
            return {"policy": policy, "closed": closed}
        return {"policy": policy, "held": [p["symbol"] for p in positions]}


def _charges(price: float, quantity: float) -> float:
    """Realistic Indian F&O charges via the existing calculator, else 0."""
    try:
        from app.core.charges import ChargesCalculator, InstrumentType, TradeSide

        breakdown = ChargesCalculator().calculate(
            instrument_type=InstrumentType.OPTIONS,
            side=TradeSide.BUY,
            price=price,
            quantity=quantity,
            lot_size=1,
        )
        return round(float(getattr(breakdown, "total_charges", 0.0) or 0.0), 2)
    except Exception:
        logger.debug("Charge calculation unavailable; recording 0 charges", exc_info=True)
        return 0.0


def _diff_positions(local: List[Dict[str, Any]], broker: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    broker_index = {(b.get("symbol"), str(b.get("side", "")).upper()): b for b in broker}
    out: List[Dict[str, Any]] = []
    for item in local:
        key = (item["symbol"], str(item["side"]).upper())
        match = broker_index.get(key)
        if match is None:
            if not item["is_paper"]:
                out.append({"type": "missing_at_broker", "local": item})
            continue
        if int(match.get("quantity") or 0) != int(item["quantity"]):
            out.append(
                {
                    "type": "quantity_mismatch",
                    "symbol": item["symbol"],
                    "local": item["quantity"],
                    "broker": match.get("quantity"),
                }
            )
    return out


async def _ltp(symbol: str) -> Optional[float]:
    try:
        from app.services.brain.data_intelligence import get_tdil

        quotes = await get_tdil().quotes([symbol])
        value = (quotes.get(symbol) or {}).get("ltp")
        return float(value) if value is not None else None
    except Exception:
        return None


_service: Optional[ExecutionService] = None


def get_execution_service() -> ExecutionService:
    global _service
    if _service is None:
        _service = ExecutionService()
    return _service


__all__ = [
    "BrokerAdapterUnavailable",
    "DuplicateOrderError",
    "ExecutionService",
    "LIVE_BROKER_ADAPTER_ENABLED",
    "get_execution_service",
]
