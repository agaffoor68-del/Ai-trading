"""Independent Risk Management Engine.

This module is deliberately **not** aware of Grok, prompts or strategies.  It
consumes a plain proposal dict and the persisted ``RiskConfig``/``KillSwitch``
rows and returns an allow/deny decision with reasons.  The AI can call it; it
cannot change it:

* limits are read from ``risk_configs`` and only the settings API writes them;
* the kill switch is read from ``kill_switches`` and only the user (or the
  emergency stop endpoint) can clear it;
* every decision is appended to ``risk_events`` for audit.

Order of checks is fixed and cheap checks run first.  Any ``deny`` short
circuits: no order is ever submitted when a single rule fails.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core import market_time as mt
from app.core.brain_models import (
    KillSwitch,
    OrderRecord,
    RiskConfig,
    RiskEvent,
)
from app.core.database import SessionLocal
from app.core.datetime_utils import now_ist

logger = logging.getLogger(__name__)

# Segment aliases accepted in ``allowed_segments``.
SEGMENT_ALIASES = {
    "NSE": "NSE", "BSE": "BSE", "NFO": "NSE", "BFO": "BSE",
    "INDEX": "NSE", "STOCK": "NSE", "EQUITY": "NSE",
    "FUTURES": "NSE", "OPTIONS": "NSE",
    "CRYPTO": "CRYPTO",
}

MAX_QUOTE_AGE_SECONDS = 90


@dataclass
class RiskDecision:
    """Result of one validation pass."""

    allowed: bool
    stage: str
    reasons: List[str] = field(default_factory=list)
    checks: List[Dict[str, Any]] = field(default_factory=list)
    limits: Dict[str, Any] = field(default_factory=dict)
    decision_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def add(self, name: str, passed: bool, detail: str = "", **extra: Any) -> bool:
        self.checks.append({"check": name, "passed": bool(passed), "detail": detail, **extra})
        if not passed:
            self.reasons.append(f"{name}: {detail}" if detail else name)
        return passed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "allowed": self.allowed,
            "failed_stage": None if self.allowed else self.stage,
            "reasons": self.reasons,
            "checks": self.checks,
            "limits": self.limits,
        }


def default_config(user_id: Optional[int]) -> RiskConfig:
    """A locked-down configuration used when the user has saved none yet.

    Autonomous trading is OFF, mode is paper and the instrument list is empty,
    so nothing can trade until the user explicitly configures and enables it.
    """
    return RiskConfig(
        user_id=user_id,
        master_autonomous_enabled=False,
        trading_mode="paper",
        allowed_instruments=[],
        allowed_segments=[],
        max_risk_per_trade_pct=0.5,
        max_daily_loss=2000.0,
        max_total_open_positions=3,
        max_position_size=50,
        max_daily_trades=10,
        max_portfolio_exposure=100000.0,
        max_consecutive_losses=3,
        session_start="09:20",
        session_end="15:10",
        square_off_time="15:15",
        emergency_exit_policy="hold",
        require_stop_loss=True,
        min_risk_reward=1.5,
        max_spread_pct=0.25,
    )


def load_config(db, user_id: Optional[int]) -> RiskConfig:
    if user_id is None:
        return default_config(None)
    config = db.query(RiskConfig).filter(RiskConfig.user_id == user_id).first()
    return config or default_config(user_id)


def kill_switch_active(db, user_id: Optional[int]) -> Optional[KillSwitch]:
    """Global switch (user_id NULL) OR the user's own switch."""
    rows = (
        db.query(KillSwitch)
        .filter((KillSwitch.active.is_(True)) & ((KillSwitch.user_id.is_(None)) | (KillSwitch.user_id == user_id)))
        .all()
    )
    return rows[0] if rows else None


def _segment_of(symbol: str) -> str:
    text = (symbol or "").upper()
    if text.startswith("BSE:"):
        return "BSE"
    if "CRYPTO" in text or text.endswith("USDT") or text.startswith("BINANCE"):
        return "CRYPTO"
    return "NSE"


