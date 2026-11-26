"""Persistent AI memory and knowledge retrieval (Part 9).

Memory is stored in ``memory_entries`` (PostgreSQL) so it survives restarts and
model swaps.  Retrieval is deterministic and dependency-free: a weighted lexical
score over title/content/tags plus filters for memory type, symbol, regime and
recency.  ``embedding`` is reserved for a future vector index; nothing pretends
a semantic search happened when it did not.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import select

from app.core.brain_models import MemoryEntry
from app.core.database import SessionLocal
from app.core.datetime_utils import now_ist

logger = logging.getLogger(__name__)

MEMORY_TYPES = (
    "trade_decision",
    "winning_trade",
    "losing_trade",
    "strategy",
    "indicator_performance",
    "news_impact",
    "market_condition",
    "strategy_version",
    "risk_event",
    "lesson",
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "the a an and or of to in on for with is are was were be been this that it its as at by from".split()
)


@dataclass
class MemoryHit:
    memory_type: str
    title: str
    content: str
    score: float
    created_at: Optional[str]
    symbol: Optional[str]
    outcome: Optional[str]
    decision_id: Optional[str]
    tags: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_type": self.memory_type,
            "title": self.title,
            "content": self.content,
            "score": round(self.score, 4),
            "created_at": self.created_at,
            "symbol": self.symbol,
            "outcome": self.outcome,
            "decision_id": self.decision_id,
            "tags": self.tags,
        }


def tokenize(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOPWORDS and len(t) > 1]


def score_entry(query_tokens: Sequence[str], entry: MemoryEntry, tag_tokens: Sequence[str]) -> float:
    """Weighted lexical overlap in [0, 1].  Deterministic and explainable."""
    if not query_tokens:
        return 0.0
    title_tokens = set(tokenize(entry.title))
    body_tokens = set(tokenize(entry.content))
    haystack = title_tokens | body_tokens | set(tag_tokens)
    overlap = sum(1 for token in set(query_tokens) if token in haystack)
    if overlap == 0:
        return 0.0
    coverage = overlap / len(set(query_tokens))
    title_bonus = sum(0.15 for token in set(query_tokens) if token in title_tokens) / len(set(query_tokens))
    importance = float(entry.importance or 0.5)
    return min(1.0, coverage * 0.7 + title_bonus + importance * 0.15)


def _recency_boost(entry: MemoryEntry, reference: datetime, half_life_days: float = 120.0) -> float:
    if not entry.created_at:
        return 0.0
    created = entry.created_at
    if created.tzinfo is None:
        from app.core.datetime_utils import IST

        created = created.replace(tzinfo=IST)
    age_days = max(0.0, (reference - created).total_seconds() / 86400.0)
    return math.exp(-age_days / half_life_days) * 0.1


async def search_memory(
    query: str,
    user_id: Optional[int] = None,
    memory_types: Optional[Sequence[str]] = None,
    symbol: Optional[str] = None,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """Return the most relevant stored memories for ``query``."""
    tokens = tokenize(query)
    if not tokens:
        return []
    reference = now_ist()
    rows: List[MemoryEntry] = []
    with SessionLocal() as db:
        stmt = select(MemoryEntry).order_by(MemoryEntry.created_at.desc()).limit(500)
        if user_id is not None:
            stmt = stmt.where((MemoryEntry.user_id == user_id) | (MemoryEntry.user_id.is_(None)))
        if memory_types:
            stmt = stmt.where(MemoryEntry.memory_type.in_(list(memory_types)))
        if symbol:
            stmt = stmt.where(MemoryEntry.symbol == symbol)
        rows = list(db.execute(stmt).scalars())

    hits: List[MemoryHit] = []
    for entry in rows:
        tag_tokens = tokenize(" ".join(str(t) for t in (entry.tags or [])))
        score = score_entry(tokens, entry, tag_tokens) + _recency_boost(entry, reference)
        if score <= 0:
            continue
        hits.append(
            MemoryHit(
                memory_type=entry.memory_type,
                title=entry.title,
                content=entry.content,
                score=score,
                created_at=entry.created_at.isoformat() if entry.created_at else None,
                symbol=entry.symbol,
                outcome=entry.outcome,
                decision_id=entry.decision_id,
                tags=list(entry.tags or []),
            )
        )
    hits.sort(key=lambda h: h.score, reverse=True)
    return [hit.to_dict() for hit in hits[: max(1, min(limit, 25))]]


def write_memory(
    memory_type: str,
    title: str,
    content: str,
    user_id: Optional[int] = None,
    symbol: Optional[str] = None,
    regime: Optional[str] = None,
    decision_id: Optional[str] = None,
    strategy_version: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
    outcome: Optional[str] = None,
    pnl: Optional[float] = None,
    importance: float = 0.5,
) -> Optional[str]:
    """Persist one memory row.  Returns the row id, or ``None`` on failure."""
    if memory_type not in MEMORY_TYPES:
        logger.warning("Refusing unknown memory type %s", memory_type)
        return None
    try:
        with SessionLocal() as db:
            entry = MemoryEntry(
                user_id=user_id,
                memory_type=memory_type,
                symbol=symbol,
                regime=regime,
                decision_id=decision_id,
                strategy_version=strategy_version,
                title=title[:500],
                content=content,
                tags=list(tags or []),
                outcome=outcome,
                pnl=pnl,
                importance=max(0.0, min(1.0, importance)),
            )
            db.add(entry)
            db.commit()
            return str(entry.id)
    except Exception:
        logger.exception("Failed to write memory row")
        return None


async def similar_situations(
    symbol: str,
    regime: Optional[str],
    user_id: Optional[int] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """Answer: "have I traded this condition before, and what happened?"."""
    query = f"{symbol} {regime or ''} market condition outcome".strip()
    memories = await search_memory(
        query=query,
        user_id=user_id,
        memory_types=["trade_decision", "winning_trade", "losing_trade", "market_condition", "lesson"],
        symbol=symbol,
        limit=limit,
    )
    wins = [m for m in memories if (m.get("outcome") or "").upper() == "WIN"]
    losses = [m for m in memories if (m.get("outcome") or "").upper() == "LOSS"]
    return {
        "symbol": symbol,
        "regime": regime,
        "matches": memories,
        "summary": {
            "matches": len(memories),
            "wins": len(wins),
            "losses": len(losses),
            "note": (
                "No comparable historical situation is stored yet."
                if not memories
                else "Comparable stored situations found; differences must still be checked."
            ),
        },
    }


__all__ = [
    "MEMORY_TYPES",
    "MemoryHit",
    "score_entry",
    "search_memory",
    "similar_situations",
    "tokenize",
    "write_memory",
]
