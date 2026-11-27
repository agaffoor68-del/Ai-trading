"""Trading Data Intelligence Layer (TDIL).

The only surface through which the AI Brain may read platform data.  It wraps
the existing providers (Fyers REST, the Redis tick cache, the 169-indicator
engine, the options-chain service, the news store, the trade/learning tables)
and adds three things the raw providers do not have:

1. **Provenance.**  Every value carries ``source`` and ``timestamp``; nothing is
   synthesised.  A missing value stays ``None``.
2. **Freshness gating.**  ``freshness`` reports per-block ages and a hard
   ``stale`` flag; the decision engine turns that into ``NO_TRADE``.
3. **Scoped access.**  Credentials, broker tokens and raw database rows never
   cross this boundary — only typed, paginated, time-windowed snapshots.

Nothing here writes risk configuration or places orders.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.core import market_time as mt
from app.core.datetime_utils import naive_as_ist, now_ist

logger = logging.getLogger(__name__)

# Indicators that need a feed the platform does not have.  They are reported as
# unavailable rather than guessed, and they never contribute to a decision.
UNAVAILABLE_WITHOUT_FEED = frozenset(
    {
        "vwap_session", "anchored_vwap", "volume_profile", "market_profile",
        "order_block", "fair_value_gap", "cumulative_delta", "tick_rule",
        "buy_sell_volume_ratio", "garch_volatility", "hurst_exponent",
    }
)

# Indicators the Brain considers for a standard options/ index decision.  The
# full 169 remain available through /indicators and the dashboard.
#
# Every id below must exist in ``app.services.indicators.REGISTRY``: the
# snapshot builder silently drops unknown ids, which previously removed six
# indicators from the decision without any error.
DEFAULT_BRAIN_INDICATORS: Sequence[str] = (
    "ema", "sma", "macd", "rsi", "stochrsi", "supertrend", "adx", "donchian",
    "keltner", "bollinger", "atr", "relative_volume", "obv",
    "vwap", "pivot_points", "swing_high_low", "market_structure_break",
    "support_resistance_zones", "put_call_ratio",
    "max_pain", "iv_rank",
)

# Indicators whose absence invalidates a trend/mean-reversion plan.
CRITICAL_INDICATORS = frozenset({"ema", "rsi", "atr"})


@dataclass
class FreshnessBlock:
    """Age/source of one data block."""

    name: str
    timestamp: Optional[str] = None
    age_seconds: Optional[float] = None
    source: Optional[str] = None
    stale: bool = True
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block": self.name,
            "timestamp": self.timestamp,
            "age_seconds": self.age_seconds,
            "source": self.source,
            "stale": self.stale,
            "note": self.note,
        }


@dataclass
class FreshnessReport:
    blocks: List[FreshnessBlock] = field(default_factory=list)
    max_quote_age: int = mt.DEFAULT_MAX_QUOTE_AGE
    max_candle_age: int = mt.DEFAULT_MAX_CANDLE_AGE

    def add(self, block: FreshnessBlock) -> None:
        self.blocks.append(block)

    @property
    def stale(self) -> bool:
        return any(block.stale for block in self.blocks)

    @property
    def stale_blocks(self) -> List[str]:
        return [block.name for block in self.blocks if block.stale]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stale": self.stale,
            "stale_blocks": self.stale_blocks,
            "max_quote_age_seconds": self.max_quote_age,
            "max_candle_age_seconds": self.max_candle_age,
            "blocks": [block.to_dict() for block in self.blocks],
        }


class DataUnavailable(Exception):
    """Raised when a required block cannot be produced from a real source."""


def _block(
    name: str,
    timestamp: Any,
    source: Optional[str],
    max_age: int,
    note: Optional[str] = None,
) -> FreshnessBlock:
    parsed = mt.parse_timestamp(timestamp)
    age = mt.age_seconds(timestamp)
    stale = parsed is None or age is None or age > max_age or age < -120
    if parsed is None:
        note = note or "provider returned no usable timestamp"
    elif stale and age is not None and age > max_age:
        note = note or f"last update {int(age)}s ago exceeds {max_age}s limit"
    return FreshnessBlock(
        name=name,
        timestamp=parsed.isoformat() if parsed else None,
        age_seconds=age,
        source=source,
        stale=stale,
        note=note,
    )


class TradingDataIntelligence:
    """Structured, provenance-aware read access to every platform data block."""

    def __init__(self, max_quote_age: int = mt.DEFAULT_MAX_QUOTE_AGE,
                 max_candle_age: int = mt.DEFAULT_MAX_CANDLE_AGE) -> None:
        self.max_quote_age = max_quote_age
        self.max_candle_age = max_candle_age

    # ------------------------------------------------------------------ market
    async def quotes(self, symbols: Sequence[str]) -> Dict[str, Dict[str, Any]]:
        """Live quotes with source + timestamp (Redis tick cache, Fyers fallback)."""
        if not symbols:
            return {}
        try:
            from app.services.trading_data_service import get_trading_data_service

            service = get_trading_data_service()
            raw = await service.get_live_quotes(list(symbols))
        except Exception as exc:  # provider down is data-unavailable, not fatal
            logger.warning("Quote retrieval failed: %s", exc)
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        for symbol, point in raw.items():
            payload = point.model_dump() if hasattr(point, "model_dump") else dict(point)
            payload["timestamp"] = payload.get("timestamp")
            out[symbol] = payload
        return out

    async def candles(
        self,
        symbol: str,
        interval: str = "5m",
        limit: int = 200,
    ) -> Dict[str, Any]:
        """OHLCV candles from the configured provider only."""
        from app.services import indicator_service

        try:
            payload = await indicator_service.fetch_candles(symbol, interval, limit)
        except Exception as exc:
            logger.warning("Candle retrieval failed for %s %s: %s", symbol, interval, exc)
            return {"symbol": symbol, "interval": interval, "candles": [], "error": str(exc)}
        candles = payload if isinstance(payload, list) else (payload or {}).get("candles", [])
        return {
            "symbol": symbol,
            "interval": interval,
            "candles": candles,
            "count": len(candles),
            "last_ts": candles[-1].get("ts") if candles else None,
            "source": "fyers_v3",
        }

    # -------------------------------------------------------------- indicators
    async def indicators(
        self,
        symbol: str,
        interval: str = "5m",
        indicator_ids: Optional[Sequence[str]] = None,
        limit: int = 300,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Indicator snapshot over real candles; unavailable ids are reported."""
        from app.services import indicator_service
        from app.services.indicators import REGISTRY

        wanted = [i for i in (indicator_ids or DEFAULT_BRAIN_INDICATORS) if i in REGISTRY]
        unknown = [i for i in (indicator_ids or []) if i not in REGISTRY]
        blocked = [i for i in wanted if i in UNAVAILABLE_WITHOUT_FEED]
        computable = [i for i in wanted if i not in UNAVAILABLE_WITHOUT_FEED]
        if not computable:
            return {
                "symbol": symbol,
                "interval": interval,
                "available": False,
                "reason": "no computable indicator requested",
                "unavailable": blocked,
                "unknown": unknown,
                "values": {},
            }
        try:
            payload = await indicator_service.calculate_async(
                symbol=symbol,
                interval=interval,
                indicator_ids=computable,
                params=params or {},
                limit=limit,
            )
        except Exception as exc:
            logger.warning("Indicator calculation failed for %s: %s", symbol, exc)
            return {
                "symbol": symbol,
                "interval": interval,
                "available": False,
                "reason": f"calculation failed: {exc}",
                "unavailable": blocked,
                "unknown": unknown,
                "values": {},
            }
        results = payload.get("results", {}) if isinstance(payload, dict) else {}
        values: Dict[str, Any] = {}
        missing: List[str] = []
        for key, item in results.items():
            latest = _latest_value(item)
            if latest is None:
                missing.append(key)
            else:
                values[key] = latest
        return {
            "symbol": symbol,
            "interval": interval,
            "available": bool(values),
            "as_of": payload.get("as_of") if isinstance(payload, dict) else None,
            "candles": payload.get("candles") if isinstance(payload, dict) else None,
            "values": values,
            "missing": missing + blocked,
            "unavailable": blocked,
            "unknown": unknown,
            "critical_missing": sorted(CRITICAL_INDICATORS.intersection(missing + blocked)),
            "source": "indicator_engine",
        }

    async def indicator_unavailable(self) -> List[str]:
        from app.services.indicators import REGISTRY

        return sorted(i for i, spec in REGISTRY.items() if spec.get("status") != "implemented_tested")

    # ----------------------------------------------------------------- options
    async def options_chain(self, symbol: str, expiry: Optional[str] = None) -> Dict[str, Any]:
        """Option chain + PCR + max pain + IV, straight from the existing service."""
        try:
            from app.services.trading_data_service import get_trading_data_service

            service = get_trading_data_service()
            chain = await service.get_options_chain(symbol, expiry)
        except Exception as exc:
            logger.warning("Option chain failed for %s: %s", symbol, exc)
            return {"symbol": symbol, "available": False, "error": str(exc)}
        if chain is None:
            return {"symbol": symbol, "available": False, "error": "no chain for symbol"}
        payload = chain.model_dump() if hasattr(chain, "model_dump") else dict(chain)
        payload["available"] = True
        payload.setdefault("source", "fyers_v3")
        return payload

    # -------------------------------------------------------------------- news
    async def news(
        self,
        instruments: Optional[Sequence[str]] = None,
        hours: int = 24,
        limit: int = 20,
        regions: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Recent stored news, newest first, filtered by instrument/region."""
        from sqlalchemy import select

        from app.core.brain_models import NewsItem
        from app.core.database import SessionLocal

        cutoff = now_ist() - timedelta(hours=max(1, min(hours, 168)))
        wanted = {i.upper() for i in (instruments or [])}
        region_filter = {r.lower() for r in (regions or [])}
        rows: List[Dict[str, Any]] = []
        try:
            with SessionLocal() as db:
                stmt = select(NewsItem).order_by(NewsItem.published_at.desc().nullslast()).limit(limit * 4)
                for item in db.execute(stmt).scalars():
                    published = naive_as_ist(item.published_at) if item.published_at else None
                    if published and published < cutoff:
                        continue
                    if region_filter and (item.region or "").lower() not in region_filter:
                        continue
                    if wanted and not wanted.intersection({str(i).upper() for i in (item.instruments or [])}):
                        continue
                    rows.append(
                        {
                            "headline": item.headline,
                            "source": item.source,
                            "url": item.url,
                            "region": item.region,
                            "published_at": item.published_at.isoformat() if item.published_at else None,
                            "instruments": item.instruments or [],
                            "sectors": item.sectors or [],
                            "sentiment": item.sentiment,
                            "impact": item.impact,
                            "reliability": item.reliability,
                            "confirmation": item.confirmation,
                            "impact_duration": item.impact_duration,
                            "summary": item.summary,
                        }
                    )
                    if len(rows) >= limit:
                        break
        except Exception as exc:
            logger.warning("News retrieval failed: %s", exc)
            return []
        return rows

    # -------------------------------------------------------- trades & learning
    async def trade_history(
        self,
        user_id: Optional[int] = None,
        days: int = 90,
        limit: int = 100,
        outcome: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Closed trades reconstructed from order records + learning reports."""
        from sqlalchemy import select

        from app.core.brain_models import LearningReport, OrderRecord
        from app.core.database import SessionLocal

        cutoff = now_ist() - timedelta(days=max(1, min(days, 365)))
        rows: List[Dict[str, Any]] = []
        try:
            with SessionLocal() as db:
                stmt = (
                    select(OrderRecord)
                    .where(OrderRecord.created_at >= cutoff)
                    .order_by(OrderRecord.created_at.desc())
                    .limit(limit * 2)
                )
                if user_id is not None:
                    stmt = stmt.where(OrderRecord.user_id == user_id)
                reports: Dict[str, LearningReport] = {}
                rstmt = select(LearningReport).where(LearningReport.created_at >= cutoff)
                if user_id is not None:
                    rstmt = rstmt.where(LearningReport.user_id == user_id)
                for report in db.execute(rstmt).scalars():
                    reports[report.decision_id] = report
                for order in db.execute(stmt).scalars():
                    if order.status not in {"FILLED", "CLOSED", "CANCELLED", "REJECTED"}:
                        continue
                    report = reports.get(order.decision_id)
                    row = {
                        "decision_id": order.decision_id,
                        "symbol": order.symbol,
                        "side": order.side,
                        "quantity": order.quantity,
                        "entry_price": order.requested_price,
                        "exit_price": order.filled_price if order.status == "CLOSED" else None,
                        "pnl": report.pnl if report else None,
                        "outcome": report.outcome if report else ("OPEN" if order.status == "FILLED" else order.status),
                        "status": order.status,
                        "created_at": order.created_at.isoformat() if order.created_at else None,
                        "is_paper": order.is_paper,
                    }
                    if outcome and row["outcome"] != outcome:
                        continue
                    rows.append(row)
                    if len(rows) >= limit:
                        break
        except Exception as exc:
            logger.warning("Trade history retrieval failed: %s", exc)
            return []
        return rows

    async def performance(self, user_id: Optional[int] = None, days: int = 90) -> Dict[str, Any]:
        """Realised performance computed from stored orders/learning rows."""
        trades = await self.trade_history(user_id=user_id, days=days, limit=500)
        closed = [t for t in trades if t.get("pnl") is not None]
        wins = [t for t in closed if (t["pnl"] or 0) > 0]
        losses = [t for t in closed if (t["pnl"] or 0) < 0]
        gross_profit = sum(t["pnl"] for t in wins)
        gross_loss = abs(sum(t["pnl"] for t in losses))
        return {
            "closed_trades": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(closed), 4) if closed else None,
            "net_pnl": round(sum(t["pnl"] for t in closed), 2) if closed else None,
            "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
            "max_drawdown": _max_drawdown([t["pnl"] or 0.0 for t in closed]),
            "source": "order_records+learning_reports",
        }

    async def memory(
        self,
        query: str,
        user_id: Optional[int] = None,
        memory_types: Optional[Sequence[str]] = None,
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        """Retrieve similar historical situations from persistent memory."""
        try:
            from app.services.memory_service import search_memory

            return await search_memory(
                query=query, user_id=user_id, memory_types=memory_types, limit=limit
            )
        except Exception as exc:
            logger.warning("Memory retrieval failed: %s", exc)
            return []

    async def strategy_versions(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        from sqlalchemy import select

        from app.core.brain_models import StrategyVersion
        from app.core.database import SessionLocal

        try:
            with SessionLocal() as db:
                stmt = select(StrategyVersion).order_by(StrategyVersion.created_at.desc()).limit(50)
                if user_id is not None:
                    stmt = stmt.where(StrategyVersion.user_id == user_id)
                return [
                    {
                        "version": row.version,
                        "name": row.name,
                        "status": row.status,
                        "parent_version": row.parent_version,
                        "params": row.params or {},
                        "validation_report": row.validation_report,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }
                    for row in db.execute(stmt).scalars()
                ]
        except Exception as exc:
            logger.warning("Strategy version retrieval failed: %s", exc)
            return []

    # ------------------------------------------------------------ market regime
    async def market_regime(self, symbol: str, interval: str = "1d") -> Dict[str, Any]:
        """Rule-based regime label from real candles (never a guess)."""
        payload = await self.candles(symbol, interval, limit=250)
        candles = payload.get("candles") or []
        if len(candles) < 30:
            return {"symbol": symbol, "regime": "unknown", "reason": "insufficient candles"}
        closes = [c["close"] for c in candles if c.get("close") is not None]
        if len(closes) < 30:
            return {"symbol": symbol, "regime": "unknown", "reason": "insufficient closes"}
        window = closes[-50:] if len(closes) >= 50 else closes
        mean = sum(window) / len(window)
        variance = sum((c - mean) ** 2 for c in window) / len(window)
        std = variance ** 0.5
        atr_like = sum(
            max(
                c["high"] - c["low"],
                abs(c["high"] - (candles[i - 1]["close"] if i else c["close"])),
            )
            for i, c in enumerate(candles[-14:])
        ) / max(1, len(candles[-14:]))
        last = closes[-1]
        slope = (closes[-1] - closes[-min(20, len(closes))]) / max(1, min(20, len(closes)))
        regime = "range"
        if std and abs(last - mean) / std > 1.0 and abs(slope) > std * 0.1:
            regime = "trend_up" if slope > 0 else "trend_down"
        elif atr_like and std and atr_like / max(std, 1e-9) > 1.4:
            regime = "volatile"
        return {
            "symbol": symbol,
            "interval": interval,
            "regime": regime,
            "last_close": last,
            "mean": round(mean, 4),
            "std": round(std, 4),
            "atr14": round(atr_like, 4),
            "slope20": round(slope, 4),
            "as_of": payload.get("last_ts"),
            "source": "fyers_v3",
        }

    # ------------------------------------------------------------- the snapshot
    async def snapshot(
        self,
        symbol: str,
        interval: str = "5m",
        user_id: Optional[int] = None,
        indicator_ids: Optional[Sequence[str]] = None,
        include_options: bool = True,
        include_news: bool = True,
        history_days: int = 90,
    ) -> Dict[str, Any]:
        """Assemble the full, provenance-tagged context for one decision."""
        freshness = FreshnessReport(max_quote_age=self.max_quote_age, max_candle_age=self.max_candle_age)

        quotes = await self.quotes([symbol])
        quote = quotes.get(symbol) or {}
        freshness.add(_block("quote", quote.get("timestamp"), quote.get("source"), self.max_quote_age))

        candle_block = await self.candles(symbol, interval)
        candles = candle_block.get("candles") or []
        last_closed = _last_closed_candle(candles, interval)
        freshness.add(
            _block(
                "candles",
                last_closed.get("ts") if last_closed else candle_block.get("last_ts"),
                candle_block.get("source"),
                self.max_candle_age,
                note=None if candles else "provider returned no candles",
            )
        )

        indicator_block = await self.indicators(symbol, interval, indicator_ids)
        freshness.add(
            _block(
                "indicators",
                indicator_block.get("as_of") or (last_closed or {}).get("ts"),
                indicator_block.get("source"),
                self.max_candle_age,
                note=None if indicator_block.get("available") else indicator_block.get("reason"),
            )
        )

        options_block: Dict[str, Any] = {"available": False}
        if include_options:
            options_block = await self.options_chain(symbol)
            freshness.add(
                _block(
                    "options",
                    options_block.get("timestamp"),
                    options_block.get("source"),
                    max(self.max_quote_age * 5, 600),
                    note=None if options_block.get("available") else "chain unavailable for symbol",
                )
            )

        news_block: List[Dict[str, Any]] = []
        if include_news:
            news_block = await self.news(instruments=[symbol], hours=24, limit=10)
            newest = mt.newest_timestamp(n.get("published_at") for n in news_block)
            freshness.add(
                _block(
                    "news",
                    newest,
                    "news_store",
                    max(self.max_candle_age * 8, 7200),
                    note=None if news_block else "no stored news in window",
                )
            )

        trades = await self.trade_history(user_id=user_id, days=history_days, limit=50)
        performance = await self.performance(user_id=user_id, days=history_days)
        strategies = await self.strategy_versions(user_id=user_id)
        regime = await self.market_regime(symbol, "1d")

        return {
            "symbol": symbol,
            "interval": interval,
            "generated_at": now_ist().isoformat(),
            "quote": quote or None,
            "candles": candles[-200:],
            "candle_meta": {
                "count": len(candles),
                "interval": interval,
                "source": candle_block.get("source"),
                "last_ts": candle_block.get("last_ts"),
            },
            "indicators": indicator_block,
            "options": options_block,
            "news": news_block,
            "trades": trades,
            "performance": performance,
            "strategies": strategies,
            "regime": regime,
            "freshness": freshness.to_dict(),
            "data_complete": not freshness.stale and bool(candles) and bool(indicator_block.get("values")),
        }


def _latest_value(result: Any) -> Optional[float]:
    """Last finite number in an indicator result (series/levels/meta/dict).

    The engine returns ``{"series": {...}, "levels": {...}, "meta": {...}}``;
    a bare number is also accepted.  ``None`` means "no value produced", which
    the caller must treat as missing rather than zero.
    """
    if result is None:
        return None
    if isinstance(result, (int, float)) and not isinstance(result, bool):
        return float(result)
    if not isinstance(result, dict):
        return None
    if result.get("status") in {"error", "not_implemented", "insufficient_data"}:
        return None
    candidates: List[Any] = []
    for section in ("series", "levels"):
        block = result.get(section) or {}
        if isinstance(block, dict):
            for series in block.values():
                if isinstance(series, (list, tuple)):
                    candidates.extend(series)
                elif isinstance(series, (int, float)) and not isinstance(series, bool):
                    candidates.append(series)
    if not candidates:
        meta = result.get("meta") or {}
        if isinstance(meta, dict):
            candidates.extend(
                v for v in meta.values() if isinstance(v, (int, float)) and not isinstance(v, bool)
            )
    numeric = [float(c) for c in candidates if isinstance(c, (int, float)) and not isinstance(c, bool)]
    return numeric[-1] if numeric else None


def _last_closed_candle(candles: Iterable[Dict[str, Any]], interval: str) -> Optional[Dict[str, Any]]:
    """Last candle whose bar has completed (prevents look-ahead on the live bar)."""
    for candle in reversed(list(candles)):
        if mt.bar_is_closed(candle.get("ts"), interval):
            return candle
    return None


def _max_drawdown(equity: Sequence[float]) -> Optional[float]:
    if not equity:
        return None
    peak = equity[0]
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value - peak)
    return round(worst, 2)


_tdil: Optional[TradingDataIntelligence] = None


def get_tdil() -> TradingDataIntelligence:
    """Process-wide singleton (cheap: holds no state but config)."""
    global _tdil
    if _tdil is None:
        _tdil = TradingDataIntelligence()
    return _tdil


__all__ = [
    "CRITICAL_INDICATORS",
    "DEFAULT_BRAIN_INDICATORS",
    "DataUnavailable",
    "FreshnessBlock",
    "FreshnessReport",
    "TradingDataIntelligence",
    "UNAVAILABLE_WITHOUT_FEED",
    "get_tdil",
]
