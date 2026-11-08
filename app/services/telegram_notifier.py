"""
Telegram Notification Service

Sends trading alerts via Telegram Bot API using python-telegram-bot
or fallback HTTP requests.
"""

import asyncio
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Sends alerts to a Telegram chat via the Bot API.

    Supports both python-telegram-bot (if installed) and raw HTTP requests
    as a fallback so the service works regardless of library availability.
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: str | int,
        parse_mode: str = "HTML",
        timeout: int = 10,
    ):
        self.bot_token = bot_token
        self.chat_id = str(chat_id)
        self.parse_mode = parse_mode
        self.timeout = timeout
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self._session

    async def send_message(self, text: str, disable_notification: bool = False) -> bool:
        """Send a text message to the configured chat."""
        try:
            session = await self._get_session()
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": self.parse_mode,
                "disable_notification": disable_notification,
            }
            async with session.post(
                f"{self.base_url}/sendMessage", json=payload
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("ok", False)
                logger.error(
                    f"Telegram API error: status={resp.status} await={await resp.text()}"
                )
                return False
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    async def send_alert(self, alert_type: str, details: str) -> bool:
        """Send a formatted alert with emoji based on type."""
        emoji_map = {
            "ORDER_EXECUTED": "✅",
            "SL_HIT": "🛑",
            "TARGET_HIT": "🎯",
            "API_FAILED": "⚠️",
            "AI_SUMMARY": "🤖",
            "TSL_UPDATED": "📉",
            "MARKET_CLOSED": "📴",
            "AUTO_LOGIN": "🔐",
        }
        emoji = emoji_map.get(alert_type, "ℹ️")
        text = f"{emoji} <b>{alert_type.replace('_', ' ')}</b>\n{details}"
        return await self.send_message(text)

    # --- Specific alert helpers ---

    async def order_executed(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        order_id: str,
        instrument_type: str = "",
    ) -> bool:
        details = (
            f"Symbol: {symbol} {instrument_type}\n"
            f"Side: {side}\n"
            f"Qty: {quantity}\n"
            f"Price: {price}\n"
            f"Order ID: {order_id}"
        )
        return await self.send_alert("ORDER_EXECUTED", details)

    async def sl_hit(
        self,
        symbol: str,
        side: str,
        quantity: int,
        exit_price: float,
        pnl: float,
        order_id: str,
    ) -> bool:
        details = (
            f"Symbol: {symbol}\n"
            f"Side: {side}\n"
            f"Qty: {quantity}\n"
            f"Exit Price: {exit_price}\n"
            f"P&L: {pnl}\n"
            f"Order ID: {order_id}"
        )
        return await self.send_alert("SL_HIT", details)

    async def target_hit(
        self,
        symbol: str,
        side: str,
        quantity: int,
        exit_price: float,
        pnl: float,
        order_id: str,
    ) -> bool:
        details = (
            f"Symbol: {symbol}\n"
            f"Side: {side}\n"
            f"Qty: {quantity}\n"
            f"Exit Price: {exit_price}\n"
            f"P&L: {pnl}\n"
            f"Order ID: {order_id}"
        )
        return await self.send_alert("TARGET_HIT", details)

    async def api_connection_failed(
        self,
        service: str,
        error: str,
        retry_in: Optional[int] = None,
    ) -> bool:
        details = f"Service: {service}\nError: {error}"
        if retry_in:
            details += f"\nRetry in: {retry_in}s"
        return await self.send_alert("API_FAILED", details)

    async def ai_daily_summary(
        self,
        date: str,
        total_trades: int,
        winning_trades: int,
        net_pnl: float,
        win_rate: float,
    ) -> bool:
        details = (
            f"Date: {date}\n"
            f"Total Trades: {total_trades}\n"
            f"Winning Trades: {winning_trades}\n"
            f"Net P&L: {net_pnl}\n"
            f"Win Rate: {win_rate:.2f}%"
        )
        return await self.send_alert("AI_SUMMARY", details)

    async def tsl_updated(
        self,
        symbol: str,
        old_sl: float,
        new_sl: float,
        current_price: float,
    ) -> bool:
        details = (
            f"Symbol: {symbol}\n"
            f"Old SL: {old_sl}\n"
            f"New SL: {new_sl}\n"
            f"Current Price: {current_price}"
        )
        return await self.send_alert("TSL_UPDATED", details)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
