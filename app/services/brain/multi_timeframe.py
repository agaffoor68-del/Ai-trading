"""Synchronized multi-timeframe market-data pipeline (Task 1).

Responsibilities
----------------
* load the canonical timeframe ladder (3m → 1d) from the existing provider;
* normalise each series (dedupe, sort, validate) **without inventing bars**;
* refuse to expose an unfinished bar, so nothing downstream can look ahead;
* quantify data quality per timeframe: duplicates, gaps, stale, no-data;
* align every timeframe to one decision instant and report the skew.

Nothing here fabricates prices.  A missing bar stays missing and is reported;
a stale series is flagged ``stale`` so the decision layer can emit NO_TRADE.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Sequence

from app.core import market_time as mt
from app.core.datetime_utils import now_ist

logger = logging.getLogger(__name__)

# Canonical ladder for intraday decisions, fastest first.  ``1m`` stays the
# trigger timeframe; the rest provide confirmation.
DECISION_TIMEFRAMES: List[str] = ["1m", "3m", "5m", "15m", "30m", "1h", "1d"]
# The subset this task is specified to synchronise.
SYNC_TIMEFRAMES: List[str] = ["3m", "5m", "15m", "30m", "1h", "4h", "1d"]

# Timeframes where the NSE session divides cleanly, so a missing bar is a real
# gap rather than an artefact of session length (375 min: 375/30 = 12.5).
STRICT_GAP_TIMEFRAMES = frozenset({"1m", "3m", "5m", "15m"})

NSE_SESSION_MINUTES = 375  # 09:15 → 15:30

# A series is stale when its last closed bar is older than this many bar
# lengths (plus slack), regardless of whether the market is open.
STALE_BAR_MULTIPLE = 2.0
STALE_SLACK_SECONDS = 120


def bar_seconds(timeframe: str) -> int:
    """Bar length in seconds for a supported timeframe."""
    return mt.BAR_SECONDS.get((timeframe or "").lower(), 0)


def bar_close_ts(ts: int, timeframe: str) -> int:
    """Epoch second at which the bar starting at ``ts`` finishes."""
    return int(ts) + bar_seconds(timeframe)


def expected_bars_per_session(timeframe: str) -> Optional[int]:
    """Bars a full NSE session should contain, or ``None`` when undefined."""
    seconds = bar_seconds(timeframe)
    if not seconds:
        return None
    if timeframe in ("1d", "1wk", "1mo"):
        return 1
    if seconds > NSE_SESSION_MINUTES * 60:
        return None
    count = NSE_SESSION_MINUTES * 60 // seconds
    return int(count) if count > 0 else None


# --------------------------------------------------------------------------
# Normalisation
# --------------------------------------------------------------------------
@dataclass
class NormalizeReport:
    """What normalisation had to remove, so quality reporting is honest."""

    received: int = 0
    used: int = 0
    duplicates: int = 0
    out_of_order: int = 0
    invalid: int = 0
    incomplete_dropped: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {
            "received": self.received,
            "used": self.used,
            "duplicates_removed": self.duplicates,
            "out_of_order_removed": self.out_of_order,
            "invalid_removed": self.invalid,
            "incomplete_bar_dropped": self.incomplete_dropped,
        }


def _is_valid(candle: Any) -> bool:
    """Structural OHLCV check (delegates to the shared validator)."""
    from app.services.indicator_service import validate_candle

    return validate_candle(candle)


def normalize_candles(
    candles: Iterable[Dict[str, Any]],
    timeframe: str,
    reference: Optional[datetime] = None,
    keep_incomplete: bool = False,
) -> tuple[List[Dict[str, Any]], NormalizeReport]:
    """Return ``(closed_candles_sorted_ascending, report)``.

    * duplicates (same ``ts``) keep the first occurrence and are counted;
    * out-of-order bars are re-sorted, and a bar that appears before an already
      seen later timestamp is counted once;
    * structurally invalid bars are dropped;
    * the still-forming bar is dropped unless ``keep_incomplete`` is set — this
      is the look-ahead guard, not a convenience.
    """
    report = NormalizeReport()
    raw = list(candles or [])
    report.received = len(raw)
    if not raw:
        return [], report

    seen: Dict[int, Dict[str, Any]] = {}
    highest_ts = -1
    for candle in raw:
        if not _is_valid(candle):
            report.invalid += 1
            continue
        try:
            ts = int(candle["ts"])
        except (TypeError, ValueError):
            report.invalid += 1
            continue
        if ts in seen:
            report.duplicates += 1
            continue
        if ts < highest_ts:
            report.out_of_order += 1
        highest_ts = max(highest_ts, ts)
        seen[ts] = {
            "ts": ts,
            "open": float(candle["open"]),
            "high": float(candle["high"]),
            "low": float(candle["low"]),
            "close": float(candle["close"]),
            "volume": float(candle.get("volume") or 0.0),
        }

    ordered = [seen[ts] for ts in sorted(seen)]

    if not keep_incomplete and ordered:
        ref = reference or mt.utc_now()
        while ordered and not mt.bar_is_closed(ordered[-1]["ts"], timeframe, ref):
            ordered.pop()
            report.incomplete_dropped += 1

    report.used = len(ordered)
    return ordered, report


# --------------------------------------------------------------------------
# Gap / staleness assessment
# --------------------------------------------------------------------------
def _ist_date(ts: int) -> date:
    parsed = mt.parse_timestamp(ts)
    if parsed is None:
        return date(1970, 1, 1)
    return parsed.astimezone(mt.IST).date()


def detect_gaps(candles: Sequence[Dict[str, Any]], timeframe: str) -> Dict[str, Any]:
    """Count missing bars inside each *fully covered* trading day.

    Only interior days are judged.  The first and last day of any window are
    partial by construction (the window starts/ends mid-session), so asserting
    a shortfall there would report phantom gaps.  With a single day of history
    the function therefore reports the day count but no missing bars.
    """
    expected = expected_bars_per_session(timeframe)
    if not candles or expected is None:
        return {"expected_per_session": expected, "missing_bars": 0, "gap_days": [], "days_covered": 0}

    by_day: Dict[date, int] = {}
    for candle in candles:
        day = _ist_date(int(candle["ts"]))
        by_day[day] = by_day.get(day, 0) + 1

    days = sorted(by_day)
    strict = timeframe in STRICT_GAP_TIMEFRAMES
    missing = 0
    gap_days: List[Dict[str, Any]] = []

    interior = days[1:-1] if len(days) > 2 else []
    for day in interior:
        present = by_day[day]
        shortfall = max(0, expected - present)
        if shortfall:
            missing += shortfall
            gap_days.append({"date": day.isoformat(), "present": present, "missing": shortfall})
        elif strict and present > expected + 1:
            # More bars than a session can hold: usually a duplicated feed day.
            gap_days.append(
                {"date": day.isoformat(), "present": present, "missing": 0, "anomaly": "excess_bars"}
            )

    return {
        "expected_per_session": expected,
        "missing_bars": missing,
        "gap_days": gap_days[-10:],
        "days_covered": len(days),
    }


@dataclass
class TimeframeQuality:
    """Machine-readable data-quality verdict for one timeframe."""

    timeframe: str
    status: str  # ok | stale | insufficient | no_data | market_closed
    reason: Optional[str] = None
    candles: int = 0
    last_closed_ts: Optional[int] = None
    last_closed_at: Optional[str] = None
    age_seconds: Optional[float] = None
    market_open: bool = False
    duplicates_removed: int = 0
    invalid_removed: int = 0
    incomplete_bar_dropped: int = 0
    missing_bars: int = 0
    expected_per_session: Optional[int] = None
    gap_days: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.status in ("ok", "market_closed")

    def as_dict(self) -> Dict[str, Any]:
        return {
            "timeframe": self.timeframe,
            "status": self.status,
            "reason": self.reason,
            "candles": self.candles,
            "last_closed_ts": self.last_closed_ts,
            "last_closed_at": self.last_closed_at,
            "age_seconds": None if self.age_seconds is None else round(self.age_seconds, 1),
            "market_open": self.market_open,
            "duplicates_removed": self.duplicates_removed,
            "invalid_removed": self.invalid_removed,
            "incomplete_bar_dropped": self.incomplete_bar_dropped,
            "missing_bars": self.missing_bars,
            "expected_per_session": self.expected_per_session,
            "gap_days": self.gap_days,
            "usable": self.usable,
        }


@dataclass
class TimeframeSeries:
    """One timeframe's closed candles plus its quality verdict."""

    timeframe: str
    candles: List[Dict[str, Any]]
    quality: TimeframeQuality

    @property
    def last_close(self) -> Optional[float]:
        return float(self.candles[-1]["close"]) if self.candles else None

    @property
    def last_ts(self) -> Optional[int]:
        return int(self.candles[-1]["ts"]) if self.candles else None

    def as_dict(self, include_candles: bool = False) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "timeframe": self.timeframe,
            "quality": self.quality.as_dict(),
            "last_close": self.last_close,
            "last_ts": self.last_ts,
        }
        if include_candles:
            payload["candles"] = self.candles
        return payload


