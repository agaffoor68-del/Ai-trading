"""
NTP Time Synchronization Module

Syncs system time with NTP servers on startup and provides a drift guard
that rejects trade execution if server time drifts by more than 2 seconds
from actual time. Critical for institutional-grade trading systems where
timestamps determine order validity, SL/target triggers, and PnL attribution.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

try:
    import ntplib
    HAS_NTPLIB = True
except ImportError:
    HAS_NTPLIB = False

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)

# Default NTP servers
DEFAULT_NTP_SERVERS = [
    "time.google.com",
    "in.pool.ntp.org",
    "pool.ntp.org",
    "time.windows.com",
]

MAX_DRIFT_SECONDS = 2.0


@dataclass
class TimeSyncResult:
    synced: bool
    ntp_time: Optional[datetime] = None
    system_time: Optional[datetime] = None
    drift_seconds: Optional[float] = None
    offset_seconds: Optional[float] = None
    server: Optional[str] = None
    error: Optional[str] = None


class TimeSyncer:
    """
    Synchronizes local system time with NTP servers.

    Provides:
    - Initial sync on server startup
    - Drift check before trade execution (reject if > 2 seconds)
    - Offset calculation to adjust system time readings
    """

    def __init__(
        self,
        ntp_servers: Optional[list[str]] = None,
        max_drift_seconds: float = MAX_DRIFT_SECONDS,
        timeout: int = 5,
    ):
        self.ntp_servers = ntp_servers or DEFAULT_NTP_SERVERS
        self.max_drift_seconds = max_drift_seconds
        self.timeout = timeout
        self.offset_seconds: float = 0.0  # ntp_time - system_time
        self.last_sync: Optional[datetime] = None
        self.last_result: Optional[TimeSyncResult] = None
        self.is_synced: bool = False

    async def sync(self) -> TimeSyncResult:
        """Attempt to sync with NTP servers (tries each until one succeeds)."""
        if not HAS_NTPLIB:
            result = TimeSyncResult(
                synced=False,
                error="ntplib not installed. Run: pip install ntplib",
            )
            self.last_result = result
            self.is_synced = False
            return result

        import asyncio

        loop = asyncio.get_event_loop()

        for server in self.ntp_servers:
            try:
                client = ntplib.NTPClient()
                response = await loop.run_in_executor(
                    None, lambda: client.request(server, version=3, timeout=self.timeout)
                )

                ntp_time = datetime.fromtimestamp(response.tx_time, tz=timezone.utc)
                system_time = datetime.now(timezone.utc)
                drift = abs((ntp_time - system_time).total_seconds())
                offset = (ntp_time - system_time).total_seconds()

                self.offset_seconds = offset
                self.last_sync = system_time
                self.is_synced = drift <= self.max_drift_seconds

                result = TimeSyncResult(
                    synced=self.is_synced,
                    ntp_time=ntp_time,
                    system_time=system_time,
                    drift_seconds=round(drift, 4),
                    offset_seconds=round(offset, 4),
                    server=server,
                )
                self.last_result = result

                if self.is_synced:
                    logger.info(
                        f"NTP synced with {server}: offset={offset:.4f}s, drift={drift:.4f}s"
                    )
                else:
                    logger.warning(
                        f"NTP drift exceeds threshold: {drift:.4f}s > {self.max_drift_seconds}s"
                    )

                return result

            except Exception as e:
                logger.warning(f"NTP sync failed for {server}: {e}")
                continue

        # All servers failed
        result = TimeSyncResult(
            synced=False,
            error="All NTP servers unreachable",
        )
        self.last_result = result
        self.is_synced = False
        logger.error("NTP sync failed: all servers unreachable")
        return result

    def get_adjusted_now(self) -> datetime:
        """Return current UTC time adjusted by NTP offset."""
        return datetime.now(timezone.utc) + __import__("datetime").timedelta(
            seconds=self.offset_seconds
        )

    def is_time_valid(self, max_drift: Optional[float] = None) -> bool:
        """
        Check if current time is within acceptable drift from NTP.

        Returns False if not synced or drift exceeds threshold.
        Trade execution should be rejected when this returns False.
        """
        if not self.is_synced:
            return False

        threshold = max_drift if max_drift is not None else self.max_drift_seconds

        # Re-check drift periodically (if last sync was > 5 min ago, be conservative)
        if self.last_sync:
            elapsed = (datetime.now(timezone.utc) - self.last_sync).total_seconds()
            if elapsed > 300:  # 5 minutes
                # Drift accumulates ~15ms/min for typical quartz, be conservative
                estimated_drift = abs(self.offset_seconds) + (elapsed * 0.015)
                if estimated_drift > threshold:
                    logger.warning(
                        f"Estimated time drift {estimated_drift:.4f}s exceeds threshold {threshold}s"
                    )
                    return False

        return True

    def require_time_valid(self) -> None:
        """Raise if time is not valid for trading."""
        if not self.is_time_valid():
            drift_info = ""
            if self.last_result and self.last_result.drift_seconds is not None:
                drift_info = f" (last drift: {self.last_result.drift_seconds}s)"
            raise RuntimeError(
                f"System time not synchronized with NTP or drift exceeds "
                f"{self.max_drift_seconds}s{drift_info}. Rejecting trade execution."
            )


# Global singleton instance
time_syncer = TimeSyncer()
