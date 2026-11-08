"""
Phase 2: Database Models - Authentication & Subscription

SQLAlchemy models for User and Subscription.
PostgreSQL only - no SQLite.
"""

from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Boolean, Enum
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
