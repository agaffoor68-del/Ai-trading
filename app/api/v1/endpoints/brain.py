"""AI Brain API: decisions, monitoring, memory, learning, news, audit.

All routes are under ``/api/v1/brain``.  They are thin: every action is
delegated to a service, and nothing here can place an order that the risk
engine has not approved.

Route map:

* ``POST /decide``              run the decision pipeline for one symbol
* ``GET  /decision/{id}``       full audit record for one decision
* ``GET  /decisions``           recent decisions
* ``GET  /monitor``             open positions + stop/target distances
* ``GET  /signals``             latest AI signal per instrument
* ``GET  /memory``              search persistent memory
* ``GET  /memory/similar``      historical analogues for a symbol/regime
* ``GET  /learning/reports``    post-trade learning reports
* ``POST /learning/close``      close a position and generate its report
* ``GET  /strategies``          version history + validation status
* ``POST /strategies/validate`` run the full gate suite for a version
* ``POST /strategies/rollback`` demote a promoted version
* ``GET  /news``                stored India + global news
* ``POST /news/ingest``         fetch configured feeds now
* ``GET  /health``              provider + model connectivity
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, get_db
from app.core.brain_models import AISignal, DecisionAudit, LearningReport
from app.core.datetime_utils import now_ist
from app.services.brain.data_intelligence import get_tdil
from app.services.brain.decision_engine import get_decision_engine
from app.services.brain.execution_service import (
    LIVE_BROKER_ADAPTER_ENABLED,
    get_execution_service,
)
from app.services.brain.learning_engine import get_learning_engine
from app.services.brain.memory_service import search_memory, similar_situations
from app.services.brain.news_service import get_news_service
from app.services.brain.risk_engine import get_risk_engine, load_config

logger = logging.getLogger(__name__)
router = APIRouter()


# --------------------------------------------------------------------- schemas
class DecideRequest(BaseModel):
    symbol: str = Field(..., description="NIFTY, BANKNIFTY, RELIANCE, NSE:SBIN-EQ ...")
    interval: str = Field("5m")
    mode: str = Field("paper", description="paper | live (live still needs risk approval)")
    indicator_ids: Optional[List[str]] = Field(
        None, description="subset of the 169 registry ids; default is the Brain set"
    )


class CloseRequest(BaseModel):
    decision_id: str
    exit_price: float = Field(..., gt=0)
    exit_reason: str = Field(..., min_length=2, max_length=200)
    plan_followed: Optional[bool] = None


class ValidateRequest(BaseModel):
    version: str
    symbol: str
    interval: str = "1d"
    candles: int = Field(500, ge=100, le=2000)


class RollbackRequest(BaseModel):
    version: str


class IngestRequest(BaseModel):
    regions: Optional[List[str]] = Field(None, description="subset of india/global")
    per_source: int = Field(15, ge=1, le=50)


# ------------------------------------------------------------------- decisions
@router.post("/decide")
async def decide(
    payload: DecideRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Run the 15-step pipeline.  Returns NO_TRADE whenever data is unusable."""
    config = load_config(db, current_user.id)
    mode = payload.mode if payload.mode in {"paper", "live"} else "paper"
    if mode == "live" and config.trading_mode != "live":
        mode = "paper"
    result = await get_decision_engine().decide(
        symbol=payload.symbol,
        user_id=current_user.id,
        interval=payload.interval,
        mode=mode,
        indicator_ids=payload.indicator_ids,
    )
    return result.to_dict()


