"""Idempotent schema migration for the AI Brain tables.

The project has no Alembic setup: ``init_db()`` runs ``create_all`` and
``_migrate_fyers_tokens_table`` patches existing tables.  This module follows
the same convention so a Render deploy needs no extra step.

It is safe to run repeatedly: ``create_all`` only creates missing tables, and
each ALTER is guarded by an information_schema check.
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from app.core.database import Base, engine

logger = logging.getLogger(__name__)

# Tables introduced by the Grok autonomous brain.
BRAIN_TABLES = (
    "brain_state",
    "kill_switches",
    "risk_configs",
    "risk_events",
    "ai_signals",
    "decision_audit",
    "strategy_versions",
    "news_items",
    "memory_entries",
    "learning_reports",
    "order_records",
    "order_fills",
    "reconciliation_runs",
    "broker_credentials",
)

# Optional columns added to pre-existing tables.
ADDED_COLUMNS = {
    "user_indicator_preferences": (),
}


def run_migrations() -> dict:
    """Create the Brain tables and apply guarded column additions."""
    from app.core import brain_models  # noqa: F401 - register models

    result = {"created_tables": [], "added_columns": [], "errors": []}
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    Base.metadata.create_all(bind=engine)
    after = set(inspect(engine).get_table_names())
    result["created_tables"] = sorted(after - existing)

    with engine.begin() as conn:
        for table, columns in ADDED_COLUMNS.items():
            if table not in after:
                continue
            present = {c["name"] for c in inspector.get_columns(table)}
            for column in columns:
                if column in present:
                    continue
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" TEXT'))
                result["added_columns"].append(f"{table}.{column}")

    logger.info(
        "AI Brain migration complete: created=%s columns=%s",
        result["created_tables"] or "none new",
        result["added_columns"] or "none",
    )
    return result


__all__ = ["BRAIN_TABLES", "run_migrations"]
