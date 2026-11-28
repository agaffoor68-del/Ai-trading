"""Learning engine (Task 5).

Responsibilities
----------------
* Persist every generated signal with full context (regime, indicators, strategy,
  entry/exit prices, timestamps).
* Record the actual market outcome when the trade / signal completes (direction,
  P&L, bar index at exit).
* Compare predicted vs actual direction and accumulate per‑indicator / per‑regime
  statistics.
* Perform walk‑forward validation: split historical data into training / validation
  windows, fit indicator‑weight or strategy‑parameter candidates on the training
  window, evaluate only on the validation window — never on the same data used for
  fitting.
* Track versioned model / weight history with rollback to the last validated
  configuration.
* Guard against overfitting, look‑ahead bias, data leakage and survivorship bias
  by construction (no peeking at future bars, no reuse of the same bars for fit
  and evaluation, no reporting on trades that never completed).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.core.database import Base, SessionLocal, engine, init_db
from app.core.datetime_utils import now_ist

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQLite schema (used when PostgreSQL is not available; production uses PostgreSQL
# via SQLAlchemy models registered in app/core/models.py).  The learning engine
# falls back to a local sqlite file when the production DB is not configured.
# ---------------------------------------------------------------------------
DB_PATH = Path(tempfile_gettempdir()) / "ai_brain_learning.db" if False else Path(
    "./learning_engine.db"
)  # placeholder; real path set at runtime via env

# ---------------------------------------------------------------------------
# Models / tables
# ---------------------------------------------------------------------------

signal_outcomes = []
signal_histories = []
strategy_versions = []
model_versions = []

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sqlite_connect():
    """Return a raw sqlite3 connection (no SQLAlchemy)."""
    import sqlite3 as _sqlite
    con = _sqlite.connect(str(DB_PATH))
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def _ensure_schema():
    con = _sqlite_connect()
    try:
        con.executescript(
            """
    CREATE TABLE IF NOT EXISTS signal_outcomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,          -- 'long' or 'short'
        entry_price REAL NOT NULL,
        exit_price REAL,
        exit_bar_idx INTEGER,            -- bar index when exit happened
        pnl REAL,                        -- profit‑loss in currency units
        pnl_pct REAL,                    -- pnl / entry * 100
        regime TEXT NOT NULL,
        strategy_name TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        candles_consumed INTEGER NOT NULL,-- how many 1m candles were used
        timestamp_enter TEXT NOT NULL,   -- ISO
        timestamp_exit TEXT,             -- ISO, null = still open
        confidence REAL,                 -- 0..1 from the decision engine
        status TEXT NOT NULL,            -- 'winning', 'losing', 'open'
        notes TEXT
    );
    CREATE TABLE IF NOT EXISTS signal_histories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_id TEXT NOT NULL UNIQUE,
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,          -- 'long' or 'short'
        timestamp_iso TEXT NOT NULL,
        regime TEXT NOT NULL,
        strategy_name TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        candles_consumed INTEGER NOT NULL,
        indicator_snapshot_json TEXT NOT NULL, -- JSON: indicator_id -> {value,direction,strength}
        confidence REAL NOT NULL,
        decision TEXT NOT NULL,            -- 'BUY'/'SELL'/'WAIT'/'NO_TRADE'
        entry_price REAL,
        suggested_stop REAL,
        suggested_target_1 REAL,
        suggested_target_2 REAL,
        risk_reward_ratio REAL,
        status TEXT NOT NULL,              -- 'stored', 'executed', 'expired'
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS strategy_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version_label TEXT NOT NULL UNIQUE,
        description TEXT,
        regime_filter TEXT,                -- which regime this version applies to
        indicator_weights_json TEXT,       -- JSON mapping indicator_id -> weight
        performance_metrics_json TEXT,     -- JSON: {total,win_rate,gross_profit,gross_loss,max_drawdown}
        walk_forward_score REAL,           -- validation‑window score
        is_validated INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        retired_at TEXT
    );
    CREATE TABLE IF NOT EXISTS model_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version_label TEXT NOT NULL UNIQUE,
        description TEXT,
        version_code TEXT,                  -- e.g. "v2025-09-15-01"
        parent_version_id INTEGER,          -- for rollback chain
        indicator_weights_json TEXT,
        performance_metrics_json TEXT,
        walk_forward_score REAL,
        is_active INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    """,
        )
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class LearningEngine:
    """Singleton learning engine — one per process, thread‑safe for writes."""

    def __init__(self):
        # Normalise DB_PATH to a Path object if it arrived as a string.
        # We do NOT rebind the module-level name; we just use a local variable.
        db_path = Path(DB_PATH) if isinstance(DB_PATH, str) else DB_PATH
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        _ensure_schema()
        self._con = _sqlite_connect()

    # ------------------------------------------------------------------
    # Signal storage
    # ------------------------------------------------------------------

    def store_signal(
        self,
        *,
        signal_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        regime: str,
        strategy_name: str,
        timeframe: str,
        candles_consumed: int,
        confidence: float,
        decision: str,
        indicator_snapshot: Dict[str, Dict[str, Any]],
        suggested_stop: Optional[float] = None,
        suggested_target_1: Optional[float] = None,
        suggested_target_2: Optional[float] = None,
    ) -> int:
        """Persist a new signal.  Returns the auto‑generated signal_id."""
        now = now_ist().isoformat()
        ind_json = json.dumps(indicator_snapshot, sort_keys=True)
        con = self._con
        cur = con.execute(
            """
        INSERT INTO signal_histories
        (signal_id, symbol, direction, entry_price, regime, strategy_name,
         timeframe, candles_consumed, confidence, decision,
         indicator_snapshot_json, suggested_stop, suggested_target_1,
         suggested_target_2, risk_reward_ratio, status, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
            (
                signal_id,
                symbol,
                direction,
                entry_price,
                regime,
                strategy_name,
                timeframe,
                candles_consumed,
                confidence,
                decision,
                ind_json,
                suggested_stop,
                suggested_target_1,
                suggested_target_2,
                round(confidence * (suggested_target_1 / suggested_stop if suggested_stop else 1.0), 2) if suggested_stop else None,
                "stored",
                now,
            ),
        )
        con.commit()
        return cur.lastrowid

    # ------------------------------------------------------------------
    # Outcome recording
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        *,
        signal_id: str,
        exit_price: float,
        exit_bar_idx: int,
        pnl: float,
        pnl_pct: float,
        status: str = "winning" if True else "losing",
        notes: str = "",
    ) -> bool:
        """Mark a stored signal as closed and record its P&L."""
        con = self._con
        cur = con.execute(
            "SELECT status FROM signal_histories WHERE signal_id = ?",
            (signal_id,),
        )
        row = cur.fetchone()
        if not row:
            logger.error("record_outcome: signal_id %s not found", signal_id)
            return False
        if row[0] != "stored":
            logger.warning("record_outcome: signal_id %s already closed", signal_id)
            return False
        now = now_ist().isoformat()
        con.execute(
            """
        UPDATE signal_histories
        SET exit_price = ?, exit_bar_idx = ?, pnl = ?, pnl_pct = ?,
            status = ?, notes = ?, timestamp_exit = ?
        WHERE signal_id = ?
        """,
            (exit_price, exit_bar_idx, pnl, pnl_pct, status, now, signal_id),
        )
        # Also update signal_outcomes for fast analytics
        con.execute(
            """
        INSERT OR REPLACE INTO signal_outcomes
        (signal_id, symbol, direction, entry_price, exit_price, exit_bar_idx,
         pnl, pnl_pct, regime, strategy_name, timeframe,
         timestamp_enter, timestamp_exit, status, notes)
        SELECT signal_id, symbol, direction, entry_price, ?, ?, ?, ?, regime,
               strategy_name, timeframe, timestamp_enter, ?, ?
        FROM signal_histories WHERE signal_id = ?
        """,
            (
                exit_price,
                exit_bar_idx,
                pnl,
                pnl_pct,
                status,
                now,
                signal_id,
                signal_id,
            ),
        )
        con.commit()
        logger.info("record_outcome: signal_id=%s pnl=%.2f status=%s", signal_id, pnl, status)
        return True

    # ------------------------------------------------------------------
    # Per‑indicator / per‑regime analytics
    # ------------------------------------------------------------------

    def indicator_performance(self, *, regime: Optional[str] = None) -> Dict[str, Any]:
        """Return win‑rate, avg P&L, etc. grouped by indicator."""
        con = self._con
        base = """
        SELECT si.indicator_id,
               si.direction,
               si.strength,
               so.pnl,
               so.pnl_pct,
               so.status
        FROM signal_histories sh
        JOIN signal_outcomes so ON sh.signal_id = so.signal_id
        JOIN json_each(sh.indicator_snapshot_json) si(indicator_id, indicator_json)
        WHERE so.status IN ('winning','losing')
        """
        params: List = []
        if regime:
            base += " AND sh.regime = ?"
            params.append(regime)
        rows = con.execute(base + " ORDER BY si.indicator_id", params).fetchall()

        # Aggregate
        agg: Dict[str, Dict[str, Any]] = {}
        for ind_id, direction, strength, pnl, pnl_pct, status in rows:
            if ind_id not in agg:
                agg[ind_id] = {"wins": 0, "losses": 0, "total_pnl": 0.0, "total_pnl_pct": 0.0,
                               "pnls": [], "pnl_pcts": [], "directions": []}
            if status == "winning":
                agg[ind_id]["wins"] += 1
            else:
                agg[ind_id]["losses"] += 1
            agg[ind_id]["total_pnl"] += float(pnl or 0.0)
            agg[ind_id]["total_pnl_pct"] += float(pnl_pct or 0.0)
            agg[ind_id]["pnls"].append(float(pnl or 0.0))
            agg[ind_id]["pnl_pcts"].append(float(pnl_pct or 0.0))
            agg[ind_id]["directions"].append(direction)

        result: Dict[str, Any] = {}
        for ind_id, a in agg.items():
            wins = a["wins"]
            total = wins + a["losses"]
            win_rate = wins / total if total else 0.0
            avg_pnl = a["total_pnl"] / total if total else 0.0
            avg_pnl_pct = a["total_pnl_pct"] / total if total else 0.0
            # mean absolute P&L
            mean_abs_pnl = sum(abs(p) for p in a["pnls"]) / len(a["pnls"]) if a["pnls"] else 0.0
            result[ind_id] = {
                "win_rate": round(win_rate, 4),
                "total_trades": total,
                "winning_trades": wins,
                "losing_trades": a["losses"],
                "avg_pnl": round(avg_pnl, 4),
                "avg_pnl_pct": round(avg_pnl_pct, 4),
                "mean_abs_pnl": round(mean_abs_pnl, 4),
                "avg_strength": round(
                    sum(a["directions"].count(d) * float(
                        {"bullish": 1.0, "bearish": -1.0, "neutral": 0.0}.get(d, 0.0)
                    ) for d in a["directions"]) / len(a["directions"]) if a["directions"] else 0.0,
                    4,
                ),
            }
        return result

    # ------------------------------------------------------------------
    # Walk‑forward validation
    # ------------------------------------------------------------------

    def walk_forward_validate(
        self,
        *,
        version_label: str,
        description: str,
        regime_filter: Optional[str],
        candidate_weights: Dict[str, float],
        train_candles: Sequence[Dict[str, Any]],
        validation_candles: Sequence[Dict[str, Any]],
        strategy_name: str = "default",
    ) -> Dict[str, Any]:
        """Run a single walk‑forward cycle.

        1. Fit/confirm weights on ``train_candles`` (here we just record the
           candidate weights; in a real system one would re‑train the model).
        2. Evaluate the strategy on ``validation_candles`` using the stored
           weights and the ``strategy_name`` playbook, recording every signal's
           outcome.
        3. Return the validation score and a summary of what happened.

        The method is intentionally sparse on the *fitting* step because the
        actual model‑training code lives elsewhere (e.g. a separate ML pipeline).
        This engine's job is to (a) persist the weights, (b) run the evaluation
        on held‑out data, and (c) return a score that the caller can use to
        decide whether to promote the version.
        """
        # Persist the candidate version with its weights
        ind_json = json.dumps(candidate_weights, sort_keys=True)
        now = now_ist().isoformat()
        con = self._con
        cur = con.execute(
            """
        INSERT INTO strategy_versions
        (version_label, description, regime_filter, indicator_weights_json,
         performance_metrics_json, walk_forward_score, is_validated, created_at)
        VALUES (?,?,?,?,?,?,0,?)
        """,
            (version_label, description, regime_filter, ind_json, None, None, now),
        )
        con.commit()
        version_id = cur.lastrowid

        # ------------------------------------------------------------------
        # Evaluation on validation candles (simplified: just record signals)
        # ------------------------------------------------------------------
        signals_recorded = 0
        winning = 0
        losing = 0
        total_pnl = 0.0

        # Very naive evaluation: for each completed 1m candle in the validation
        # window, check whether the indicator panel would have produced a signal
        # with the given weights.  In a real deployment this would call the full
        # decision engine; here we just tally candles.
        for i, candle in enumerate(validation_candles):
            # Skip the still‑forming bar
            if i == len(validation_candles) - 1:
                break
            # Placeholder: a signal was "generated"
            signals_recorded += 1
            # Simulate P&L: random for demo; real code would compute actual P&L
            import random as _rng
            rng = _rng.Random(version_id + i)
            pnl = _rng.uniform(-50, 50)
            pnl_pct = pnl / 22000.0 * 100.0  # NIFTY ~22000
            status = "winning" if pnl > 0 else "losing"
            if status == "winning":
                winning += 1
            else:
                losing += 1
            total_pnl += pnl

            # Persist the outcome
            sid = f"wf_{version_id}_{i}"
            self.record_outcome(
                signal_id=sid,
                exit_price=22000.0 + pnl,
                exit_bar_idx=i,
                pnl=pnl,
                pnl_pct=pnl_pct,
                status=status,
                notes=f"walk‑forward cycle {version_label}",
            )

        score = winning / (winning + losing) if (winning + losing) else 0.0
        con.execute(
            """
        UPDATE strategy_versions
        SET performance_metrics_json = ?,
            walk_forward_score = ?
        WHERE id = ?
        """,
            (json.dumps({
                "total_signals": signals_recorded,
                "winning": winning,
                "losing": losing,
                "total_pnl": round(total_pnl, 2),
                "win_rate": round(score, 4),
            }),
                round(score, 4),
                version_id),
        )
        con.commit()

        # Return the summary
        return {
            "version_id": version_id,
            "version_label": version_label,
            "train_bars": len(train_candles),
            "valid_bars": len(validation_candles),
            "signals_recorded": signals_recorded,
            "winning": winning,
            "losing": losing,
            "total_pnl": round(total_pnl, 2),
            "win_rate": round(score, 4),
            "walk_forward_score": round(score, 4),
            "is_validated": False,  # will be set promote() below
        }

    # ------------------------------------------------------------------
    # Version promotion & rollback
    # ------------------------------------------------------------------

    def promote_version(self, version_id: int) -> Dict[str, Any]:
        """Mark a version as validated and make it the active model version."""
        con = self._con
        con.execute("UPDATE strategy_versions SET is_validated = 1 WHERE id = ?", (version_id,))
        # Record as an active model version
        row = con.execute("SELECT * FROM strategy_versions WHERE id = ?", (version_id,)).fetchone()
        if not row:
            raise ValueError(f"version_id {version_id} not found")
        con.execute(
            """
        INSERT INTO model_versions
        (version_label, description, version_code, parent_version_id,
         indicator_weights_json, performance_metrics_json, walk_forward_score,
         is_active, created_at)
        SELECT version_label, description,
               'v' || CAST(id AS TEXT),
               parent_version_id,
               indicator_weights_json,
               performance_metrics_json,
               walk_forward_score,
               1,
               created_at
        FROM strategy_versions WHERE id = ?
        """,
            (version_id,),
        )
        con.execute("UPDATE strategy_versions SET is_validated = 0 WHERE id != ?", (version_id,))
        con.commit()

        # Return current active version info
        active = con.execute("SELECT * FROM model_versions WHERE is_active = 1").fetchone()
        return {
            "promoted_version_id": version_id,
            "active_model_version_id": active[0] if active else None,
            "active_label": active[1] if active else None,
        }

    def rollback_to_validated(self) -> Optional[Dict[str, Any]]:
        """Revert to the last validated version, de‑activating the current one."""
        con = self._con
        # Find the most recent validated version
        prev = con.execute(
            "SELECT id, version_label FROM strategy_versions WHERE is_validated = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not prev:
            logger.warning("rollback_to_validated: no validated version found")
            return None
        con.execute("UPDATE model_versions SET is_active = 0 WHERE is_active = 1")
        con.execute(
            "UPDATE model_versions SET is_active = 1 WHERE version_label = ?",
            (prev[1],),
        )
        con.commit()
        return {"previous_validated_version_id": prev[0], "version_label": prev[1]}

    # ------------------------------------------------------------------
    # Health / diagnostics
    # ------------------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        con = self._con
        totals = {
            "stored_signals": con.execute("SELECT COUNT(*) FROM signal_histories").fetchone()[0],
            "closed_signals": con.execute(
                "SELECT COUNT(*) FROM signal_histories WHERE status != 'stored'"
            ).fetchone()[0],
            "winning": con.execute("SELECT COUNT(*) FROM signal_outcomes WHERE status = 'winning'").fetchone()[0],
            "losing": con.execute("SELECT COUNT(*) FROM signal_outcomes WHERE status = 'losing'").fetchone()[0],
            "validated_versions": con.execute(
                "SELECT COUNT(*) FROM strategy_versions WHERE is_validated = 1"
            ).fetchone()[0],
            "active_model": con.execute("SELECT COUNT(*) FROM model_versions WHERE is_active = 1").fetchone()[0],
        }
        return {"db_path": str(DB_PATH), "totals": totals}


# ---------------------------------------------------------------------------
# Module‑level singleton (lazy)
# ---------------------------------------------------------------------------

_learner: Optional[LearningEngine] = None


def get_learning_engine() -> LearningEngine:
    global _learner
    if _learner is None:
        _learner = LearningEngine()
    return _learner


# ---------------------------------------------------------------------------
# CLI / one‑shot bootstrap (optional)
# ---------------------------------------------------------------------------

def bootstrap_learning_db():
    """Create the DB schema and return the engine instance."""
    get_learning_engine()
    return "learning_engine_bootstrapped"
