"""
Phase 2: Database Models - Authentication & Subscription

SQLAlchemy models for User and Subscription.
PostgreSQL only - no SQLite.
"""

from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Boolean, Enum, Text, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


class UserRole(PyEnum):
    ADMIN = "ADMIN"
    USER = "USER"


class SubscriptionPlan(PyEnum):
    BASIC = "Basic"
    PRO = "Pro"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole, values_callable=lambda obj: [e.value for e in obj]), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(IST), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(IST), onupdate=lambda: datetime.now(IST), nullable=False)

    # Relationships
    subscription = relationship("Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    plan_type = Column(Enum(SubscriptionPlan, values_callable=lambda obj: [e.value for e in obj]), default=SubscriptionPlan.BASIC, nullable=False)
    start_date = Column(DateTime, default=lambda: datetime.now(IST), nullable=False)
    end_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(IST), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(IST), onupdate=lambda: datetime.now(IST), nullable=False)

    # Relationships
    user = relationship("User", back_populates="subscription")

    def __repr__(self):
        return f"<Subscription(id={self.id}, user_id={self.user_id}, plan={self.plan_type})>"


class FyersToken(Base):
    __tablename__ = "fyers_tokens"

    id = Column(Integer, primary_key=True, index=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    client_id = Column(Text, nullable=True)
    client_secret = Column(Text, nullable=True)
    expires_in = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(IST), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(IST), onupdate=lambda: datetime.now(IST), nullable=False)

    def __repr__(self):
        return f"<FyersToken(id={self.id}, expires_in={self.expires_in})>"


class UserIndicatorPreference(Base):
    """Per-user Indicator Library state: enabled, favourite and parameters.

    One row per (user, indicator).  ``params`` is a JSON object so new indicator
    parameters do not need a migration.
    """

    __tablename__ = "user_indicator_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    indicator_id = Column(String(64), nullable=False, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    favorite = Column(Boolean, default=False, nullable=False)
    params = Column(JSON, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(IST), nullable=False)

    def __repr__(self):
        return (
            f"<UserIndicatorPreference(user_id={self.user_id}, "
            f"indicator_id={self.indicator_id}, enabled={self.enabled})>"
        )
