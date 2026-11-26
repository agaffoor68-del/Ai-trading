"""Indicator Library API.

Routes (all under ``/api/v1/indicators``):

* ``GET    /``                     library listing with filters
* ``GET    /categories``           category counts
* ``GET    /{indicator_id}``       full information panel payload
* ``POST   /calculate``            calculate a batch for one symbol
* ``POST   /batch``                same, for several symbols
* ``GET    /preferences``          current user's library state (auth)
* ``PUT    /preferences``          bulk update enabled/favourite/params (auth)

Listing and metadata are public (the library must render before login, like the
market endpoints).  ``/preferences`` requires the existing JWT dependency, and
calculation reuses the existing provider client, so no new data source is added.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import get_db, get_current_user
from app.core.models import User, UserIndicatorPreference
from app.services import indicator_service
from app.services.indicators import CATEGORIES, REGISTRY
from app.services.indicators.engine import IndicatorError

logger = logging.getLogger(__name__)
router = APIRouter()


# --------------------------------------------------------------------- schemas
class CalculateRequest(BaseModel):
    symbol: str = Field(..., description="UI symbol or Fyers ticker, e.g. NIFTY or NSE:NIFTY50-INDEX")
    interval: str = Field("5m", description="1m, 3m, 5m, 10m, 15m, 30m, 1h, 2h, 4h, 1d, 1wk, 1mo")
    indicator_ids: List[str] = Field(..., min_items=1, description="Registry ids to calculate")
    params: Dict[str, Any] = Field(default_factory=dict, description="Overrides keyed by indicator id")
    limit: int = Field(300, ge=20, le=1000, description="Candles of history")
    benchmark_symbol: Optional[str] = Field(None, description="Second symbol for beta/correlation/pair tests")
    with_options: bool = Field(False, description="Attach the option chain for derivatives indicators")
    option_symbol: Optional[str] = Field(None, description="Option chain underlying symbol")


class BatchRequest(BaseModel):
    symbols: List[str] = Field(..., min_items=1)
    interval: str = "5m"
    indicator_ids: List[str] = Field(..., min_items=1)
    params: Dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(300, ge=20, le=1000)
    benchmark_symbol: Optional[str] = None


class PreferenceItem(BaseModel):
    indicator_id: str
    enabled: Optional[bool] = None
    favorite: Optional[bool] = None
    params: Optional[Dict[str, Any]] = None


class PreferenceUpdate(BaseModel):
    items: List[PreferenceItem] = Field(..., min_items=1)


# ------------------------------------------------------------------- library
@router.get("")
async def list_indicators(
    category: Optional[str] = Query(None, description="trend, momentum, volatility, volume, levels, structure, statistics, options"),
    q: Optional[str] = Query(None, description="Free-text search"),
    status: Optional[str] = Query(None, description="implemented_tested, implemented_awaiting_data, unsupported_data"),
    market: Optional[str] = Query(None, description="NSE, BSE, NIFTY, BANKNIFTY, STOCK, FUTURES, OPTIONS, ..."),
    timeframe: Optional[str] = Query(None, description="1m, 5m, 1h, 1d, ..."),
    chart: Optional[str] = Query(None, description="overlay or pane"),
    repaint: Optional[bool] = Query(None),
    ids: Optional[str] = Query(None, description="Comma-separated id filter"),
) -> dict:
    """The full 169-indicator library with category/status metadata."""
    if category and category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Unknown category '{category}'")
    id_list = [i.strip() for i in ids.split(",") if i.strip()] if ids else None
    items = indicator_service.list_indicators(
        category=category, query=q, status=status, market=market,
        timeframe=timeframe, chart=chart, repaint=repaint, ids=id_list,
    )
    return {
        "indicators": items,
        "total": len(items),
        "library_total": len(REGISTRY),
        "categories": indicator_service.category_summary(),
    }


@router.get("/categories")
async def categories() -> dict:
    return {"categories": indicator_service.category_summary()}


@router.get("/{indicator_id}")
async def get_indicator(indicator_id: str) -> dict:
    """Information panel: description, formula, defaults, data, interpretation."""
    try:
        return indicator_service.indicator_detail(indicator_id)
    except IndicatorError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ---------------------------------------------------------------- calculation
async def _calculate(payload: CalculateRequest) -> dict:
    unknown = [i for i in payload.indicator_ids if i not in REGISTRY]
    if unknown:
        raise HTTPException(status_code=400, detail={"code": "UNKNOWN_INDICATOR", "ids": unknown})
    params = payload.params or {}
    per_indicator = {i: params[i] for i in payload.indicator_ids if isinstance(params.get(i), dict)}
    shared = {k: v for k, v in params.items() if k not in per_indicator}
    try:
        return await indicator_service.calculate_async(
            symbol=payload.symbol,
            interval=payload.interval,
            indicator_ids=payload.indicator_ids,
            params=shared or None,
            limit=payload.limit,
            benchmark_symbol=payload.benchmark_symbol,
            with_options=payload.with_options,
            option_symbol=payload.option_symbol,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except IndicatorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/calculate")
async def calculate(payload: CalculateRequest) -> dict:
    """Calculate indicators for one symbol using real provider candles."""
    return await _calculate(payload)


@router.post("/batch")
async def calculate_batch(payload: BatchRequest) -> dict:
    """Batch calculation across symbols (used by the AI signal engine)."""
    unknown = [i for i in payload.indicator_ids if i not in REGISTRY]
    if unknown:
        raise HTTPException(status_code=400, detail={"code": "UNKNOWN_INDICATOR", "ids": unknown})
    out: Dict[str, Any] = {}
    for symbol in payload.symbols:
        try:
            out[symbol] = await indicator_service.calculate_async(
                symbol=symbol,
                interval=payload.interval,
                indicator_ids=payload.indicator_ids,
                params=payload.params or None,
                limit=payload.limit,
                benchmark_symbol=payload.benchmark_symbol,
            )
        except ValueError as exc:
            out[symbol] = {"error": str(exc), "results": {}}
    return {"batch": out, "requested": payload.symbols}


# ---------------------------------------------------------------- preferences
def _ensure_tables(db: Session) -> None:
    """Create the preferences table on first use (non-destructive)."""
    try:
        UserIndicatorPreference.__table__.create(bind=db.get_bind(), checkfirst=True)
    except Exception as exc:  # pragma: no cover - permissions/DB down
        logger.warning("Could not ensure indicator preference table: %s", exc)


@router.get("/preferences")
async def get_preferences(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Library state for the signed-in user (enabled, favourites, params)."""
    _ensure_tables(db)
    rows = (
        db.query(UserIndicatorPreference)
        .filter(UserIndicatorPreference.user_id == user.id)
        .all()
    )
    prefs = {
        row.indicator_id: {
            "enabled": row.enabled,
            "favorite": row.favorite,
            "params": row.params or {},
        }
        for row in rows
    }
    enabled = [k for k, v in prefs.items() if v["enabled"]]
    favorites = [k for k, v in prefs.items() if v["favorite"]]
    return {"preferences": prefs, "enabled": enabled, "favorites": favorites}


