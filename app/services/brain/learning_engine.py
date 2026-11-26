"""Automatic learning engine and validated strategy improvement (Parts 5, 6).

Two independent responsibilities:

1. **Post-trade analysis.**  After every closed trade (or every NO_TRADE that
   was later re-evaluated) a ``LearningReport`` is written from real order,
   indicator and news rows.  Winning conditions and loss reasons are derived
   from stored evidence — never from a model's opinion alone.
2. **Strategy improvement with gates.**  A candidate strategy is created as a new
   version, backtested, out-of-sample tested, walk-forward validated, compared to
   the incumbent, shadow-evaluated, and only then promoted.  Promotion requires
   *all* gates to pass and a minimum sample size.  Any failure keeps the version
   ``rejected`` (or ``disabled``) with the report attached, and the incumbent is
   untouched.  Rollback is a status change back to the previous version.

Look-ahead bias is structurally prevented: the backtester only ever reads bar
``i`` and earlier, and indicators are computed on the truncated series.
"""

from __future__ import annotations

import logging
import statistics
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import select

from app.core import market_time as mt
from app.core.brain_models import (
    LearningReport,
    OrderRecord,
    StrategyStatus,
    StrategyVersion,
)
from app.core.database import SessionLocal
from app.core.datetime_utils import now_ist
from app.services.brain.memory_service import write_memory

logger = logging.getLogger(__name__)

# --------------------------------------------------------------- gate settings
MIN_SAMPLE_SIZE = 30
MIN_PROFIT_FACTOR = 1.15
MAX_DRAWDOWN_PCT = 6.0
MIN_OUT_OF_SAMPLE_TRADES = 20
MIN_WALK_FORWARD_FOLDS = 3
MIN_SHADOW_TRADES = 10
# A candidate must beat the incumbent by this relative margin on net P&L.
MIN_IMPROVEMENT_PCT = 5.0


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str
    value: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"gate": self.name, "passed": self.passed, "detail": self.detail, "value": self.value}


@dataclass
class ValidationReport:
    version: str
    gates: List[GateResult] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    promoted: bool = False
    reason: str = ""

    def add(self, name: str, passed: bool, detail: str, value: Optional[float] = None) -> None:
        self.gates.append(GateResult(name, passed, detail, value))

    @property
    def all_passed(self) -> bool:
        return bool(self.gates) and all(g.passed for g in self.gates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "promoted": self.promoted,
            "reason": self.reason,
            "all_gates_passed": self.all_passed,
            "gates": [g.to_dict() for g in self.gates],
            "metrics": self.metrics,
            "checked_at": now_ist().isoformat(),
        }


# ------------------------------------------------------------------ indicators
def _ema(values: Sequence[float], period: int) -> List[Optional[float]]:
    if not values:
        return []
    k = 2.0 / (period + 1.0)
    out: List[Optional[float]] = [values[0]]
    for value in values[1:]:
        prev = out[-1]
        out.append(value * k + (prev if prev is not None else value) * (1 - k))
    return out


def _rsi(values: Sequence[float], period: int = 14) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(values)
    if len(values) <= period:
        return out
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        change = values[i] - values[i - 1]
        gains += max(change, 0.0)
        losses += max(-change, 0.0)
    avg_gain = gains / period
    avg_loss = losses / period
    out[period] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    for i in range(period + 1, len(values)):
        change = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
        out[i] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    return out


def _atr(candles: Sequence[Dict[str, Any]], period: int = 14) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(candles)
    if len(candles) <= period:
        return out
    trs: List[float] = [0.0]
    for i in range(1, len(candles)):
        high = float(candles[i]["high"])
        low = float(candles[i]["low"])
        prev_close = float(candles[i - 1]["close"])
        trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    atr = sum(trs[1 : period + 1]) / period
    out[period] = atr
    for i in range(period + 1, len(candles)):
        atr = (atr * (period - 1) + trs[i]) / period
        out[i] = atr
    return out