def _instrument_allowed(symbol: str, allowed: List[str]) -> bool:
    if not allowed:
        return False
    upper = (symbol or "").upper()
    for entry in allowed:
        token = str(entry).upper().strip()
        if not token:
            continue
        if upper == token or upper.endswith(f":{token}") or token in upper:
            return True
    return False


class RiskEngine:
    """Stateless validator over persisted user limits."""

    def __init__(self, max_quote_age: int = MAX_QUOTE_AGE_SECONDS) -> None:
        self.max_quote_age = max_quote_age

    # ------------------------------------------------------------------ public
    def validate_order(
        self,
        user_id: Optional[int],
        proposal: Dict[str, Any],
        market: Optional[Dict[str, Any]] = None,
        commit: bool = True,
    ) -> RiskDecision:
        """Validate a proposed order.  Never raises for a rule breach."""
        market = market or {}
        decision = RiskDecision(allowed=False, stage="init")
        with SessionLocal() as db:
            config = load_config(db, user_id)
            decision.limits = _config_dict(config)

            switch = kill_switch_active(db, user_id)
            decision.stage = "kill_switch"
            if not decision.add(
                "kill_switch",
                switch is None,
                f"kill switch active ({switch.reason})" if switch else "",
            ):
                return self._finish(db, decision, user_id, proposal, commit)

            decision.stage = "master_switch"
            if not decision.add(
                "master_autonomous_enabled",
                bool(config.master_autonomous_enabled),
                "autonomous trading is disabled by the user",
            ):
                return self._finish(db, decision, user_id, proposal, commit)

            decision.stage = "trading_mode"
            mode = (config.trading_mode or "paper").lower()
            requested_live = str(proposal.get("mode", mode)).lower() == "live"
            if not decision.add(
                "trading_mode",
                not (requested_live and mode != "live"),
                f"account mode is '{mode}', live order requested",
            ):
                return self._finish(db, decision, user_id, proposal, commit)

            if not self._validate_static(db, decision, config, proposal, market):
                return self._finish(db, decision, user_id, proposal, commit)

            decision.stage = "limits"
            if not self._validate_limits(db, decision, config, proposal, user_id):
                return self._finish(db, decision, user_id, proposal, commit)

            decision.allowed = True
            decision.stage = "approved"
            return self._finish(db, decision, user_id, proposal, commit)

    def activate_kill_switch(
        self,
        user_id: Optional[int],
        reason: str,
        activated_by: str = "user",
        exit_policy: str = "hold",
    ) -> Dict[str, Any]:
        """Turn the emergency stop on.  Idempotent."""
        with SessionLocal() as db:
            row = (
                db.query(KillSwitch)
                .filter(KillSwitch.user_id.is_(user_id) if user_id else KillSwitch.user_id.is_(None))
                .first()
            )
            if row is None:
                row = KillSwitch(user_id=user_id)
                db.add(row)
            row.active = True
            row.reason = reason
            row.activated_by = activated_by
            row.activated_at = now_ist()
            row.exit_policy = exit_policy
            db.add(
                RiskEvent(
                    user_id=user_id,
                    event_type="kill_switch_activated",
                    allowed=False,
                    reason=reason,
                    details={"activated_by": activated_by, "exit_policy": exit_policy},
                )
            )
            db.commit()
            logger.warning("KILL SWITCH ACTIVE user=%s by=%s reason=%s", user_id, activated_by, reason)
            return {"active": True, "reason": reason, "activated_by": activated_by}

    def reset_kill_switch(self, user_id: Optional[int], note: str = "manual reset") -> Dict[str, Any]:
        with SessionLocal() as db:
            rows = (
                db.query(KillSwitch)
                .filter((KillSwitch.user_id == user_id) | (KillSwitch.user_id.is_(None)))
                .all()
            )
            for row in rows:
                row.active = False
                row.reason = f"reset: {note}"
            db.add(
                RiskEvent(
                    user_id=user_id,
                    event_type="kill_switch_reset",
                    allowed=True,
                    reason=note,
                )
            )
            db.commit()
            return {"active": False, "reset": note}

    def daily_usage(self, user_id: Optional[int], day: Optional[Any] = None) -> Dict[str, Any]:
        """Realised + open exposure for the current session (from order rows)."""
        target_day = day or mt.trading_date()
        start = mt.ist_now().replace(
            year=target_day.year, month=target_day.month, day=target_day.day,
            hour=0, minute=0, second=0, microsecond=0,
        )
        with SessionLocal() as db:
            query = db.query(OrderRecord).filter(OrderRecord.created_at >= start)
            if user_id is not None:
                query = query.filter(OrderRecord.user_id == user_id)
            rows = query.all()
            realised = 0.0
            for row in rows:
                report_pnl = getattr(row, "_pnl", None)
                if report_pnl is not None:
                    realised += report_pnl
            open_rows = [r for r in rows if r.status in {"PENDING", "PARTIAL", "FILLED", "OPEN"}]
            exposure = sum(
                (r.filled_price or r.requested_price or 0.0) * (r.filled_quantity or r.quantity or 0)
                for r in open_rows
            )
            return {
                "trades_today": len([r for r in rows if r.status not in {"REJECTED", "CANCELLED"}]),
                "open_positions": len(open_rows),
                "realised_pnl": round(realised, 2),
                "exposure": round(exposure, 2),
            }

    def consecutive_losses(self, user_id: Optional[int], limit: int = 20) -> int:
        from app.core.brain_models import LearningReport

        with SessionLocal() as db:
            query = db.query(LearningReport).filter(LearningReport.outcome.in_(["WIN", "LOSS"]))
            if user_id is not None:
                query = query.filter(LearningReport.user_id == user_id)
            rows = query.order_by(LearningReport.created_at.desc()).limit(limit).all()
        streak = 0
        for row in rows:
            if row.outcome == "LOSS":
                streak += 1
            else:
                break
        return streak

    # ----------------------------------------------------------------- internal
    def _validate_static(
        self,
        db,
        decision: RiskDecision,
        config: RiskConfig,
        proposal: Dict[str, Any],
        market: Dict[str, Any],
    ) -> bool:
        symbol = str(proposal.get("symbol") or "")
        side = str(proposal.get("side") or "").upper()
        quantity = proposal.get("quantity")
        price = proposal.get("price")
        stop_loss = proposal.get("stop_loss")
        target = proposal.get("target")

        ok = decision.add("instrument_present", bool(symbol), "symbol is required")
        ok = decision.add("side_supported", side in {"BUY", "SELL"}, f"unsupported side '{side}'") and ok
        if not ok:
            return False

        decision.stage = "instrument"
        if not decision.add(
            "instrument_allowed",
            _instrument_allowed(symbol, list(config.allowed_instruments or [])),
            f"{symbol} is not in the user's allowed instruments",
        ):
            return False

        decision.stage = "segment"
        segment = _segment_of(symbol)
        allowed_segments = {SEGMENT_ALIASES.get(str(s).upper(), str(s).upper()) for s in (config.allowed_segments or [])}
        if not decision.add(
            "segment_allowed",
            segment in allowed_segments,
            f"segment {segment} not enabled (allowed: {sorted(allowed_segments) or 'none'})",
        ):
            return False

        decision.stage = "session"
        now = mt.ist_now()
        if segment != "CRYPTO":
            if not decision.add("trading_day", mt.is_market_open(segment, now), "market closed (holiday/weekend/off-hours)"):
                return False
            if not decision.add(
                "risk_session",
                mt.in_risk_session(now, config.session_start, config.session_end),
                f"outside configured session {config.session_start}-{config.session_end} IST",
            ):
                return False
            if now.astimezone(mt.IST).time() >= mt.hhmmss_to_time(config.square_off_time):
                if not decision.add("before_square_off", False, f"past square-off time {config.square_off_time}"):
                    return False

        decision.stage = "quantity"
        try:
            quantity_int = int(quantity)
        except (TypeError, ValueError):
            quantity_int = 0
        if not decision.add("quantity_positive", quantity_int > 0, f"quantity must be > 0 (got {quantity})"):
            return False
        if not decision.add(
            "max_position_size",
            quantity_int <= int(config.max_position_size),
            f"quantity {quantity_int} exceeds max position size {config.max_position_size}",
        ):
            return False
        lot_size = proposal.get("lot_size")
        if lot_size:
            if not decision.add(
                "lot_size_multiple",
                quantity_int % int(lot_size) == 0,
                f"quantity {quantity_int} is not a multiple of lot size {lot_size}",
            ):
                return False

        decision.stage = "price"
        price_value = _as_float(price)
        if not decision.add("price_valid", price_value is not None and price_value > 0, f"invalid price {price}"):
            return False
        quote = market.get("quote") or {}
        quote_ltp = _as_float(quote.get("ltp"))
        if quote_ltp is None:
            if not decision.add("quote_available", False, "no live quote for the instrument"):
                return False
        else:
            if not decision.add(
                "market_data_fresh",
                mt.is_fresh(quote.get("timestamp"), self.max_quote_age),
                f"quote age {mt.age_seconds(quote.get('timestamp'))}s exceeds {self.max_quote_age}s",
            ):
                return False
            spread = _as_float(quote.get("ask"))
            bid = _as_float(quote.get("bid"))
            if spread is not None and bid is not None and bid > 0:
                spread_pct = (spread - bid) / bid * 100
                if not decision.add(
                    "max_spread",
                    spread_pct <= float(config.max_spread_pct),
                    f"spread {spread_pct:.2f}% exceeds {config.max_spread_pct}%",
                ):
                    return False
            if price_value and abs(price_value - quote_ltp) / quote_ltp * 100 > 5:
                if not decision.add(
                    "price_near_market",
                    False,
                    f"proposed {price_value} is >5% away from LTP {quote_ltp}",
                ):
                    return False

        decision.stage = "stop_loss"
        sl_value = _as_float(stop_loss)
        if config.require_stop_loss and sl_value is None:
            if not decision.add("stop_loss_required", False, "strategy/broker configuration requires a stop-loss"):
                return False
        if sl_value is not None:
            correct_side = sl_value < price_value if side == "BUY" else sl_value > price_value
            if not decision.add("stop_loss_side", correct_side, f"stop-loss {sl_value} is on the wrong side of entry {price_value}"):
                return False

        decision.stage = "risk_reward"
        target_value = _as_float(target)
        if sl_value is not None and target_value is not None:
            risk = abs(price_value - sl_value)
            reward = abs(target_value - price_value)
            rr = reward / risk if risk > 0 else 0.0
            if not decision.add(
                "min_risk_reward",
                rr >= float(config.min_risk_reward),
                f"risk/reward {rr:.2f} below minimum {config.min_risk_reward}",
            ):
                return False
            risk_amount = risk * quantity_int
            cap = float(config.max_risk_per_trade_pct) / 100.0 * float(config.max_portfolio_exposure)
            if not decision.add(
                "max_risk_per_trade",
                risk_amount <= cap,
                f"risk {risk_amount:.2f} exceeds per-trade cap {cap:.2f}",
            ):
                return False

        decision.stage = "duplicate"
        client_order_id = proposal.get("client_order_id")
        if client_order_id:
            existing = db.query(OrderRecord).filter(OrderRecord.client_order_id == client_order_id).first()
            if not decision.add("duplicate_order", existing is None, f"order {client_order_id} already exists"):
                return False
        return True

    def _validate_limits(
        self,
        db,
        decision: RiskDecision,
        config: RiskConfig,
        proposal: Dict[str, Any],
        user_id: Optional[int],
    ) -> bool:
        usage = self.daily_usage(user_id)
        decision.limits["usage"] = usage

        if not decision.add(
            "max_daily_trades",
            usage["trades_today"] < int(config.max_daily_trades),
            f"{usage['trades_today']} trades today, limit {config.max_daily_trades}",
        ):
            return False
        if not decision.add(
            "max_total_open_positions",
            usage["open_positions"] < int(config.max_total_open_positions),
            f"{usage['open_positions']} open positions, limit {config.max_total_open_positions}",
        ):
            return False

        price = _as_float(proposal.get("price")) or 0.0
        quantity = int(proposal.get("quantity") or 0)
        new_exposure = price * quantity
        if not decision.add(
            "max_portfolio_exposure",
            usage["exposure"] + new_exposure <= float(config.max_portfolio_exposure),
            f"exposure would reach {usage['exposure'] + new_exposure:.2f}, cap {config.max_portfolio_exposure}",
        ):
            return False

        if not decision.add(
            "max_daily_loss",
            usage["realised_pnl"] > -abs(float(config.max_daily_loss)),
            f"realised loss {usage['realised_pnl']} reached daily limit {-abs(float(config.max_daily_loss))}",
        ):
            return False

        losses = self.consecutive_losses(user_id)
        if not decision.add(
            "max_consecutive_losses",
            losses < int(config.max_consecutive_losses),
            f"{losses} consecutive losses, limit {config.max_consecutive_losses}",
        ):
            return False
        return True

    def _finish(
        self,
        db,
        decision: RiskDecision,
        user_id: Optional[int],
        proposal: Dict[str, Any],
        commit: bool,
    ) -> RiskDecision:
        if commit:
            try:
                db.add(
                    RiskEvent(
                        user_id=user_id,
                        decision_id=proposal.get("decision_id") or decision.decision_id,
                        event_type="order_validation",
                        allowed=decision.allowed,
                        reason="; ".join(decision.reasons) or "all checks passed",
                        details={
                            "stage": decision.stage,
                            "symbol": proposal.get("symbol"),
                            "side": proposal.get("side"),
                            "quantity": proposal.get("quantity"),
                            "checks": decision.checks,
                        },
                    )
                )
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("Failed to persist risk event")
        return decision