def assess_timeframe(
    symbol: str,
    timeframe: str,
    candles: Iterable[Dict[str, Any]],
    reference: Optional[datetime] = None,
    min_candles: int = 20,
    market_open: Optional[bool] = None,
) -> TimeframeSeries:
    """Normalise a raw series and decide whether it may feed a decision."""
    ref = reference or mt.utc_now()
    if market_open is None:
        market_open = mt.is_market_open("NSE", now_ist())

    clean, report = normalize_candles(candles, timeframe, reference=ref)
    gaps = detect_gaps(clean, timeframe)

    quality = TimeframeQuality(
        timeframe=timeframe,
        status="ok",
        candles=len(clean),
        duplicates_removed=report.duplicates,
        invalid_removed=report.invalid,
        incomplete_bar_dropped=report.incomplete_dropped,
        missing_bars=gaps.get("missing_bars", 0),
        expected_per_session=gaps.get("expected_per_session"),
        gap_days=gaps.get("gap_days", []),
        market_open=market_open,
    )

    if not clean:
        quality.status = "no_data"
        quality.reason = "provider returned no valid closed candles for this timeframe"
        return TimeframeSeries(timeframe, clean, quality)

    last_ts = int(clean[-1]["ts"])
    close_ts = bar_close_ts(last_ts, timeframe)
    parsed_close = mt.parse_timestamp(close_ts)
    quality.last_closed_ts = last_ts
    quality.last_closed_at = parsed_close.astimezone(mt.IST).isoformat() if parsed_close else None

    reference_aware = ref if ref.tzinfo else ref.replace(tzinfo=mt.UTC)
    if parsed_close is not None:
        quality.age_seconds = (reference_aware - parsed_close).total_seconds()

    seconds = bar_seconds(timeframe)
    stale_after = (seconds * STALE_BAR_MULTIPLE) + STALE_SLACK_SECONDS if seconds else mt.DEFAULT_MAX_CANDLE_AGE

    if len(clean) < min_candles:
        quality.status = "insufficient"
        quality.reason = (
            f"{len(clean)} closed candles available, {min_candles} required for a reliable read"
        )
        return TimeframeSeries(timeframe, clean, quality)

    # Outside the session a series legitimately stops at the previous close.
    if not market_open:
        quality.status = "market_closed"
        quality.reason = "market closed: last closed bar is the session close"
        return TimeframeSeries(timeframe, clean, quality)

    if quality.age_seconds is not None and quality.age_seconds > stale_after:
        quality.status = "stale"
        quality.reason = (
            f"last closed bar is {int(quality.age_seconds)}s old "
            f"(limit {int(stale_after)}s for {timeframe})"
        )
        return TimeframeSeries(timeframe, clean, quality)

    if quality.missing_bars and timeframe in STRICT_GAP_TIMEFRAMES:
        ratio = quality.missing_bars / max(1, len(clean) + quality.missing_bars)
        if ratio > 0.15:
            quality.status = "stale"
            quality.reason = (
                f"{quality.missing_bars} missing bars ({ratio:.0%} of the window) — feed incomplete"
            )
            return TimeframeSeries(timeframe, clean, quality)

    return TimeframeSeries(timeframe, clean, quality)