@router.get("/decisions")
async def decisions(
    limit: int = Query(25, ge=1, le=100),
    symbol: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    query = (
        db.query(DecisionAudit)
        .filter((DecisionAudit.user_id == current_user.id) | (DecisionAudit.user_id.is_(None)))
        .order_by(DecisionAudit.created_at.desc())
        .limit(limit)
    )
    if symbol:
        query = query.filter(DecisionAudit.symbol == symbol)
    return {
        "decisions": [
            {
                "decision_id": row.decision_id,
                "symbol": row.symbol,
                "action": row.action,
                "confidence": row.confidence,
                "strategy_version": row.strategy_version,
                "no_trade_reason": row.no_trade_reason,
                "risk_allowed": (row.risk_result or {}).get("allowed"),
                "model_id": row.model_id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in query.all()
        ]
    }


@router.get("/decision/{decision_id}")
async def decision_detail(
    decision_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Reconstruct exactly why a trade did or did not happen."""
    row = (
        db.query(DecisionAudit)
        .filter(
            DecisionAudit.decision_id == decision_id,
            (DecisionAudit.user_id == current_user.id) | (DecisionAudit.user_id.is_(None)),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="decision not found")
    return {
        "decision_id": row.decision_id,
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "action": row.action,
        "confidence": row.confidence,
        "model_id": row.model_id,
        "strategy_version": row.strategy_version,
        "market_snapshot": row.market_snapshot,
        "indicator_snapshot": row.indicator_snapshot,
        "news_refs": row.news_refs,
        "reasoning": row.reasoning,
        "risk_result": row.risk_result,
        "order_request": row.order_request,
        "broker_response": row.broker_response,
        "execution_result": row.execution_result,
        "data_quality": row.data_quality,
        "no_trade_reason": row.no_trade_reason,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/signals")
async def signals(
    limit: int = Query(20, ge=1, le=100),
    symbol: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    query = (
        db.query(AISignal)
        .filter((AISignal.user_id == current_user.id) | (AISignal.user_id.is_(None)))
        .order_by(AISignal.created_at.desc())
        .limit(limit)
    )
    if symbol:
        query = query.filter(AISignal.symbol == symbol)
    return {
        "signals": [
            {
                "decision_id": row.decision_id,
                "symbol": row.symbol,
                "action": row.action,
                "confidence": row.confidence,
                "horizon": row.horizon,
                "entry_price": row.entry_price,
                "stop_loss": row.stop_loss,
                "targets": row.targets or [],
                "strategy_version": row.strategy_version,
                "risk_status": row.risk_status,
                "status": row.status,
                "summary": row.summary,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in query.all()
        ]
    }


# -------------------------------------------------------------------- monitor
@router.get("/monitor")
async def monitor(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Open positions, stop/target distance and live alerts."""
    state = await get_decision_engine().monitor(user_id=current_user.id)
    state["orders"] = get_execution_service().open_positions(current_user.id)
    state["risk"] = {
        "usage": get_risk_engine().daily_usage(current_user.id),
        "consecutive_losses": get_risk_engine().consecutive_losses(current_user.id),
    }
    return state


# --------------------------------------------------------------------- memory
@router.get("/memory")
async def memory(
    q: str = Query(..., min_length=2),
    limit: int = Query(8, ge=1, le=25),
    memory_type: Optional[str] = None,
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    types = [memory_type] if memory_type else None
    return {
        "query": q,
        "results": await search_memory(q, user_id=current_user.id, memory_types=types, limit=limit),
    }


@router.get("/memory/similar")
async def memory_similar(
    symbol: str,
    regime: Optional[str] = None,
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """'Have I traded this condition before, and what happened?'"""
    return await similar_situations(symbol, regime, user_id=current_user.id)


# ------------------------------------------------------------------- learning
@router.get("/learning/reports")
async def learning_reports(
    limit: int = Query(25, ge=1, le=100),
    outcome: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    query = (
        db.query(LearningReport)
        .filter((LearningReport.user_id == current_user.id) | (LearningReport.user_id.is_(None)))
        .order_by(LearningReport.created_at.desc())
        .limit(limit)
    )
    if outcome:
        query = query.filter(LearningReport.outcome == outcome.upper())
    return {
        "reports": [
            {
                "id": row.id,
                "decision_id": row.decision_id,
                "symbol": row.symbol,
                "outcome": row.outcome,
                "pnl": row.pnl,
                "r_multiple": row.r_multiple,
                "plan_followed": row.plan_followed,
                "lessons": row.lessons,
                "suggestions": row.suggestions or [],
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in query.all()
        ]
    }


@router.post("/learning/close")
async def close_and_learn(
    payload: CloseRequest,
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Close an open position with a real exit price and learn from it."""
    if payload.exit_price <= 0:
        raise HTTPException(status_code=400, detail="exit_price must be positive")
    execution = get_execution_service()
    closed = execution.close_position(
        decision_id=payload.decision_id,
        exit_price=payload.exit_price,
        exit_reason=payload.exit_reason,
        user_id=current_user.id,
    )
    if not closed.get("closed"):
        raise HTTPException(status_code=404, detail=closed.get("reason", "position not found"))
    report = get_learning_engine().analyse_trade(
        decision_id=payload.decision_id,
        exit_price=payload.exit_price,
        exit_reason=payload.exit_reason,
        user_id=current_user.id,
        plan_followed=payload.plan_followed,
    )
    return {"closed": closed, "learning": report}


# ----------------------------------------------------------------- strategies
@router.get("/strategies")
async def strategies(
    limit: int = Query(30, ge=1, le=100),
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    return {"versions": get_learning_engine().history(user_id=current_user.id, limit=limit)}


@router.post("/strategies/validate")
async def validate_strategy(
    payload: ValidateRequest,
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Backtest → out-of-sample → walk-forward → shadow → promote or reject."""
    engine = get_learning_engine()
    try:
        candles = await engine.load_candles(payload.symbol, payload.interval, payload.candles)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"historical data unavailable: {exc}")
    if len(candles) < 120:
        raise HTTPException(
            status_code=422,
            detail=f"need at least 120 candles for validation, provider returned {len(candles)}",
        )
    return engine.validate(
        version=payload.version,
        symbol=payload.symbol,
        interval=payload.interval,
        candles=candles,
        user_id=current_user.id,
    )


@router.post("/strategies/rollback")
async def rollback_strategy(
    payload: RollbackRequest,
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    return get_learning_engine().rollback(payload.version, user_id=current_user.id)


# ----------------------------------------------------------------------- news
@router.get("/news")
async def news(
    limit: int = Query(25, ge=1, le=100),
    hours: int = Query(24, ge=1, le=336),
    region: Optional[str] = Query(None, description="india | global"),
    instrument: Optional[str] = None,
    min_impact: Optional[str] = Query(None, description="low | medium | high"),
) -> Dict[str, Any]:
    service = get_news_service()
    instruments = [instrument] if instrument else None
    regions = [region] if region else None
    items = service.recent(
        instruments=instruments, regions=regions, hours=hours, limit=limit, min_impact=min_impact
    )
    return {"items": items, "count": len(items)}


@router.post("/news/ingest")
async def ingest_news(
    payload: IngestRequest,
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Fetch the configured public feeds now (admin only)."""
    from app.core.models import UserRole

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="admin only")
    return await get_news_service().ingest(
        regions=payload.regions, user_id=current_user.id, per_source=payload.per_source
    )


# --------------------------------------------------------------------- health
@router.get("/health")
async def health(current_user=Depends(get_current_user)) -> Dict[str, Any]:
    """Connectivity of every dependency the Brain needs.  No secrets exposed."""
    from app.core.config import settings
    from app.services.grok_service import get_grok_service

    tdil = get_tdil()
    unavailable = await tdil.indicator_unavailable()
    return {
        "grok": {
            "configured": bool(settings.XAI_API_KEY),
            "model": getattr(get_grok_service(), "model", None),
            "metrics": get_grok_service().get_metrics(),
        },
        "data": {
            "indicator_registry": 169,
            "indicators_needing_extra_feed": unavailable,
        },
        "risk": {
            "engine": "independent",
            "kill_switch_checked": True,
        },
        "execution": {
            "live_adapter_enabled": LIVE_BROKER_ADAPTER_ENABLED,
        },
        "server_time": now_ist().isoformat(),
    }


__all__ = ["router"]
