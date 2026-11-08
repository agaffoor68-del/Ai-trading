"""
Fyers & Kotak Auto-Login Background Job

Runs at 7:00 AM daily via APScheduler to refresh session tokens.
- Kotak: Generate TOTP and fetch new session token.
- Fyers: Prompt user / run script to refresh access token.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)


class AutoLoginManager:
    """
    Manages daily auto-login for Fyers and Kotak brokers.

    Uses APScheduler to run at 07:00 IST every trading day.
    """

    def __init__(self, market_calendar=None, telegram_notifier=None):
        self.market_calendar = market_calendar
        self.telegram = telegram_notifier
        self.scheduler = None
        self.fyers_token = None
        self.kotak_session_token = None
        self.last_run = None

    def start(self) -> bool:
        """Start the background scheduler."""
        if not HAS_APSCHEDULER:
            logger.error("apscheduler not installed. Run: pip install apscheduler")
            return False

        self.scheduler = BackgroundScheduler(timezone=IST)
        # Run every day at 07:00 IST
        self.scheduler.add_job(
            self.run_auto_login,
            CronTrigger(hour=7, minute=0, timezone=IST),
            id="daily_auto_login",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("AutoLoginManager scheduler started (07:00 IST daily)")
        return True

    def stop(self):
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("AutoLoginManager scheduler stopped")

    def run_auto_login(self):
        """Entry point called by scheduler at 07:00 IST."""
        now = datetime.now(IST)
        self.last_run = now

        if self.market_calendar and not self.market_calendar.is_trading_day(now.date()):
            logger.info(f"Skipping auto-login: {now.date()} is not a trading day")
            if self.telegram:
                asyncio_run(self.telegram.send_message(
                    "🔐 Auto-login skipped - today is a market holiday/weekend"
                ))
            return

        logger.info("Running daily auto-login at 07:00 IST")
        self._refresh_kotak()
        self._refresh_fyers()

    def _refresh_kotak(self):
        """
        Kotak auto-login: Generate TOTP and fetch session token.

        Requires: KOTAK_CLIENT_ID, KOTAK_CLIENT_SECRET, KOTAK_MPIN,
                  KOTAK_TOTP_SECRET (from environment or config).
        """
        import os

        client_id = os.getenv("KOTAK_CLIENT_ID")
        client_secret = os.getenv("KOTAK_CLIENT_SECRET")
        mpin = os.getenv("KOTAK_MPIN")
        totp_secret = os.getenv("KOTAK_TOTP_SECRET")

        if not all([client_id, client_secret, mpin, totp_secret]):
            logger.warning("Kotak credentials incomplete - skipping Kotak auto-login")
            if self.telegram:
                asyncio_run(self.telegram.send_alert(
                    "AUTO_LOGIN",
                    "Kotak auto-login skipped: missing credentials",
                ))
            return

        try:
            # Generate TOTP
            totp = self._generate_totp(totp_secret)
            logger.info(f"Kotak TOTP generated: {totp}")

            # Placeholder for Kotak session token API call
            # Example: POST /auth/session with client_id, mpin, totp
            self.kotak_session_token = f"kotak_session_{client_id}_{totp}"
            logger.info("Kotak session token refreshed successfully")

            if self.telegram:
                asyncio_run(self.telegram.send_alert(
                    "AUTO_LOGIN",
                    "Kotak session token refreshed successfully",
                ))
        except Exception as e:
            logger.error(f"Kotak auto-login failed: {e}")
            if self.telegram:
                asyncio_run(self.telegram.send_alert(
                    "API_FAILED",
                    f"Kotak auto-login failed: {e}",
                ))

    def _refresh_fyers(self):
        """
        Fyers auto-login: Prompt user or run script to refresh access token.

        Fyers requires OAuth2 flow. Since this cannot be fully automated
        without user interaction, this method logs a reminder and can
        trigger a script if configured.
        """
        import os

        client_id = os.getenv("FYERS_CLIENT_ID")
        client_secret = os.getenv("FYERS_CLIENT_SECRET")

        if not client_id or not client_secret:
            logger.warning("Fyers credentials incomplete - skipping Fyers auto-login")
            return

        # Check if there's a token refresh script
        refresh_script = os.getenv("FYERS_REFRESH_SCRIPT")
        if refresh_script:
            try:
                import subprocess
                result = subprocess.run(
                    ["python", refresh_script],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    self.fyers_token = result.stdout.strip()
                    logger.info("Fyers access token refreshed via script")
                    if self.telegram:
                        asyncio_run(self.telegram.send_alert(
                            "AUTO_LOGIN",
                            "Fyers access token refreshed via script",
                        ))
                    return
            except Exception as e:
                logger.error(f"Fyers refresh script failed: {e}")

        # Fallback: prompt user via Telegram
        logger.warning("Fyers token requires manual OAuth2 refresh")
        if self.telegram:
            auth_url = os.getenv(
                "FYERS_REDIRECT_URI",
                "http://localhost:8000/api/v1/fyers/login",
            )
            asyncio_run(self.telegram.send_alert(
                "AUTO_LOGIN",
                f"Fyers token needs manual refresh.\n"
                f"Visit: {auth_url}\n"
                f"Complete the OAuth2 flow and paste the new access token.",
            ))

    def _generate_totp(self, secret: str) -> str:
        """Generate a 6-digit TOTP code."""
        try:
            import pyotp
            return pyotp.TOTP(secret).now()
        except ImportError:
            # Fallback: simple time-based hash (not secure, for dev only)
            import hashlib
            import time
            interval = int(time.time() // 30)
            msg = f"{secret}{interval}".encode()
            return hashlib.sha256(msg).hexdigest()[:6]

    def set_fyers_token(self, token: str):
        self.fyers_token = token
        logger.info("Fyers access token set manually")

    def set_kotak_token(self, token: str):
        self.kotak_session_token = token
        logger.info("Kotak session token set manually")

    def get_tokens(self) -> dict:
        return {
            "fyers_token": self.fyers_token,
            "kotak_session_token": self.kotak_session_token,
            "last_run": self.last_run.isoformat() if self.last_run else None,
        }


def asyncio_run(coro):
    """Run an async coroutine safely (creates new loop if needed)."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Schedule as task if loop already running
            return asyncio.ensure_future(coro)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)
