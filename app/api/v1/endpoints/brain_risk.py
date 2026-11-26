"""Risk configuration, kill switch and emergency controls.

This router is the **only** writer of ``risk_configs`` and ``kill_switches``.
The AI Brain has no import path to these tables' write side: the decision engine
and execution service only ever read them through ``risk_engine``.

Routes (all under ``/api/v1/brain/risk``):

* ``GET    /config``            current limits + usage
* ``PUT    /config``            update limits (admin or owner)
* ``POST   /kill-switch``        activate the emergency stop
* ``DELETE /kill-switch``        reset it (explicit user action)
* ``POST   /emergency-exit``     apply the configured exit policy now
* ``GET    /events``             recent risk decisions
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, get_db
from app.core.brain_models import RiskConfig, RiskEvent
from app.core.datetime_utils import now_ist
from app.services.brain.execution_service import get_execution_service
from app.services.brain.risk_engine import get_risk_engine, kill_switch_active, load_config

logger = logging.getLogger(__name__)
router = APIRouter()


# --------------------------------------------------------------------- schemas
class RiskConfigUpdate(BaseModel):
    master_autonomous_enabled: Optional[bool] = None
    trading_mode: Optional[str] = Field(None, description="paper | live")
    allowed_instruments: Optional[List[str]] = None
    allowed_segments: Optional[List[str]] = None
    max_risk_per_trade_pct: Optional[float] = Field(None, ge=0.0, le=100.0)
    max_daily_loss: Optional[float] = Field(None, ge=0.0)
    max_total_open_positions: Optional[int] = Field(None, ge=0, le=50)
    max_position_size: Optional[int] = Field(None, ge=0)
    max_daily_trades: Optional[int] = Field(None, ge=0, le=200)
    max_portfolio_exposure: Optional[float] = Field(None, ge=0.0)
    max_consecutive_losses: Optional[int] = Field(None, ge=0, le=20)
    session_start: Optional[str] = None
    session_end: Optional[str] = None
    square_off_time: Optional[str] = None
    emergency_exit_policy: Optional[str] = Field(None, description="hold | flatten")
    require_stop_loss: Optional[bool] = None
    min_risk_reward: Optional[float] = Field(None, ge=0.0, le=20.0)
    max_spread_pct: Optional[float] = Field(None, ge=0.0, le=100.0)


class KillSwitchRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)
    exit_policy: Optional[str] = Field(None, description="hold | flatten")


class KillSwitchReset(BaseModel):
    note: str = Field("manual reset", max_length=300)


def _config_dict(config: RiskConfig) -> Dict[str, Any]:
    return {
        "user_id": config.user_id,
        "master_autonomous_enabled": config.master_autonomous_enabled,
        "trading_mode": config.trading_mode,
        "allowed_instruments": config.allowed_instruments or [],
        "allowed_segments": config.allowed_segments or [],
        "max_risk_per_trade_pct": config.max_risk_per_trade_pct,
        "max_daily_loss": config.max_daily_loss,
        "max_total_open_positions": config.max_total_open_positions,
        "max_position_size": config.max_position_size,
        "max_daily_trades": config.max_daily_trades,
        "max_portfolio_exposure": config.max_portfolio_exposure,
        "max_consecutive_losses": config.max_consecutive_losses,
        "session_start": config.session_start,
        "session_end": config.session_end,
        "square_off_time": config.square_off_time,
        "emergency_exit_policy": config.emergency_exit_policy,
        "require_stop_loss": config.require_stop_loss,
        "min_risk_reward": config.min_risk_reward,
        "max_spread_pct": config.max_spread_pct,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


# ------------------------------------------------------------------- endpoints
@router.get("/config")
async def get_config(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Current limits, live usage and kill-switch state."""
    config = load_config(db, current_user.id)
    engine = get_risk_engine()
    switch = kill_switch_active(db, current_user.id)
    return {
        "config": _config_dict(config),
        "usage": engine.daily_usage(current_user.id),
        "consecutive_losses": engine.consecutive_losses(current_user.id),
        "kill_switch": {
            "active": switch is not None,
            "reason": switch.reason if switch else None,
            "activated_by": switch.activated_by if switch else None,
            "activated_at": switch.activated_at.isoformat() if switch and switch.activated_at else None,
            "exit_policy": switch.exit_policy if switch else config.emergency_exit_policy,
        },
        "server_time": now_ist().isoformat(),
    }


