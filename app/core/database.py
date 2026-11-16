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

# Force psycopg3 driver - Render injects DATABASE_URL as postgresql://
# which SQLAlchemy defaults to psycopg2 (not installed). Normalize to +psycopg.
_DATABASE_URL = settings.DATABASE_URL
if _DATABASE_URL.startswith("postgres://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif _DATABASE_URL.startswith("postgresql://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
elif "postgresql+psycopg2://" in _DATABASE_URL:
    _DATABASE_URL = _DATABASE_URL.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
# If it already has +psycopg, leave it as is.

# Automatically append sslmode=require if missing (required for Render PostgreSQL)
if "sslmode=" not in _DATABASE_URL:
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
    """Create all tables from current models.

    fyers_tokens is only a token cache, so we drop and recreate it to pick up
    schema changes (client_id / client_secret columns). create_all() never
    alters existing tables, and cached tokens are safe to lose (re-login).
    """
    # Register every model even when init_db is called outside app.main.
    from app.core import models  # noqa: F401

    try:
        # Drop the token cache first so the new model schema is applied cleanly
        # even when the live table was created by an older version.
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS fyers_tokens"))
        logger.info("Dropped fyers_tokens table (token cache; will be recreated)")

        Base.metadata.create_all(bind=engine)
        # Test the connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection successful")
    except Exception:
        logger.exception("Database initialization failed")
        raise


def _migrate_fyers_tokens_table():
    """Kept for reference: add client_id/client_secret without dropping.

    init_db() now drops/recreates the cache table directly, so this runs only
    if called explicitly. Deleting cached tokens is safe - the user simply
    logs in to Fyers again.
    """
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        if "fyers_tokens" not in inspector.get_table_names():
            return  # Table will be created by create_all on next start

        existing = {col["name"] for col in inspector.get_columns("fyers_tokens")}
        missing = [c for c in ("client_id", "client_secret") if c not in existing]
        if not missing:
            return

        with engine.begin() as conn:
            for col in missing:
                logger.info(
                    "Migrating fyers_tokens: adding missing column %s", col
                )
                conn.execute(
                    text(f"ALTER TABLE fyers_tokens ADD COLUMN {col} TEXT")
                )
        logger.info("fyers_tokens migration complete (columns: %s)", sorted(existing | set(missing)))
    except Exception as e:
        logger.warning(
            "Could ALTER TABLE fyers_tokens (%s); dropping token cache and "
            "recreating from model. Users will need to log in to Fyers again.",
            e,
        )
        try:
            with engine.begin() as conn:
                conn.execute(text("DROP TABLE IF EXISTS fyers_tokens"))
            Base.metadata.create_all(bind=engine, tables=[models.FyersToken.__table__])
            logger.info("fyers_tokens table recreated with current schema")
        except Exception:
            logger.exception("Failed to recreate fyers_tokens table")
            raise