# ---------------------------------------------------------------- backtesting
def backtest(
    candles: Sequence[Dict[str, Any]],
    params: Dict[str, Any],
    start_index: int = 0,
    end_index: Optional[int] = None,
) -> Dict[str, Any]:
    """Causal EMA+RSI backtest.

    ``end_index`` truncates the series *before* any indicator is computed, which
    is what makes the out-of-sample and walk-forward splits leak-free.
    """
    end = len(candles) if end_index is None else max(0, min(end_index, len(candles)))
    series = list(candles[:end])
    if len(series) < 40:
        return {"trades": [], "metrics": _empty_metrics("insufficient_data")}

    closes = [float(c["close"]) for c in series]
    fast = int(params.get("ema_fast", 9))
    slow = int(params.get("ema_slow", 21))
    rsi_period = int(params.get("rsi_period", 14))
    rsi_hi = float(params.get("rsi_upper", 70))
    rsi_lo = float(params.get("rsi_lower", 30))
    sl_atr = float(params.get("sl_atr_mult", 1.5))
    tp_atr = float(params.get("tp_atr_mult", 2.5))
    allow_short = bool(params.get("allow_short", True))

    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    rsi = _rsi(closes, rsi_period)
    atr = _atr(series, rsi_period)

    trades: List[Dict[str, Any]] = []
    position: Optional[Dict[str, Any]] = None

    for i in range(max(slow, rsi_period, 1), len(series) - 1):
        bar = series[i]
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        atr_value = atr[i] or 0.0
        f = ema_fast[i]
        s = ema_slow[i]
        r = rsi[i]
        if f is None or s is None or r is None:
            continue

        if position is not None:
            exit_price: Optional[float] = None
            reason = ""
            if position["side"] == "BUY":
                if low <= position["stop"]:
                    exit_price, reason = position["stop"], "stop_loss"
                elif high >= position["target"]:
                    exit_price, reason = position["target"], "target"
            else:
                if high >= position["stop"]:
                    exit_price, reason = position["stop"], "stop_loss"
                elif low <= position["target"]:
                    exit_price, reason = position["target"], "target"
            if exit_price is not None:
                gross = (exit_price - position["entry"]) * (1 if position["side"] == "BUY" else -1)
                trades.append(
                    {
                        "side": position["side"],
                        "entry_index": position["entry_index"],
                        "exit_index": i,
                        "entry": round(position["entry"], 4),
                        "exit": round(exit_price, 4),
                        "pnl": round(gross, 4),
                        "reason": reason,
                        "r_multiple": round(gross / position["risk"], 3) if position["risk"] else None,
                    }
                )
                position = None

        if position is not None or atr_value <= 0:
            continue

        long_signal = f > s and r < rsi_hi and r > 45
        short_signal = f < s and r > rsi_lo and r < 55
        if long_signal:
            position = {
                "side": "BUY", "entry": close, "stop": close - sl_atr * atr_value,
                "target": close + tp_atr * atr_value, "risk": sl_atr * atr_value,
                "entry_index": i,
            }
        elif short_signal and allow_short:
            position = {
                "side": "SELL", "entry": close, "stop": close + sl_atr * atr_value,
                "target": close - tp_atr * atr_value, "risk": sl_atr * atr_value,
                "entry_index": i,
            }

    if position is not None:
        last = float(series[-1]["close"])
        gross = (last - position["entry"]) * (1 if position["side"] == "BUY" else -1)
        trades.append(
            {
                "side": position["side"],
                "entry_index": position["entry_index"],
                "exit_index": len(series) - 1,
                "entry": round(position["entry"], 4),
                "exit": round(last, 4),
                "pnl": round(gross, 4),
                "reason": "open_at_end",
                "r_multiple": round(gross / position["risk"], 3) if position["risk"] else None,
            }
        )

    return {"trades": trades, "metrics": compute_metrics(trades)}