# --------------------------------------------------------------------------
# Cross-timeframe synchronisation
# --------------------------------------------------------------------------
@dataclass
class SyncReport:
    """How well the timeframes line up at one decision instant."""

    aligned: bool
    as_of: Optional[str]
    skew_seconds: Optional[float]
    usable_timeframes: List[str]
    blocked_timeframes: List[str]
    reasons: Dict[str, str]
    note: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "aligned": self.aligned,
            "as_of": self.as_of,
            "skew_seconds": None if self.skew_seconds is None else round(self.skew_seconds, 1),
            "usable_timeframes": self.usable_timeframes,
            "blocked_timeframes": self.blocked_timeframes,
            "reasons": self.reasons,
            "note": self.note,
        }


def synchronize(series: Dict[str, TimeframeSeries]) -> SyncReport:
    """Check that every usable timeframe ends at the same decision instant.

    ``skew_seconds`` is the spread between the newest and oldest *closed-bar
    end time* across usable timeframes.  A large skew means at least one
    timeframe is lagging, which is reported rather than papered over.
    """
    usable: List[str] = []
    blocked: List[str] = []
    reasons: Dict[str, str] = {}
    ends: Dict[str, int] = {}

    for timeframe, item in series.items():
        if item.quality.usable and item.candles:
            usable.append(timeframe)
            ends[timeframe] = bar_close_ts(int(item.candles[-1]["ts"]), timeframe)
        else:
            blocked.append(timeframe)
            reasons[timeframe] = item.quality.reason or item.quality.status

    if not usable:
        return SyncReport(
            aligned=False,
            as_of=None,
            skew_seconds=None,
            usable_timeframes=[],
            blocked_timeframes=blocked,
            reasons=reasons,
            note="no timeframe has usable closed candles",
        )

    newest = max(ends.values())
    oldest = min(ends.values())
    skew = float(newest - oldest)
    as_of_dt = mt.parse_timestamp(newest)
    as_of = as_of_dt.astimezone(mt.IST).isoformat() if as_of_dt else None

    # Tolerate one bar of the slowest usable timeframe.
    slowest = max(usable, key=lambda tf: bar_seconds(tf) or 0)
    tolerance = float(bar_seconds(slowest) or 300)

    aligned = skew <= tolerance and not blocked
    note = None
    if blocked:
        note = "some timeframes are unusable; the decision uses only the usable set"
    elif skew > tolerance:
        note = (
            f"timeframes disagree by {int(skew)}s "
            f"(tolerance {int(tolerance)}s for {slowest})"
        )

    return SyncReport(
        aligned=aligned,
        as_of=as_of,
        skew_seconds=skew,
        usable_timeframes=sorted(usable, key=lambda tf: bar_seconds(tf) or 0),
        blocked_timeframes=blocked,
        reasons=reasons,
        note=note,
    )


