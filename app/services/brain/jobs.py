"""Background jobs for the AI Brain.

Runs as asyncio tasks inside the existing FastAPI process (no new queue
dependency).  Every loop is defensive: one failing iteration is logged and the
loop continues, and each job can be disabled by configuration.

Jobs:

* ``news_ingest_loop``     – pull India + global feeds on an interval.
* ``monitor_loop``         – check open positions against stop/target/limits.
* ``strategy_learning_loop`` – validate the newest candidate version.
* ``reconcile_loop``       – local vs broker position reconciliation.

Nothing here trades: the loops observe, learn and alert.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.core import market_time as mt
from app.core.config import settings
from app.core.datetime_utils import now_ist
from app.services.brain.decision_engine import get_decision_engine
from app.services.brain.execution_service import get_execution_service
from app.services.brain.learning_engine import get_learning_engine
from app.services.brain.news_service import get_news_service
from app.services.brain.risk_engine import get_risk_engine

logger = logging.getLogger(__name__)

NEWS_INTERVAL_SECONDS = 15 * 60
MONITOR_INTERVAL_SECONDS = 60
RECONCILE_INTERVAL_SECONDS = 15 * 60
LEARNING_INTERVAL_SECONDS = 60 * 60

_tasks: List[asyncio.Task] = []
_started = False


def _enabled(flag: str, default: bool = True) -> bool:
    return bool(getattr(settings, flag, default))


async def news_ingest_loop() -> None:
    """Refresh stored news.  Failures are logged, never raised."""
    while True:
        try:
            report = await get_news_service().ingest()
            logger.info(
                "News ingest: fetched=%s stored=%s dup=%s errors=%s",
                report.get("fetched"), report.get("stored"),
                report.get("duplicates"), len(report.get("errors") or []),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("News ingest loop iteration failed")
        await asyncio.sleep(NEWS_INTERVAL_SECONDS)


async def monitor_loop() -> None:
    """Position monitoring: stop/target proximity and risk usage alerts."""
    notifier = None
    try:
        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            from app.services.telegram_notifier import TelegramNotifier

            notifier = TelegramNotifier(settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID)
    except Exception:
        logger.debug("Telegram notifier unavailable", exc_info=True)

    while True:
        try:
            state = await get_decision_engine().monitor()
            for alert in state.get("alerts") or []:
                logger.warning("Position alert: %s", alert)
                if notifier is not None:
                    await notifier.send_message(
                        f"⚠️ {alert.get('type')}: {alert.get('symbol')} "
                        f"ltp={alert.get('ltp')} sl={alert.get('stop_loss')}"
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Monitor loop iteration failed")
        await asyncio.sleep(MONITOR_INTERVAL_SECONDS)


async def reconcile_loop() -> None:
    """Detect drift between local orders and broker positions."""
    while True:
        try:
            result = await get_execution_service().reconcile()
            if not result.get("matched"):
                logger.warning("Reconciliation discrepancies: %s", result.get("discrepancies"))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Reconcile loop iteration failed")
        await asyncio.sleep(RECONCILE_INTERVAL_SECONDS)


async def strategy_learning_loop() -> None:
    """Validate the newest draft candidate against real history."""
    while True:
        try:
            engine = get_learning_engine()
            pending = [
                v for v in engine.history(limit=10) if v.get("status") == "draft"
            ]
            for version in pending[:1]:
                params = version.get("params") or {}
                symbol = params.get("symbol")
                interval = params.get("interval", "1d")
                if not symbol:
                    continue
                candles = await engine.load_candles(symbol, interval, 800)
                if len(candles) < 120:
                    logger.info("Skipping validation for %s: only %s candles", version["version"], len(candles))
                    continue
                report = engine.validate(version["version"], symbol, interval, candles)
                logger.info(
                    "Strategy %s validated: promoted=%s reason=%s",
                    version["version"], report.get("promoted"), report.get("reason"),
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Strategy learning loop iteration failed")
        await asyncio.sleep(LEARNING_INTERVAL_SECONDS)


def start_background_jobs() -> List[str]:
    """Start enabled loops once.  Returns the started job names."""
    global _started
    if _started:
        return []
    started: List[str] = []
    candidates = {
        "news_ingest": (news_ingest_loop, _enabled("BRAIN_NEWS_INGEST_ENABLED", True)),
        "monitor": (monitor_loop, _enabled("BRAIN_MONITOR_ENABLED", True)),
        "reconcile": (reconcile_loop, _enabled("BRAIN_RECONCILE_ENABLED", True)),
        "strategy_learning": (
            strategy_learning_loop,
            _enabled("BRAIN_STRATEGY_LEARNING_ENABLED", False),
        ),
    }
    for name, (coro, enabled) in candidates.items():
        if not enabled:
            continue
        _tasks.append(asyncio.create_task(coro(), name=f"brain-{name}"))
        started.append(name)
    _started = True
    logger.info("AI Brain background jobs started: %s", started or "none")
    return started


async def stop_background_jobs() -> None:
    """Cancel every loop and wait briefly for clean shutdown."""
    global _started
    for task in _tasks:
        task.cancel()
    for task in _tasks:
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    _tasks.clear()
    _started = False
    logger.info("AI Brain background jobs stopped")


def job_status() -> Dict[str, Any]:
    return {
        "started": _started,
        "jobs": [
            {"name": task.get_name(), "done": task.done(), "cancelled": task.cancelled()}
            for task in _tasks
        ],
        "server_time": now_ist().isoformat(),
    }


__all__ = [
    "job_status",
    "monitor_loop",
    "news_ingest_loop",
    "reconcile_loop",
    "start_background_jobs",
    "stop_background_jobs",
    "strategy_learning_loop",
]
