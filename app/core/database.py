"""
Phase 1 Database Configuration
PostgreSQL ONLY - SQLAlchemy 2.0 with psycopg2 driver.
No SQLite allowed per non-negotiable rules.
"""

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Force psycopg v3 driver (psycopg2 is incompatible with Python 3.14)
# Render injects DATABASE_URL as postgresql:// — normalize to +psycopg dialect
_DATABASE_URL = settings.DATABASE_URL
_DATABASE_URL = _DATABASE_URL.replace("postgresql://", "postgresql+psycopg://")
_DATABASE_URL = _DATABASE_URL.replace("postgres://", "postgresql+psycopg://")
DATABASE_URL = _DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Instrument(Base):
    """
    Symbol Master table - parsed from Fyers Symbol Master CSVs.
    Only Fyers symbols are stored (Rule: Fyers ONLY for data).
    """
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)  # e.g., NSE:NIFTY50-INDEX
    name = Column(String, nullable=True)
    exchange = Column(String, nullable=True)  # NSE_CM, NSE_FO, etc.
    segment = Column(String, nullable=True)
    lot_size = Column(Integer, nullable=True)
    tick_size = Column(String, nullable=True)
    instrument_type = Column(String, nullable=True)  # EQ, FUT, OPT
    expiry = Column(DateTime, nullable=True)
    strike = Column(Text, nullable=True)
    option_type = Column(String, nullable=True)  # CE, PE
    fyers_token = Column(String, nullable=True, index=True)  # Fyers instrument token
    is_active = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
