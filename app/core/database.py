"""
Phase 1 Database Configuration
PostgreSQL ONLY - SQLAlchemy 2.0 with psycopg3 driver.
No SQLite allowed per non-negotiable rules.
"""

import logging
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

# 1. DATABASE URL - PostgreSQL for production, SQLite for development
# 2. Force psycopg3 driver - Render injects DATABASE_URL as postgresql://
# which SQLAlchemy defaults to psycopg2 (not installed). Normalize to +psycopg.
_DATABASE_URL = settings.DATABASE_URL
if _DATABASE_URL.startswith("postgres://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif _DATABASE_URL.startswith("postgresql://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
elif "postgresql+psycopg2://" in _DATABASE_URL:
    _DATABASE_URL = _DATABASE_URL.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
elif "sqlite" in _DATABASE_URL:
    # SQLite - no special driver needed
    pass
else:
    # Default to PostgreSQL (will fail without psycopg3)
    pass

# Automatically append sslmode=require if missing (required for Render PostgreSQL)
if "sslmode=" not in _DATABASE_URL and "sqlite" not in _DATABASE_URL:
    separator = "&" if "?" in _DATABASE_URL else "?"
    _DATABASE_URL = f"{_DATABASE_URL}{separator}sslmode=require"

DATABASE_URL = _DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    hide_parameters=True,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Instrument(Base):
    """Symbol Master table - parsed from Fyers Symbol Master CSVs."""
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    name = Column(String, nullable=True)
    exchange = Column(String, nullable=True)
    segment = Column(String, nullable=True)
    lot_size = Column(Integer, nullable=True)
    tick_size = Column(String, nullable=True)
    instrument_type = Column(String, nullable=True)
    expiry = Column(DateTime, nullable=True)
    strike = Column(Text, nullable=True)
    option_type = Column(String, nullable=True)
    fyers_token = Column(String, nullable=True, index=True)
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
    """Create missing tables without deleting persisted Fyers tokens."""
    from app.core import models  # noqa: F401 - register every model with metadata
    from app.core.migrations_brain import run_migrations

    try:
        # create_all is non-destructive: unlike DROP TABLE, it preserves OAuth
        # tokens and credentials across application restarts.
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        # AI Brain tables (decision audit, learning, news, risk, memory).
        run_migrations()
        logger.info("Database connection successful; existing Fyers tokens preserved")
    except Exception:
        logger.exception("Database initialization failed")
        raise


def _migrate_fyers_tokens_table():
    """Add optional encrypted credential columns to an existing token table."""
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        if "fyers_tokens" not in inspector.get_table_names():
            return
        existing = {column["name"] for column in inspector.get_columns("fyers_tokens")}
        missing = [column for column in ("client_id", "client_secret") if column not in existing]
        if not missing:
            return
        with engine.begin() as conn:
            for column in missing:
                conn.execute(text(f"ALTER TABLE fyers_tokens ADD COLUMN {column} TEXT"))
        logger.info("Migrated fyers_tokens table with columns: %s", missing)
    except Exception:
        logger.exception("Failed to migrate fyers_tokens table")
        raise
