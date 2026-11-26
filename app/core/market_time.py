"""Trading sessions, freshness and timestamp parsing for the AI Brain.

Nothing here invents data: every helper either parses a timestamp that came
from a provider or reports that the value is missing/stale.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo

from app.core.market_calendar import MarketCalendar

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")

# Maximum age (seconds) a quote may have before the Brain treats it as stale.
DEFAULT_MAX_QUOTE_AGE = 90
DEFAULT_MAX_CANDLE_AGE = 900
# A candle is only "closed" once the next bar has started.
BAR_SECONDS = {
    "1m": 60, "2m": 120, "3m": 180, "5m": 300, "10m": 600, "15m": 900,
    "20m": 1200, "30m": 1800, "45m": 2700, "1h": 3600, "60m": 3600,
    "2h": 7200, "4h": 14400, "1d": 86400, "1wk": 604800, "1mo": 2592000,
}


@dataclass(frozen=True)
class SessionWindow:
    """One tradable window for a market segment, in IST."""

    name: str
    open: time
    close: time
    days: tuple[int, ...]  # 0 = Monday .. 6 = Sunday

    def contains(self, moment: datetime) -> bool:
        if moment.weekday() not in self.days:
            return False
        return self.open <= moment.time() <= self.close


# NSE equity/derivatives.  Pre-open 09:00-09:15 is deliberately excluded: orders
# there behave differently and the Brain must not fire into an unstable book.
NSE_SESSION = SessionWindow("NSE", time(9, 15), time(15, 30), (0, 1, 2, 3, 4))
# MCX (gold/silver) evening session is not modelled: no broker feed is wired for it.
CRYPTO_SESSION = SessionWindow("CRYPTO", time(0, 0), time(23, 59), (0, 1, 2, 3, 4, 5, 6))


def utc_now() -> datetime:
    return datetime.now(UTC)


def ist_now() -> datetime:
    return datetime.now(IST)


_FYERS_CANDLE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


def parse_timestamp(value: Any) -> Optional[datetime]:
    """Parse a provider timestamp into an aware IST datetime.

    Accepts epoch seconds/milliseconds, ISO-8601 strings (with or without an
    offset) and ``datetime`` objects.  Returns ``None`` when the value is
    missing or unparseable — callers must treat that as "unknown freshness",
    never as "fresh".
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if isinstance(value, (int, float)):
        seconds = float(value)
        if seconds > 1e12:  # milliseconds
            seconds /= 1000.0
        try:
            return datetime.fromtimestamp(seconds, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d{10}(\.\d+)?", text) or re.fullmatch(r"\d{13}", text):
        return parse_timestamp(float(text))
    for fmt in _FYERS_CANDLE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            # Fyers returns IST wall-clock for Indian candles.
            parsed = parsed.replace(tzinfo=IST)
        return parsed.astimezone(UTC)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def age_seconds(timestamp: Any, reference: Optional[datetime] = None) -> Optional[float]:
    """Age of ``timestamp`` in seconds, or ``None`` when unknown."""
    parsed = parse_timestamp(timestamp)
    if parsed is None:
        return None
    ref = reference or utc_now()
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=UTC)
    return (ref - parsed).total_seconds()


def is_fresh(
    timestamp: Any,
    max_age_seconds: int,
    reference: Optional[datetime] = None,
) -> bool:
    age = age_seconds(timestamp, reference)
    return age is not None and -60 <= age <= max_age_seconds


def bar_is_closed(ts: Any, interval: str, reference: Optional[datetime] = None) -> bool:
    """True when the bar starting at ``ts`` has already completed."""
    parsed = parse_timestamp(ts)
    if parsed is None:
        return False
    seconds = BAR_SECONDS.get((interval or "").lower(), 300)
    ref = reference or utc_now()
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=UTC)
    return (ref - parsed).total_seconds() >= seconds


def session_for(segment: str) -> Optional[SessionWindow]:
    key = (segment or "").upper()
    if key in {"NSE", "BSE", "NFO", "BFO", "MCX", "STOCK", "FUTURES", "OPTIONS", "INDEX"}:
        return NSE_SESSION
    if key in {"CRYPTO", "CRYPTO_24_7"}:
        return CRYPTO_SESSION
    return None


def is_market_open(segment: str = "NSE", moment: Optional[datetime] = None) -> bool:
    """Whether the segment is inside its normal session on a trading day."""
    now = moment or ist_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    local = now.astimezone(IST)
    window = session_for(segment)
    if window is None:
        return False
    if not window.contains(local):
        return False
    if window is NSE_SESSION:
        calendar = MarketCalendar()
        return calendar.is_trading_day(local.date())
    return True


def next_session_start(segment: str = "NSE", moment: Optional[datetime] = None) -> Optional[datetime]:
    now = moment or ist_now()
    local = now.astimezone(IST)
    window = session_for(segment)
    if window is None:
        return None
    calendar = MarketCalendar() if window is NSE_SESSION else None
    for offset in range(0, 8):
        day = local.date() + timedelta(days=offset)
        if day.weekday() not in window.days:
            continue
        if calendar is not None and not calendar.is_trading_day(day):
            continue
        candidate = datetime.combine(day, window.open, tzinfo=IST)
        if candidate > local:
            return candidate
    return None


def hhmmss_to_time(value: str) -> time:
    """Parse ``HH:MM`` (or ``HH:MM:SS``) from the risk configuration."""
    parts = [int(p) for p in str(value).split(":")]
    while len(parts) < 3:
        parts.append(0)
    return time(parts[0], parts[1], parts[2])


def in_risk_session(moment: datetime, start: str, end: str) -> bool:
    local = moment.astimezone(IST) if moment.tzinfo else moment.replace(tzinfo=IST)
    return hhmmss_to_time(start) <= local.time() <= hhmmss_to_time(end)


def trading_date(moment: Optional[datetime] = None) -> date:
    return (moment or ist_now()).astimezone(IST).date()


def market_snapshot_reference(symbol: str, ts: Any, source: str) -> dict:
    """Compact provenance record stored on the audit row."""
    parsed = parse_timestamp(ts)
    return {
        "symbol": symbol,
        "source": source,
        "timestamp": parsed.isoformat() if parsed else None,
        "age_seconds": age_seconds(ts),
    }


def newest_timestamp(values: Iterable[Any]) -> Optional[datetime]:
    parsed = [p for p in (parse_timestamp(v) for v in values) if p is not None]
    return max(parsed) if parsed else None


__all__ = [
    "BAR_SECONDS",
    "CRYPTO_SESSION",
    "DEFAULT_MAX_CANDLE_AGE",
    "DEFAULT_MAX_QUOTE_AGE",
    "IST",
    "NSE_SESSION",
    "SessionWindow",
    "age_seconds",
    "bar_is_closed",
    "hhmmss_to_time",
    "in_risk_session",
    "is_fresh",
    "is_market_open",
    "ist_now",
    "market_snapshot_reference",
    "newest_timestamp",
    "next_session_start",
    "parse_timestamp",
    "session_for",
    "trading_date",
    "utc_now",
]