@router.put("/preferences")
async def update_preferences(
    payload: PreferenceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Bulk update library state. Unknown ids are rejected, never ignored."""
    _ensure_tables(db)
    unknown = [i.indicator_id for i in payload.items if i.indicator_id not in REGISTRY]
    if unknown:
        raise HTTPException(status_code=400, detail={"code": "UNKNOWN_INDICATOR", "ids": unknown})

    existing = {
        row.indicator_id: row
        for row in db.query(UserIndicatorPreference)
        .filter(UserIndicatorPreference.user_id == user.id)
        .all()
    }
    updated = 0
    for item in payload.items:
        row = existing.get(item.indicator_id)
        if row is None:
            row = UserIndicatorPreference(
                user_id=user.id,
                indicator_id=item.indicator_id,
                enabled=True if item.enabled is None else item.enabled,
                favorite=bool(item.favorite),
                params=item.params or {},
            )
            db.add(row)
            existing[item.indicator_id] = row
        else:
            if item.enabled is not None:
                row.enabled = item.enabled
            if item.favorite is not None:
                row.favorite = item.favorite
            if item.params is not None:
                row.params = item.params
        updated += 1
    db.commit()
    return {"updated": updated, "items": [i.indicator_id for i in payload.items]}


@router.get("/preferences/summary")
async def preference_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Small payload for the chart toolbar (ids only)."""
    _ensure_tables(db)
    rows = db.query(UserIndicatorPreference).filter(
        UserIndicatorPreference.user_id == user.id
    ).all()
    return {
        "enabled": [r.indicator_id for r in rows if r.enabled],
        "favorites": [r.indicator_id for r in rows if r.favorite],
        "count": db.query(func.count(UserIndicatorPreference.id)).filter(
            UserIndicatorPreference.user_id == user.id
        ).scalar() or 0,
    }