# --------------------------------------------------------------------------
# Snapshot assembly
# --------------------------------------------------------------------------
Loader = Callable[[str, str, int], Awaitable[List[Dict[str, Any]]]]


@dataclass
class MultiTimeframeSnapshot:
    """Everything the decision layer needs about one instrument's candles."""

    symbol: str
    reference: str
    market_open: bool
    timeframes: Dict[str, TimeframeSeries]
    sync: SyncReport

    @property
    def usable(self) -> bool:
        return bool(self.sync.usable_timeframes)

    def series(self, timeframe: str) -> Optional[TimeframeSeries]:
        return self.timeframes.get(timeframe)

    def candles(self, timeframe: str) -> List[Dict[str, Any]]:
        item = self.timeframes.get(timeframe)
        return list(item.candles) if item else []

    def closes(self, timeframe: str) -> List[float]:
        return [float(c["close"]) for c in self.candles(timeframe)]

    def as_dict(self, include_candles: bool = False) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "reference": self.reference,
            "market_open": self.market_open,
            "usable": self.usable,
            "sync": self.sync.as_dict(),
            "timeframes": {
                tf: item.as_dict(include_candles=include_candles)
                for tf, item in self.timeframes.items()
            },
        }


async def load_series(
    symbol: str,
    timeframe: str,
    limit: int,
    loader: Optional[Loader] = None,
    reference: Optional[datetime] = None,
    min_candles: int = 20,
    market_open: Optional[bool] = None,
) -> TimeframeSeries:
    """Fetch + assess one timeframe, degrading to ``no_data`` on failure."""
    if loader is None:
        from app.services.indicator_service import fetch_candles as loader  # type: ignore[assignment]

    try:
        raw = await loader(symbol, timeframe, limit)
    except Exception as error:  # provider/network/token failure
        logger.warning("candle load failed for %s %s: %s", symbol, timeframe, error)
        quality = TimeframeQuality(
            timeframe=timeframe,
            status="no_data",
            reason=f"provider error: {error}",
            market_open=bool(market_open),
        )
        return TimeframeSeries(timeframe, [], quality)

    return assess_timeframe(
        symbol,
        timeframe,
        raw,
        reference=reference,
        min_candles=min_candles,
        market_open=market_open,
    )


