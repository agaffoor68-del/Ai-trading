"""
Market Calendar - NSE Holiday & Time Filter

Prevents trade execution on weekends and NSE holidays.
Provides auto square-off gating for valid trading days only.
"""

import json
import logging
import os
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

logger = logging.getLogger(__name__)

# Default NSE trading hours
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)

# Default NSE holidays for 2026 (placeholder - user should update)
DEFAULT_NSE_HOLIDAYS_2026 = [
    "2026-01-26",  # Republic Day
    "2026-03-30",  # Holi
    "2026-04-01",  # Annual Closing
    "2026-04-10",  # Good Friday
    "2026-05-01",  # Maharashtra Day
    "2026-08-15",  # Independence Day
    "2026-10-02",  # Gandhi Jayanti
    "2026-10-21",  # Diwali
    "2026-12-25",  # Christmas
]


class MarketCalendar:
    """
    Utility to determine if the market is open for trading.

    Loads NSE holidays from a JSON file or uses built-in defaults.
    Blocks trading on weekends and holidays.
    """

    def __init__(self, holidays_file: Optional[str] = None):
        self.holidays_file = holidays_file or os.path.join(
            os.path.dirname(__file__), "..", "core", "nse_holidays.json"
        )
        self.holidays: set[date] = self._load_holidays()

    def _load_holidays(self) -> set[date]:
        holidays: set[date] = set()
        try:
            if Path(self.holidays_file).exists():
                with open(self.holidays_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for h in data.get("holidays", []):
                        holidays.add(date.fromisoformat(h))
            else:
                for h in DEFAULT_NSE_HOLIDAYS_2026:
                    holidays.add(date.fromisoformat(h))
        except Exception as e:
            logger.error(f"Failed to load holidays: {e}. Using defaults.")
            for h in DEFAULT_NSE_HOLIDAYS_2026:
                holidays.add(date.fromisoformat(h))
        self.holidays = holidays
        self.save_holidays()
        return holidays

    def save_holidays(self) -> None:
        """Persist current holiday list to JSON file."""
        try:
            path = Path(self.holidays_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {"holidays": sorted(d.isoformat() for d in self.holidays)}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save holidays: {e}")

    def add_holiday(self, holiday_date: str | date) -> None:
        d = date.fromisoformat(holiday_date) if isinstance(holiday_date, str) else holiday_date
        self.holidays.add(d)
        self.save_holidays()

    def remove_holiday(self, holiday_date: str | date) -> None:
        d = date.fromisoformat(holiday_date) if isinstance(holiday_date, str) else holiday_date
        self.holidays.discard(d)
        self.save_holidays()

    def is_trading_day(self, check_date: Optional[date] = None) -> bool:
        """Return True if the date is a weekday and not an NSE holiday."""
        d = check_date or datetime.now(IST).date()
        if d.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        if d in self.holidays:
            return False
        return True

    def is_market_open(self, check_time: Optional[datetime] = None) -> bool:
        """Return True if market is currently open (weekday, not holiday, within hours)."""
        now = check_time or datetime.now(IST)
        if not self.is_trading_day(now.date()):
            return False
        t = now.time()
        return MARKET_OPEN <= t <= MARKET_CLOSE

    def can_trade(self, check_time: Optional[datetime] = None) -> bool:
        """Alias for is_market_open - used by execution engine gate."""
        return self.is_market_open(check_time)

    def time_to_close(self, check_time: Optional[datetime] = None) -> int:
        """Minutes remaining until market close. Returns 0 if closed/not trading day."""
        now = check_time or datetime.now(IST)
        if not self.is_market_open(now):
            return 0
        close_dt = datetime.combine(now.date(), MARKET_CLOSE, tzinfo=IST)
        delta = (close_dt - now).total_seconds()
        return max(0, int(delta // 60))

    def next_trading_day(self, from_date: Optional[date] = None) -> date:
        d = from_date or datetime.now(IST).date()
        from datetime import timedelta
        d = d + timedelta(days=1)
        while not self.is_trading_day(d):
            d += timedelta(days=1)
        return d
