"""Strategy Builder persistence model.

The Strategy Builder (``/api/v1/strategies``) stores user-authored rule sets:
a name, entry conditions, timeframe and risk settings.  It is deliberately
separate from :class:`app.core.brain_models.StrategyVersion`, which holds the
AI Brain's validated/promoted versions and their backtest evidence.  Mixing the
two would either lose the builder's rule text or corrupt the validation
history, so the builder gets its own table.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)

from app.core.database import Base
from app.core.datetime_utils import now_ist


class UserStrategy(Base):
    """A user's rule-based strategy definition."""

    __tablename__ = "user_strategies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id"), index=True, nullable=False
    )
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    conditions = Column(JSON, nullable=False, default=list)
    timeframe = Column(String(16), nullable=False, default="15m")
    stop_loss_pct = Column(Float, nullable=True)
    target_pct = Column(Float, nullable=True)
    indicators = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=now_ist, nullable=False)
    updated_at = Column(
        DateTime, default=now_ist, onupdate=now_ist, nullable=False
    )

    def to_dict(self) -> dict:
        """JSON shape consumed by the Strategy Builder page."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description or "",
            "conditions": self.conditions or [],
            "timeframe": self.timeframe,
            "stopLoss": self.stop_loss_pct,
            "target": self.target_pct,
            "indicators": self.indicators or [],
            "isActive": bool(self.is_active),
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


__all__ = ["UserStrategy"]