@router.put("/config")
async def update_config(
    payload: RiskConfigUpdate,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Persist new limits.  The AI cannot call this: it needs a user JWT."""
    config = db.query(RiskConfig).filter(RiskConfig.user_id == current_user.id).first()
    if config is None:
        config = load_config(db, current_user.id)
        db.add(config)
    changes = payload.model_dump(exclude_none=True)
    if "trading_mode" in changes:
        mode = str(changes["trading_mode"]).lower()
        if mode not in {"paper", "live"}:
            raise HTTPException(status_code=400, detail="trading_mode must be 'paper' or 'live'")
        changes["trading_mode"] = mode
    if "emergency_exit_policy" in changes:
        policy = str(changes["emergency_exit_policy"]).lower()
        if policy not in {"hold", "flatten"}:
            raise HTTPException(status_code=400, detail="emergency_exit_policy must be 'hold' or 'flatten'")
        changes["emergency_exit_policy"] = policy
    for key, value in changes.items():
        setattr(config, key, value)
    config.updated_at = now_ist()
    db.commit()
    db.add(
        RiskEvent(
            user_id=current_user.id,
            event_type="risk_config_updated",
            allowed=True,
            reason="user updated risk configuration",
            details={"changed": sorted(changes.keys()), "source": "api"},
        )
    )
    db.commit()
    logger.info("Risk config updated for user %s: %s", current_user.id, sorted(changes.keys()))
    return {"updated": sorted(changes.keys()), "config": _config_dict(config)}


@router.post("/kill-switch")
async def activate(
    payload: KillSwitchRequest,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Emergency stop: no new orders are validated while this is active."""
    config = load_config(db, current_user.id)
    policy = (payload.exit_policy or config.emergency_exit_policy or "hold").lower()
    state = get_risk_engine().activate_kill_switch(
        user_id=current_user.id,
        reason=payload.reason,
        activated_by="user",
        exit_policy=policy,
    )
    await _notify_kill_switch(current_user.id, payload.reason, policy)
    return state


@router.delete("/kill-switch")
async def reset(
    payload: KillSwitchReset,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Clear the stop.  Requires an explicit, deliberate user action."""
    state = get_risk_engine().reset_kill_switch(current_user.id, payload.note)
    return state


@router.post("/emergency-exit")
async def emergency_exit(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Apply the configured exit policy to open positions right now."""
    config = load_config(db, current_user.id)
    result = await get_execution_service().emergency_exit(current_user.id, config.emergency_exit_policy)
    db.add(
        RiskEvent(
            user_id=current_user.id,
            event_type="emergency_exit",
            allowed=True,
            reason=f"policy={config.emergency_exit_policy}",
            details=result,
        )
    )
    db.commit()
    return result


@router.get("/events")
async def events(
    limit: int = 50,
    event_type: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Recent risk decisions, newest first (audit trail)."""
    query = (
        db.query(RiskEvent)
        .filter((RiskEvent.user_id == current_user.id) | (RiskEvent.user_id.is_(None)))
        .order_by(RiskEvent.created_at.desc())
        .limit(max(1, min(limit, 200)))
    )
    if event_type:
        query = query.filter(RiskEvent.event_type == event_type)
    return {
        "events": [
            {
                "id": row.id,
                "event_type": row.event_type,
                "allowed": row.allowed,
                "reason": row.reason,
                "decision_id": row.decision_id,
                "details": row.details,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in query.all()
        ]
    }


async def _notify_kill_switch(user_id: int, reason: str, policy: str) -> None:
    """Best-effort Telegram alert; never blocks the response."""
    try:
        from app.core.config import settings
        from app.services.telegram_notifier import TelegramNotifier

        if not (settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID):
            return
        notifier = TelegramNotifier(settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID)
        await notifier.send_message(
            f"🔴 KILL SWITCH ACTIVATED\nReason: {reason}\nExit policy: {policy}\n"
            f"Time: {now_ist().strftime('%Y-%m-%d %H:%M:%S IST')}"
        )
    except Exception:
        logger.exception("Kill-switch notification failed")


__all__ = ["router"]
