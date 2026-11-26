"""AI Brain database models (decision audit, learning, news, risk, memory).

Design rules enforced here:

* The risk configuration and the kill switch live in the database and are the
  only source of truth for the independent Risk Management Engine.  No AI code
  path is allowed to write ``RiskConfig`` limits or clear ``KillSwitch``.
* Every AI decision gets a unique ``decision_id`` (UUID) that is referenced by
  the audit row, the order request, the broker response and the learning row,
  so a trade can be reconstructed end to end.
* Nothing in this module invents market data: rows only ever store snapshots
  that were produced by the Trading Data Intelligence Layer, together with the
  source and the timestamp of that snapshot.
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
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.datetime_utils import now_ist


class DecisionAction(PyEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    NO_TRADE = "NO_TRADE"


class NewsUrgency(PyEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StrategyStatus(PyEnum):
    DRAFT = "draft"
    BACKTESTING = "backtesting"
    OUT_OF_SAMPLE = "out_of_sample"
    WALK_FORWARD = "walk_forward"
    SHADOW = "shadow"
    VALIDATED = "validated"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    DISABLED = "disabled"


class BrainModel(Base):
    """Persisted AI Brain state that is not tied to a single decision."""

    __tablename__ = "brain_state"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    scope = Column(String(64), nullable=False, default="global", index=True)
    state = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "scope", name="uq_brain_state_scope"),)


class KillSwitch(Base):
    """Global emergency stop.  One row per user (NULL user_id = global)."""

    __tablename__ = "kill_switches"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    active = Column(Boolean, nullable=False, default=False, index=True)
    reason = Column(Text, nullable=True)
    activated_by = Column(String(64), nullable=False, default="system")
    activated_at = Column(DateTime, default=now_ist, nullable=False)
    auto_reset_at = Column(DateTime, nullable=True)
    cancelled_pending_orders = Column(Integer, nullable=False, default=0)
    exit_policy = Column(String(32), nullable=False, default="hold")

    __table_args__ = (UniqueConstraint("user_id", name="uq_kill_switch_user"),)


class RiskConfig(Base):
    """User risk limits.  Written only by the settings API, never by the AI."""

    __tablename__ = "risk_configs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    master_autonomous_enabled = Column(Boolean, nullable=False, default=False)
    trading_mode = Column(String(32), nullable=False, default="paper")
    allowed_instruments = Column(JSON, nullable=False, default=list)
    allowed_segments = Column(JSON, nullable=False, default=list)
    max_risk_per_trade_pct = Column(Float, nullable=False, default=0.5)
    max_daily_loss = Column(Float, nullable=False, default=2000.0)
    max_total_open_positions = Column(Integer, nullable=False, default=3)
    max_position_size = Column(Integer, nullable=False, default=50)
    max_daily_trades = Column(Integer, nullable=False, default=10)
    max_portfolio_exposure = Column(Float, nullable=False, default=100000.0)
    max_consecutive_losses = Column(Integer, nullable=False, default=3)
    session_start = Column(String(5), nullable=False, default="09:20")
    session_end = Column(String(5), nullable=False, default="15:10")
    square_off_time = Column(String(5), nullable=False, default="15:15")
    emergency_exit_policy = Column(String(32), nullable=False, default="hold")
    require_stop_loss = Column(Boolean, nullable=False, default=True)
    min_risk_reward = Column(Float, nullable=False, default=1.5)
    max_spread_pct = Column(Float, nullable=False, default=0.25)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist, nullable=False)


class RiskEvent(Base):
    """Every risk decision (allow/deny) plus kill-switch and limit breaches."""

    __tablename__ = "risk_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    decision_id = Column(String(64), index=True, nullable=True)
    event_type = Column(String(48), nullable=False, index=True)
    allowed = Column(Boolean, nullable=False, default=True)
    reason = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=now_ist, index=True, nullable=False)


class AISignal(Base):
    """Latest AI decision per instrument, used by the dashboard."""

    __tablename__ = "ai_signals"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    decision_id = Column(String(64), index=True, nullable=False)
    symbol = Column(String(64), index=True, nullable=False)
    action = Column(String(16), nullable=False, index=True)
    confidence = Column(Float, nullable=False, default=0.0)
    horizon = Column(String(32), nullable=True)
    entry_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    targets = Column(JSON, nullable=False, default=list)
    strategy_version = Column(String(64), nullable=True)
    risk_status = Column(String(32), nullable=True)
    status = Column(String(24), nullable=False, default="proposed", index=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now_ist, index=True, nullable=False)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist, nullable=False)

    __table_args__ = (Index("ix_ai_signals_user_symbol", "user_id", "symbol"),)


class DecisionAudit(Base):
    """Full audit trail for one AI decision (Part 12)."""

    __tablename__ = "decision_audit"

    id = Column(Integer, primary_key=True)
    decision_id = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    symbol = Column(String(64), index=True, nullable=False)
    timeframe = Column(String(16), nullable=True)
    action = Column(String(16), nullable=False)
    confidence = Column(Float, nullable=True)
    model_id = Column(String(64), nullable=True)
    strategy_version = Column(String(64), nullable=True)
    market_snapshot = Column(JSON, nullable=True)
    indicator_snapshot = Column(JSON, nullable=True)
    news_refs = Column(JSON, nullable=True)
    reasoning = Column(Text, nullable=True)
    risk_result = Column(JSON, nullable=True)
    order_request = Column(JSON, nullable=True)
    broker_response = Column(JSON, nullable=True)
    execution_result = Column(JSON, nullable=True)
    data_quality = Column(JSON, nullable=True)
    no_trade_reason = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=now_ist, index=True, nullable=False)


class StrategyVersion(Base):
    """Versioned strategy with its validation evidence and promotion state."""

    __tablename__ = "strategy_versions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    version = Column(String(64), nullable=False, index=True)
    parent_version = Column(String(64), nullable=True)
    name = Column(String(120), nullable=False)
    status = Column(String(24), nullable=False, default=StrategyStatus.DRAFT.value, index=True)
    params = Column(JSON, nullable=False, default=dict)
    changelog = Column(Text, nullable=True)
    backtest_metrics = Column(JSON, nullable=True)
    out_of_sample_metrics = Column(JSON, nullable=True)
    walk_forward_metrics = Column(JSON, nullable=True)
    shadow_metrics = Column(JSON, nullable=True)
    validation_report = Column(JSON, nullable=True)
    promoted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now_ist, nullable=False)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "version", name="uq_strategy_version"),)


class NewsItem(Base):
    """Financial news with provenance.  Content is untrusted data."""

    __tablename__ = "news_items"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    headline = Column(Text, nullable=False)
    source = Column(String(120), nullable=False, index=True)
    url = Column(Text, nullable=True)
    region = Column(String(16), nullable=False, default="india", index=True)
    published_at = Column(DateTime, nullable=True, index=True)
    event_at = Column(DateTime, nullable=True)
    instruments = Column(JSON, nullable=False, default=list)
    sectors = Column(JSON, nullable=False, default=list)
    sentiment = Column(String(16), nullable=True)
    sentiment_score = Column(Float, nullable=True)
    impact = Column(String(16), nullable=True)
    reliability = Column(String(24), nullable=False, default="unverified")
    confirmation = Column(String(24), nullable=False, default="single_source")
    impact_duration = Column(String(24), nullable=True)
    summary = Column(Text, nullable=True)
    raw_excerpt = Column(Text, nullable=True)
    ingested_at = Column(DateTime, default=now_ist, nullable=False)
    content_hash = Column(String(64), index=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_news_content_hash"),
        Index("ix_news_region_published", "region", "published_at"),
    )


class MemoryEntry(Base):
    """Long-term AI memory (Part 9).  One row per typed memory."""

    __tablename__ = "memory_entries"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    memory_type = Column(String(32), nullable=False, index=True)
    symbol = Column(String(64), nullable=True, index=True)
    regime = Column(String(64), nullable=True, index=True)
    decision_id = Column(String(64), nullable=True, index=True)
    strategy_version = Column(String(64), nullable=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(JSON, nullable=False, default=list)
    embedding = Column(JSON, nullable=True)
    outcome = Column(String(16), nullable=True)
    pnl = Column(Float, nullable=True)
    importance = Column(Float, nullable=False, default=0.5)
    created_at = Column(DateTime, default=now_ist, index=True, nullable=False)


class LearningReport(Base):
    """Post-trade learning report, one per closed trade / decision."""

    __tablename__ = "learning_reports"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    decision_id = Column(String(64), index=True, nullable=False)
    symbol = Column(String(64), index=True, nullable=True)
    outcome = Column(String(16), nullable=False, index=True)
    pnl = Column(Float, nullable=True)
    r_multiple = Column(Float, nullable=True)
    plan_followed = Column(Boolean, nullable=True)
    win_conditions = Column(JSON, nullable=False, default=list)
    loss_reasons = Column(JSON, nullable=False, default=list)
    indicator_performance = Column(JSON, nullable=True)
    news_impact = Column(JSON, nullable=True)
    lessons = Column(Text, nullable=True)
    suggestions = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=now_ist, index=True, nullable=False)


class OrderRecord(Base):
    """Order lifecycle with idempotency key (duplicate-submit protection)."""

    __tablename__ = "order_records"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    decision_id = Column(String(64), index=True, nullable=False)
    client_order_id = Column(String(64), unique=True, index=True, nullable=False)
    symbol = Column(String(64), nullable=False, index=True)
    side = Column(String(8), nullable=False)
    quantity = Column(Integer, nullable=False)
    order_type = Column(String(16), nullable=False, default="MARKET")
    product_type = Column(String(16), nullable=False, default="INTRADAY")
    status = Column(String(24), nullable=False, default="PENDING", index=True)
    requested_price = Column(Float, nullable=True)
    filled_price = Column(Float, nullable=True)
    filled_quantity = Column(Integer, nullable=False, default=0)
    pending_quantity = Column(Integer, nullable=False, default=0)
    broker_order_id = Column(String(64), nullable=True, index=True)
    broker = Column(String(32), nullable=False, default="paper")
    stop_loss = Column(Float, nullable=True)
    target = Column(Float, nullable=True)
    charges = Column(Float, nullable=False, default=0.0)
    slippage = Column(Float, nullable=False, default=0.0)
    rejection_reason = Column(Text, nullable=True)
    is_paper = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=now_ist, index=True, nullable=False)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist, nullable=False)

    fills = relationship("OrderFill", back_populates="order", cascade="all, delete-orphan")


class OrderFill(Base):
    """Individual fill events (partial fills are normal)."""

    __tablename__ = "order_fills"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("order_records.id"), index=True, nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    charges = Column(Float, nullable=False, default=0.0)
    filled_at = Column(DateTime, default=now_ist, nullable=False)
    source = Column(String(32), nullable=False, default="broker")

    order = relationship("OrderRecord", back_populates="fills")


class ReconciliationRun(Base):
    """Local-vs-broker position reconciliation results."""

    __tablename__ = "reconciliation_runs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    broker = Column(String(32), nullable=False, default="paper")
    matched = Column(Boolean, nullable=False, default=True)
    discrepancies = Column(JSON, nullable=False, default=list)
    local_positions = Column(JSON, nullable=False, default=list)
    broker_positions = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=now_ist, index=True, nullable=False)


class BrokerCredentials(Base):
    """Encrypted broker credential envelope (never handed to the AI)."""

    __tablename__ = "broker_credentials"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    broker = Column(String(32), nullable=False, index=True)
    encrypted_blob = Column(Text, nullable=False)
    permissions = Column(JSON, nullable=False, default=list)
    verified = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "broker", name="uq_broker_credentials"),)


__all__ = [
    "AISignal",
    "BrainModel",
    "BrokerCredentials",
    "DecisionAction",
    "DecisionAudit",
    "KillSwitch",
    "LearningReport",
    "MemoryEntry",
    "NewsItem",
    "NewsUrgency",
    "OrderFill",
    "OrderRecord",
    "ReconciliationRun",
    "RiskConfig",
    "RiskEvent",
    "StrategyStatus",
    "StrategyVersion",
]
