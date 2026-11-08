"""
Phase 1: Redis WebSocket Tick Cache

Caches live WebSocket ticks in Redis to protect PostgreSQL from high-frequency writes.
Latest LTP per symbol is stored in Redis; completed candles are flushed to PostgreSQL.

Non-Negotiable Rule: Fyers WebSocket is the ONLY source for live market data.
"""

import asyncio
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)


class RedisTickStore:
    """
    Redis-backed tick cache for live WebSocket data.

    Keys:
      - tick:{symbol} -> JSON string of latest tick (24h TTL)
      - ticks:all -> Set of all tracked symbols
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        ttl_seconds: int = 86400,
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password or None
        self.ttl = ttl_seconds
        self._client = None
        self._connected = False

    async def connect(self) -> bool:
        if not HAS_REDIS:
            logger.error("redis not installed. Run: pip install redis")
            return False
        try:
            self._client = aioredis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
            )
            await self._client.ping()
            self._connected = True
            logger.info(f"Redis connected at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self._connected = False
            return False

    async def close(self):
        if self._client:
            await self._client.close()
            self._connected = False

    def _tick_key(self, symbol: str) -> str:
        return f"tick:{symbol}"

    async def write_tick(self, symbol: str, tick: dict) -> bool:
        """Write latest tick for a symbol to Redis (overwrites previous)."""
        if not self._connected:
            return False
        try:
            tick["updated_at"] = datetime.now(IST).isoformat()
            payload = json.dumps(tick, default=str)
            await self._client.set(self._tick_key(symbol), payload, ex=self.ttl)
            await self._client.sadd("ticks:all", symbol)
            return True
        except Exception as e:
            logger.error(f"Redis write_tick error for {symbol}: {e}")
            return False

    async def get_tick(self, symbol: str) -> Optional[dict]:
        """Read latest tick for a symbol from Redis."""
        if not self._connected:
            return None
        try:
            payload = await self._client.get(self._tick_key(symbol))
            if payload:
                return json.loads(payload)
            return None
        except Exception as e:
            logger.error(f"Redis get_tick error for {symbol}: {e}")
            return None

    async def get_all_ticks(self) -> dict:
        """Read all tracked symbols' latest ticks."""
        if not self._connected:
            return {}
        try:
            symbols = await self._client.smembers("ticks:all")
            result = {}
            for sym in symbols:
                tick = await self.get_tick(sym)
                if tick:
                    result[sym] = tick
            return result
        except Exception as e:
            logger.error(f"Redis get_all_ticks error: {e}")
            return {}

    async def subscribe_to_ticks(self, callback, symbols: list[str] = None):
        """
        Subscribe to Redis keyspace notifications for tick updates.
        Calls callback(symbol, tick) whenever a tick is written.
        """
        if not self._connected:
            logger.error("Redis not connected")
            return
        try:
            pubsub = self._client.pubsub()
            await pubsub.subscribe("__keyspace@0__:tick:*")
            logger.info("Subscribed to Redis tick notifications")
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message["type"] == "message":
                    key = (
                        message["data"].decode()
                        if isinstance(message["data"], bytes)
                        else message["data"]
                    )
                    symbol = key.split(":")[-1] if ":" in key else key
                    tick = await self.get_tick(symbol)
                    if tick:
                        await callback(symbol, tick)
        except asyncio.CancelledError:
            logger.info("Tick subscription cancelled")
        except Exception as e:
            logger.error(f"Redis subscription error: {e}")


# Global singleton instance
redis_tick_store = RedisTickStore(
    host=__import__("os").getenv("REDIS_HOST", "localhost"),
    port=int(__import__("os").getenv("REDIS_PORT", "6379")),
    db=int(__import__("os").getenv("REDIS_DB", "0")),
    password=__import__("os").getenv("REDIS_PASSWORD", "") or None,
)
