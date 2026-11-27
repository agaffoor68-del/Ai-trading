"""Strategy Builder API.

Routes (all under ``/api/v1/strategies``):

* ``GET    /``                 list the current user's strategies
* ``POST   /``                 create a strategy
* ``GET    /{strategy_id}``    fetch one strategy
* ``PUT    /{strategy_id}``    update a strategy (partial update allowed)
* ``DELETE /{strategy_id}``    delete a strategy

Every route is authenticated and scoped to ``current_user.id``; one user can
never read or modify another user's strategies.  The older ``POST``/``PUT``/
``DELETE`` calls that carried ``{"id": ...}`` in the body are still accepted so
the existing Strategy Builder page keeps working.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, get_db
from app.core.datetime_utils import now_ist
from app.core.strategy_models import UserStrategy
from app.core.models import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["strategies"])

MAX_CONDITIONS = 30


# --------------------------------------------------------------------- schemas
class StrategyCondition(BaseModel):
    id: Optional[str] = None
    indicator1: Optional[str] = None
    condition: Optional[str] = None
    indicator2: Optional[str] = None
    value: Optional[float] = None
    timeframe: Optional[str] = None


class StrategyPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=2000)
    conditions: List[StrategyCondition] = Field(default_factory=list)
    timeframe: str = Field("15m", max_length=16)
    stopLoss: Optional[float] = Field(None, ge=0, le=100)
    target: Optional[float] = Field(None, ge=0, le=1000)
    isActive: bool = False
    indicators: List[str] = Field(default_factory=list)
    # Legacy body-based identity, still sent by the existing UI.
    id: Optional[int] = None


class StrategyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=2000)
    conditions: Optional[List[StrategyCondition]] = None
    timeframe: Optional[str] = Field(None, max_length=16)
    stopLoss: Optional[float] = Field(None, ge=0, le=100)
    target: Optional[float] = Field(None, ge=0, le=1000)
    isActive: Optional[bool] = None
    indicators: Optional[List[str]] = None
    id: Optional[int] = None


# --------------------------------------------------------------------- helpers
def _owned(db: Session, strategy_id: int, user_id: int) -> UserStrategy:
    row = (
        db.query(UserStrategy)
        .filter(
            UserStrategy.id == strategy_id,
            UserStrategy.user_id == user_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return row


def _conditions(payload: Optional[List[StrategyCondition]]) -> List[dict]:
    if not payload:
        return []
    if len(payload) > MAX_CONDITIONS:
        raise HTTPException(
            status_code=422,
            detail=f"At most {MAX_CONDITIONS} conditions are allowed",
        )
    out: List[dict] = []
    for item in payload:
        if not item.indicator1 or not item.condition:
            raise HTTPException(
                status_code=422,
                detail="Each condition needs indicator1 and condition",
            )
        out.append(item.model_dump(exclude_none=True))
    return out


def _apply(row: UserStrategy, data: dict) -> UserStrategy:
    if "name" in data and data["name"] is not None:
        row.name = data["name"]
    if "description" in data:
        row.description = data["description"]
    if "conditions" in data and data["conditions"] is not None:
        row.conditions = _conditions(data["conditions"])
    if data.get("timeframe"):
        row.timeframe = data["timeframe"]
    if "stopLoss" in data:
        row.stop_loss_pct = data["stopLoss"]
    if "target" in data:
        row.target_pct = data["target"]
    if "indicators" in data and data["indicators"] is not None:
        row.indicators = data["indicators"]
    if "isActive" in data and data["isActive"] is not None:
        row.is_active = bool(data["isActive"])
    row.updated_at = now_ist()
    return row


# ----------------------------------------------------------------------- routes
@router.get("")
@router.get("/")
async def list_strategies(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    active_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List the caller's strategies, newest first."""
    query = db.query(UserStrategy).filter(UserStrategy.user_id == current_user.id)
    if active_only:
        query = query.filter(UserStrategy.is_active.is_(True))
    total = query.count()
    rows = (
        query.order_by(UserStrategy.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    strategies = [row.to_dict() for row in rows]
    # The UI accepts either a bare array or {strategies: [...]}; return both
    # keys plus the array-friendly envelope it already handles.
    return {
        "strategies": strategies,
        "items": strategies,
        "total": total,
        "count": len(strategies),
    }


@router.post("", status_code=201)
@router.post("/", status_code=201)
async def create_strategy(
    payload: StrategyPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a strategy owned by the caller."""
    row = UserStrategy(
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        conditions=_conditions(payload.conditions),
        timeframe=payload.timeframe,
        stop_loss_pct=payload.stopLoss,
        target_pct=payload.target,
        indicators=payload.indicators or [],
        is_active=bool(payload.isActive),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(
        "Strategy %s created for user %s", row.id, current_user.id
    )
    return {"strategy": row.to_dict(), **row.to_dict()}


@router.get("/{strategy_id}")
async def get_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Fetch one of the caller's strategies."""
    row = _owned(db, strategy_id, current_user.id)
    return {"strategy": row.to_dict(), **row.to_dict()}


@router.put("/{strategy_id}")
async def update_strategy(
    strategy_id: int,
    payload: StrategyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update one of the caller's strategies."""
    row = _owned(db, strategy_id, current_user.id)
    _apply(row, payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(row)
    return {"strategy": row.to_dict(), **row.to_dict()}


@router.delete("/{strategy_id}")
async def delete_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete one of the caller's strategies."""
    row = _owned(db, strategy_id, current_user.id)
    db.delete(row)
    db.commit()
    logger.info("Strategy %s deleted for user %s", strategy_id, current_user.id)
    return {"deleted": True, "id": strategy_id}


__all__ = ["router"]