def _as_float(value: Any) -> Optional[float]:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


def _config_dict(config: RiskConfig) -> Dict[str, Any]:
    return {
        "trading_mode": config.trading_mode,
        "master_autonomous_enabled": config.master_autonomous_enabled,
        "max_risk_per_trade_pct": config.max_risk_per_trade_pct,
        "max_daily_loss": config.max_daily_loss,
        "max_total_open_positions": config.max_total_open_positions,
        "max_position_size": config.max_position_size,
        "max_daily_trades": config.max_daily_trades,
        "max_portfolio_exposure": config.max_portfolio_exposure,
        "max_consecutive_losses": config.max_consecutive_losses,
        "session": [config.session_start, config.session_end],
        "square_off": config.square_off_time,
        "require_stop_loss": config.require_stop_loss,
        "min_risk_reward": config.min_risk_reward,
    }


_engine: Optional[RiskEngine] = None


def get_risk_engine() -> RiskEngine:
    global _engine
    if _engine is None:
        _engine = RiskEngine()
    return _engine


__all__ = [
    "RiskDecision",
    "RiskEngine",
    "activate_kill_switch",
    "default_config",
    "get_risk_engine",
    "kill_switch_active",
    "load_config",
]


def activate_kill_switch(user_id: Optional[int], reason: str, activated_by: str = "user",
                         exit_policy: str = "hold") -> Dict[str, Any]:
    """Module-level convenience wrapper used by the API layer."""
    return get_risk_engine().activate_kill_switch(user_id, reason, activated_by, exit_policy)
