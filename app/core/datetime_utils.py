"""
Timezone-aware datetime utilities.

All datetimes in this codebase must be timezone-aware (UTC).
This module provides helpers to ensure consistent handling.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Application timezone (IST)
IST = ZoneInfo("Asia/Kolkata")

# UTC timezone
UTC = timezone.utc


def now_utc() -> datetime:
    """Get current time in UTC (timezone-aware)."""
    return datetime.now(UTC)


def now_ist() -> datetime:
    """Get current time in IST (timezone-aware)."""
    return datetime.now(IST)


def to_utc(dt: datetime) -> datetime:
    """
    Convert any datetime to UTC.
    
    If naive, treats as UTC.
    If aware, converts to UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_ist(dt: datetime) -> datetime:
    """
    Convert any datetime to IST.
    
    If naive, treats as UTC then converts to IST.
    If aware, converts to IST.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC).astimezone(IST)
    return dt.astimezone(IST)


def parse_iso_utc(iso_string: str) -> datetime:
    """
    Parse ISO format string to UTC datetime.
    
    If string has no timezone, treats as UTC.
    """
    dt = datetime.fromisoformat(iso_string)
    return to_utc(dt)


def parse_iso_ist(iso_string: str) -> datetime:
    """
    Parse ISO format string to IST datetime.
    
    If string has no timezone, treats as UTC then converts to IST.
    """
    dt = datetime.fromisoformat(iso_string)
    return to_ist(dt)


def naive_as_utc(dt: datetime) -> datetime:
    """
    Treat a naive datetime as UTC.
    
    Use this for reading old database rows that stored naive UTC times.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def naive_as_ist(dt: datetime) -> datetime:
    """
    Treat a naive datetime as IST.
    
    Use this for reading old database rows that stored naive IST times.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt


def utc_to_epoch(dt: datetime) -> int:
    """Convert timezone-aware UTC datetime to Unix epoch seconds."""
    return int(to_utc(dt).timestamp())


def epoch_to_utc(epoch: int) -> datetime:
    """Convert Unix epoch seconds to timezone-aware UTC datetime."""
    return datetime.fromtimestamp(epoch, UTC)


def epoch_to_ist(epoch: int) -> datetime:
    """Convert Unix epoch seconds to timezone-aware IST datetime."""
    return datetime.fromtimestamp(epoch, IST)