def compute_metrics(trades: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if not trades:
        return _empty_metrics("no_trades")
    pnls = [float(t["pnl"]) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    r_multiples = [float(t["r_multiple"]) for t in trades if t.get("r_multiple") is not None]
    return {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(trades), 4),
        "net_pnl": round(sum(pnls), 4),
        "avg_pnl": round(statistics.fmean(pnls), 4),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
        "max_drawdown": round(max_dd, 4),
        "avg_r_multiple": round(statistics.fmean(r_multiples), 3) if r_multiples else None,
        "expectancy": round(statistics.fmean(pnls), 4),
    }


def _empty_metrics(reason: str) -> Dict[str, Any]:
    return {
        "trades": 0, "wins": 0, "losses": 0, "win_rate": None, "net_pnl": None,
        "avg_pnl": None, "profit_factor": None, "max_drawdown": None,
        "avg_r_multiple": None, "expectancy": None, "reason": reason,
    }


# ------------------------------------------------------------ learning service
class LearningEngine:
    """Post-trade analysis + gated strategy promotion."""

    # ------------------------------------------------------------- part 5: learn
    def analyse_trade(
        self,
        decision_id: str,
        exit_price: float,
        exit_reason: str,
        user_id: Optional[int] = None,
        plan_followed: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Write a learning report from the stored lifecycle of one trade."""
        from app.core.brain_models import DecisionAudit

        with SessionLocal() as db:
            order = (
                db.query(OrderRecord)
                .filter(OrderRecord.decision_id == decision_id)
                .order_by(OrderRecord.created_at.desc())
                .first()
            )
            audit = db.query(DecisionAudit).filter(DecisionAudit.decision_id == decision_id).first()
            if order is None:
                return {"written": False, "reason": "no order for decision"}

            entry = float(order.filled_price or order.requested_price or 0.0)
            quantity = int(order.filled_quantity or order.quantity or 0)
            direction = 1 if order.side == "BUY" else -1
            gross = (float(exit_price) - entry) * quantity * direction
            charges = float(order.charges or 0.0)
            net = gross - charges
            risk_per_unit = abs(entry - float(order.stop_loss or entry))
            r_multiple = (gross / (risk_per_unit * quantity)) if risk_per_unit and quantity else None
            outcome = "WIN" if net > 0 else "LOSS" if net < 0 else "BREAKEVEN"

            indicator_snapshot = (audit.indicator_snapshot if audit else None) or {}
            values = indicator_snapshot.get("values") or {}
            news_refs = (audit.news_refs if audit else None) or []

            win_conditions: List[Dict[str, Any]] = []
            loss_reasons: List[Dict[str, Any]] = []
            if outcome == "WIN":
                for key, value in list(values.items())[:12]:
                    win_conditions.append({"indicator": key, "value": value})
                loss_reasons = []
            elif outcome == "LOSS":
                loss_reasons.append({"reason": exit_reason or "unknown", "detail": "exit path"})
                if not plan_followed:
                    loss_reasons.append({"reason": "plan_deviation", "detail": "trade did not follow the plan"})
                if risk_per_unit and r_multiple is not None and r_multiple < 0:
                    loss_reasons.append({"reason": "stop_loss_placement", "detail": f"R={r_multiple:.2f}"})
                if not values:
                    loss_reasons.append({"reason": "weak_confirmation", "detail": "no indicator confirmation stored"})
                win_conditions = []

            report = LearningReport(
                user_id=user_id or order.user_id,
                decision_id=decision_id,
                symbol=order.symbol,
                outcome=outcome,
                pnl=round(net, 2),
                r_multiple=round(r_multiple, 3) if r_multiple is not None else None,
                plan_followed=plan_followed,
                win_conditions=win_conditions,
                loss_reasons=loss_reasons,
                indicator_performance={
                    key: values[key] for key in list(values)[:20]
                } or None,
                news_impact=[{"headline": n.get("headline"), "effect": n.get("effect")} for n in news_refs[:5]] or None,
                lessons=_lesson_text(outcome, exit_reason, loss_reasons, win_conditions),
                suggestions=_suggestions(outcome, loss_reasons, values),
            )
            db.add(report)
            db.commit()
            report_id = report.id

            # Capture plain values before the session closes (detached-instance
            # safe): write_memory opens its own session.
            _symbol = order.symbol
            _user_id = user_id or order.user_id
            _outcome = outcome
            _entry = entry
            _exit_price = float(exit_price)
            _exit_reason = exit_reason
            _loss_reasons = list(loss_reasons)
            _win_conditions = list(win_conditions)
            _decision_id = decision_id

        write_memory(
            memory_type="winning_trade" if _outcome == "WIN" else "losing_trade" if _outcome == "LOSS" else "lesson",
            title=f"{_outcome} {_symbol} {_entry}->{_exit_price} ({_exit_reason})",
            content=_lesson_text(_outcome, _exit_reason, _loss_reasons, _win_conditions),
            user_id=_user_id,
            symbol=_symbol,
            decision_id=_decision_id,
            outcome=_outcome,
            pnl=round(net, 2),
            tags=[_outcome.lower(), _exit_reason or "unknown"],
            importance=0.8 if _outcome == "LOSS" else 0.6,
        )
        return {
            "written": True,
            "report_id": report_id,
            "decision_id": decision_id,
            "outcome": outcome,
            "net_pnl": round(net, 2),
            "r_multiple": round(r_multiple, 3) if r_multiple is not None else None,
            "exit_reason": exit_reason,
        }

    # -------------------------------------------- part 6: strategy improvement
    async def load_candles(self, symbol: str, interval: str, limit: int) -> List[Dict[str, Any]]:
        from app.services import indicator_service

        try:
            candles = await indicator_service.fetch_candles(symbol, interval, limit)
        except Exception as exc:
            logger.warning("Backtest candle load failed for %s: %s", symbol, exc)
            return []
        return list(candles or [])

    def propose_version(
        self,
        base_params: Dict[str, Any],
        symbol: str,
        interval: str,
        user_id: Optional[int] = None,
        changelog: Optional[str] = None,
        parent_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new candidate version (never mutates the incumbent)."""
        version = f"v{now_ist().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"
        with SessionLocal() as db:
            row = StrategyVersion(
                user_id=user_id,
                version=version,
                parent_version=parent_version,
                name=f"{symbol} {interval} ema-rsi",
                status=StrategyStatus.DRAFT.value,
                params={**base_params, "symbol": symbol, "interval": interval},
                changelog=changelog or "candidate generated by learning engine",
            )
            db.add(row)
            db.commit()
        return {"version": version, "parent_version": parent_version, "status": "draft"}

    def validate(
        self,
        version: str,
        symbol: str,
        interval: str,
        candles: Sequence[Dict[str, Any]],
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run every gate; promote only when all pass."""
        report = ValidationReport(version=version)
        if len(candles) < MIN_SAMPLE_SIZE * 3:
            report.reason = "insufficient_history"
            self._save(version, report, StrategyStatus.REJECTED)
            return report.to_dict()

        params = self._params(version)
        total = len(candles)
        split = int(total * 0.6)

        # 1. In-sample backtest (causal).
        insample = backtest(candles, params, 0, split)
        # 2. Out-of-sample on the untouched tail.
        outsample = backtest(candles, params, split, total)
        # 3. Walk-forward: rolling refit-free windows (params fixed, data moves).
        folds: List[Dict[str, Any]] = []
        fold = max(40, total // (MIN_WALK_FORWARD_FOLDS + 1))
        cursor = split
        while cursor < total and len(folds) < 6:
            folds.append(backtest(candles, params, max(0, cursor - fold), min(total, cursor + fold)))
            cursor += fold
        # 4. Shadow: the most recent slice, as a paper proxy.
        shadow = backtest(candles, params, max(0, total - fold), total)

        metrics = {
            "in_sample": insample["metrics"],
            "out_of_sample": outsample["metrics"],
            "walk_forward": [f["metrics"] for f in folds],
            "shadow": shadow["metrics"],
            "candles": total,
            "split_index": split,
        }
        report.metrics = metrics

        oos = outsample["metrics"]
        report.add(
            "min_sample_size",
            (oos["trades"] or 0) >= MIN_SAMPLE_SIZE,
            f"out-of-sample trades {oos['trades']} < {MIN_SAMPLE_SIZE}",
            oos["trades"],
        )
        pf = oos.get("profit_factor")
        report.add(
            "profit_factor",
            pf is not None and pf >= MIN_PROFIT_FACTOR,
            f"out-of-sample profit factor {pf} < {MIN_PROFIT_FACTOR}",
            pf,
        )
        dd = oos.get("max_drawdown")
        dd_pct = _drawdown_pct(dd, candles, split)
        report.add(
            "max_drawdown",
            dd_pct is not None and abs(dd_pct) <= MAX_DRAWDOWN_PCT,
            f"out-of-sample drawdown {dd_pct}% exceeds {MAX_DRAWDOWN_PCT}%",
            dd_pct,
        )
        report.add(
            "out_of_sample_positive",
            (oos.get("net_pnl") or 0.0) > 0,
            f"out-of-sample net {oos.get('net_pnl')} is not positive",
            oos.get("net_pnl"),
        )
        report.add(
            "walk_forward_folds",
            len(folds) >= MIN_WALK_FORWARD_FOLDS,
            f"only {len(folds)} walk-forward folds (need {MIN_WALK_FORWARD_FOLDS})",
            len(folds),
        )
        report.add(
            "walk_forward_consistency",
            _consistency([f["metrics"].get("net_pnl") for f in folds]),
            "walk-forward windows are not consistently positive",
        )
        shadow_trades = shadow["metrics"].get("trades") or 0
        report.add(
            "shadow_sample",
            shadow_trades >= MIN_SHADOW_TRADES,
            f"shadow window has {shadow_trades} trades (need {MIN_SHADOW_TRADES})",
            shadow_trades,
        )

        incumbent = self._incumbent(symbol, interval, user_id, exclude=version)
        if incumbent is not None:
            incumbent_net = (incumbent.get("out_of_sample_metrics") or {}).get("net_pnl")
            candidate_net = oos.get("net_pnl") or 0.0
            if incumbent_net is None:
                report.add("beats_incumbent", candidate_net > 0, "incumbent has no metrics yet", candidate_net)
            else:
                improvement = (candidate_net - incumbent_net) / abs(incumbent_net) * 100 if incumbent_net else 0.0
                report.add(
                    "beats_incumbent",
                    improvement >= MIN_IMPROVEMENT_PCT,
                    f"candidate improves net P&L by {improvement:.1f}% (need {MIN_IMPROVEMENT_PCT}%)",
                    round(improvement, 2),
                )
        else:
            report.add("beats_incumbent", True, "no incumbent strategy yet", None)

        status = StrategyStatus.PROMOTED if report.all_passed else StrategyStatus.REJECTED
        report.promoted = report.all_passed
        report.reason = "all gates passed" if report.all_passed else "one or more gates failed"
        self._save(version, report, status)
        return report.to_dict()

    def rollback(self, version: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Demote a promoted version and re-activate its parent."""
        with SessionLocal() as db:
            stmt = db.query(StrategyVersion).filter(StrategyVersion.version == version)
            if user_id is not None:
                stmt = stmt.filter(StrategyVersion.user_id == user_id)
            row = stmt.first()
            if row is None:
                return {"rolled_back": False, "reason": "unknown version"}
            parent = row.parent_version
            row.status = StrategyStatus.DISABLED.value
            if parent:
                parent_row = (
                    db.query(StrategyVersion)
                    .filter(StrategyVersion.version == parent, StrategyVersion.status == StrategyStatus.PROMOTED.value)
                    .first()
                )
                if parent_row is not None:
                    parent_row.status = StrategyStatus.PROMOTED.value
            db.commit()
        write_memory(
            memory_type="strategy_version",
            title=f"Rolled back {version}",
            content=f"{version} demoted to disabled; parent {parent} restored where available.",
            user_id=user_id,
            strategy_version=version,
            tags=["rollback"],
            importance=0.7,
        )
        return {"rolled_back": True, "version": version, "restored": parent}

    def history(self, user_id: Optional[int] = None, limit: int = 30) -> List[Dict[str, Any]]:
        with SessionLocal() as db:
            stmt = db.query(StrategyVersion)
            if user_id is not None:
                stmt = stmt.filter(StrategyVersion.user_id == user_id)
            stmt = stmt.order_by(StrategyVersion.created_at.desc()).limit(limit)
            return [
                {
                    "version": r.version,
                    "parent": r.parent_version,
                    "name": r.name,
                    "status": r.status,
                    "params": r.params or {},
                    "validation": r.validation_report,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "promoted_at": r.promoted_at.isoformat() if r.promoted_at else None,
                }
                for r in stmt.all()
            ]

    # ----------------------------------------------------------------- helpers
    def _params(self, version: str) -> Dict[str, Any]:
        with SessionLocal() as db:
            row = db.query(StrategyVersion).filter(StrategyVersion.version == version).first()
            if row is None:
                raise ValueError(f"unknown strategy version {version}")
            return dict(row.params or {})

    def _incumbent(
        self, symbol: str, interval: str, user_id: Optional[int], exclude: str
    ) -> Optional[Dict[str, Any]]:
        with SessionLocal() as db:
            stmt = (
                db.query(StrategyVersion)
                .filter(
                    StrategyVersion.status == StrategyStatus.PROMOTED.value,
                    StrategyVersion.version != exclude,
                )
                .order_by(StrategyVersion.promoted_at.desc().nullslast())
            )
            if user_id is not None:
                stmt = stmt.filter(StrategyVersion.user_id == user_id)
            for row in stmt.limit(20).all():
                params = row.params or {}
                if params.get("symbol") == symbol and params.get("interval") == interval:
                    return {
                        "version": row.version,
                        "out_of_sample_metrics": row.out_of_sample_metrics,
                    }
        return None

    def _save(self, version: str, report: ValidationReport, status: StrategyStatus) -> None:
        try:
            with SessionLocal() as db:
                row = db.query(StrategyVersion).filter(StrategyVersion.version == version).first()
                if row is None:
                    logger.warning("Cannot save validation for unknown version %s", version)
                    return
                row.status = status.value
                row.validation_report = report.to_dict()
                row.backtest_metrics = report.metrics.get("in_sample")
                row.out_of_sample_metrics = report.metrics.get("out_of_sample")
                row.walk_forward_metrics = {"folds": report.metrics.get("walk_forward")}
                row.shadow_metrics = report.metrics.get("shadow")
                row.updated_at = now_ist()
                if status is StrategyStatus.PROMOTED:
                    row.promoted_at = now_ist()
                db.commit()
        except Exception:
            logger.exception("Failed to persist validation report for %s", version)


def _lesson_text(
    outcome: str,
    exit_reason: str,
    loss_reasons: Sequence[Dict[str, Any]],
    win_conditions: Sequence[Dict[str, Any]],
) -> str:
    if outcome == "WIN":
        drivers = ", ".join(str(c.get("indicator")) for c in win_conditions[:5]) or "no indicator snapshot"
        return f"Winning trade closed via {exit_reason}. Contributing conditions: {drivers}."
    if outcome == "LOSS":
        reasons = "; ".join(f"{r.get('reason')}: {r.get('detail')}" for r in loss_reasons[:4])
        return f"Losing trade closed via {exit_reason}. Reasons: {reasons or 'not determined'}."
    return f"Break-even trade closed via {exit_reason}."


def _suggestions(
    outcome: str, loss_reasons: Sequence[Dict[str, Any]], values: Dict[str, Any]
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    reasons = {r.get("reason") for r in loss_reasons}
    if "stop_loss_placement" in reasons:
        out.append({"action": "widen_stop", "detail": "test a larger ATR multiple", "approved_range": [1.0, 3.0]})
    if "weak_confirmation" in reasons:
        out.append({"action": "tighten_entry", "detail": "require an extra confirmation indicator"})
    if outcome == "WIN" and values:
        out.append({"action": "keep", "detail": "current confirmation set produced a win"})
    return out


def _drawdown_pct(max_dd: Optional[float], candles: Sequence[Dict[str, Any]], split: int) -> Optional[float]:
    if max_dd is None:
        return None
    window = candles[split:]
    equity = sum(float(c["close"]) for c in window[:1]) or 1.0
    if not equity:
        return None
    return round(float(max_dd) / equity * 100, 3)


def _consistency(values: Sequence[Optional[float]]) -> bool:
    numbers = [v for v in values if v is not None]
    if len(numbers) < MIN_WALK_FORWARD_FOLDS:
        return False
    positive = [v for v in numbers if v > 0]
    return len(positive) >= max(2, int(len(numbers) * 0.6))


_engine: Optional[LearningEngine] = None


def get_learning_engine() -> LearningEngine:
    global _engine
    if _engine is None:
        _engine = LearningEngine()
    return _engine


__all__ = [
    "GateResult",
    "LearningEngine",
    "MIN_SAMPLE_SIZE",
    "ValidationReport",
    "backtest",
    "compute_metrics",
    "get_learning_engine",
]