async def build_snapshot(
    symbol: str,
    timeframes: Optional[Sequence[str]] = None,
    limit: int = 300,
    loader: Optional[Loader] = None,
    reference: Optional[datetime] = None,
    min_candles: int = 20,
    market_open: Optional[bool] = None,
) -> MultiTimeframeSnapshot:
    """Load every timeframe for ``symbol`` and align them to one instant."""
    import asyncio

    wanted = list(timeframes or DECISION_TIMEFRAMES)
    ref = reference or mt.utc_now()
    if market_open is None:
        market_open = mt.is_market_open("NSE", now_ist())

    results = await asyncio.gather(
        *(
            load_series(
                symbol,
                tf,
                limit,
                loader=loader,
                reference=ref,
                min_candles=min_candles,
                market_open=market_open,
            )
            for tf in wanted
        ),
        return_exceptions=False,
    )

    series = {item.timeframe: item for item in results}
    sync = synchronize(series)
    return MultiTimeframeSnapshot(
        symbol=symbol,
        reference=ref.astimezone(mt.IST).isoformat() if ref.tzinfo else ref.isoformat(),
        market_open=bool(market_open),
        timeframes=series,
        sync=sync,
    )


def data_quality_report(snapshot: MultiTimeframeSnapshot) -> Dict[str, Any]:
    """Compact quality summary suitable for an API response."""
    return {
        "symbol": snapshot.symbol,
        "reference": snapshot.reference,
        "market_open": snapshot.market_open,
        "usable": snapshot.usable,
        "sync": snapshot.sync.as_dict(),
        "timeframes": {
            tf: {
                "status": item.quality.status,
                "reason": item.quality.reason,
                "candles": item.quality.candles,
                "last_closed_at": item.quality.last_closed_at,
                "age_seconds": (
                    None if item.quality.age_seconds is None
                    else round(item.quality.age_seconds, 1)
                ),
                "missing_bars": item.quality.missing_bars,
                "duplicates_removed": item.quality.duplicates_removed,
                "incomplete_bar_dropped": item.quality.incomplete_bar_dropped,
            }
            for tf, item in snapshot.timeframes.items()
        },
    }


__all__ = [
    "DECISION_TIMEFRAMES",
    "SYNC_TIMEFRAMES",
    "MultiTimeframeSnapshot",
    "NormalizeReport",
    "SyncReport",
    "TimeframeQuality",
    "TimeframeSeries",
    "assess_timeframe",
    "bar_close_ts",
    "bar_seconds",
    "build_snapshot",
    "data_quality_report",
    "detect_gaps",
    "expected_bars_per_session",
    "load_series",
    "normalize_candles",
    "synchronize",
]
