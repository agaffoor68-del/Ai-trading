"""
Phase 1: Redis WebSocket Tick Cache

Caches live WebSocket ticks in Redis to protect PostgreSQL from high-frequency writes.
Latest LTP per symbol is stored in Redis; completed candles are flushed to PostgreSQL.

Non-Negotiable Rule: Fyers WebSocket is the ONLY source for live market data.
"""

import asyncio
import json
import logging
from urllib.parse import urlparse
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Callable

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
    
    Features:
    - Reads REDIS_URL from environment (no localhost default in production)
    - If REDIS_URL missing or Redis unreachable at startup:
      - Logs one clear ERROR: "Redis unavailable, live ticks disabled"
      - Keeps server running
      - Retries connection in background with backoff (5s up to 60s)
    - All operations handle Redis being down without raising
    - Supports both redis:// and rediss:// (TLS) URLs
    """

    def __init__(
        self,
        ttl_seconds: int = 86400,
    ):
        from app.core.config import settings
        self.url = settings.REDIS_URL  # Read from env var, no default
        self.ttl = ttl_seconds
        self._client = None
        self._connected = False
        self._host = None
        self._port = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._stop_reconnect = False
        
    def is_connected(self) -> bool:
        """Check if Redis is currently connected."""
        return self._connected

    async def start(self):
        """Start the Redis connection manager (call once at startup)."""
        if not HAS_REDIS:
            logger.error("redis not installed. Run: pip install redis")
            return
        
        if not self.url:
            logger.error("REDIS_URL not set in environment - Redis unavailable, live ticks disabled")
            return
        
        # Try initial connection (non-blocking)
        await self._try_connect()
        
        # Start background reconnection task
        self._stop_reconnect = False
        self._reconnect_task = asyncio.create_task(self._reconnect_loop(), name="redis-reconnect")
        logger.info("Redis connection manager started")

    async def _try_connect(self) -> bool:
        """Try to connect to Redis. Returns True if successful."""
        if not self.url:
            return False
            
        try:
            parsed = urlparse(self.url)
            self._host = parsed.hostname
            self._port = parsed.port or 6379
            logger.info("Connecting to Redis at %s:%s", self._host, self._port)
            
            # Support both redis:// and rediss:// (TLS)
            self._client = aioredis.from_url(self.url, decode_responses=True)
            await self._client.ping()
            self._connected = True
            logger.info("Redis connected successfully at %s:%s", self._host, self._port)
            return True
        except Exception as e:
            logger.error("Redis unavailable, live ticks disabled: %s", e)
            self._connected = False
            self._client = None
            return False

    async def _reconnect_loop(self):
        """Background task that retries connection with exponential backoff."""
        backoff = 5
        max_backoff = 60
        
        while not self._stop_reconnect:
            if self._connected:
                await asyncio.sleep(5)
                continue
                
            logger.info("Attempting to reconnect to Redis...")
            if await self._try_connect():
                logger.info("Redis reconnected successfully")
                backoff = 5  # Reset backoff on success
            else:
                logger.warning("Redis reconnect failed, retrying in %ds (max %ds)", backoff, max_backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    async def stop(self):
        """Stop the Redis connection manager."""
        self._stop_reconnect = True
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        await self.close()

    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
        self._connected = False

    def _tick_key(self, symbol: str) -> str:
        return f"tick:{symbol}"

    async def write_tick(self, symbol: str, tick: dict) -> bool:
        """Write latest tick for a symbol to Redis (overwrites previous).
        
        Returns False if Redis is unavailable (never raises).
        """
        if not self._connected or not self._client:
            return False
        try:
            tick["updated_at"] = datetime.now(IST).isoformat()
            payload = json.dumps(tick, default=str)
            await self._client.set(self._tick_key(symbol), payload, ex=self.ttl)
            await self._client.sadd("ticks:all", symbol)
            return True
        except Exception as e:
            logger.error("Redis write_tick error for %s: %s", symbol, e)
            # Connection might have dropped
            self._connected = False
            return False

    async def get_tick(self, symbol: str) -> Optional[dict]:
        """Read latest tick for a symbol from Redis.
        
        Returns None if Redis is unavailable or key doesn't exist (never raises).
        """
        if not self._connected or not self._client:
            return None
        try:
            payload = await self._client.get(self._tick_key(symbol))
            if payload:
                return json.loads(payload)
            return None
        except Exception as e:
            logger.error("Redis get_tick error for %s: %s", symbol, e)
            self._connected = False
            return None

    async def get_all_ticks(self) -> dict:
        """Read all tracked symbols' latest ticks."""
        if not self._connected or not self._client:
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
            logger.error("Redis get_all_ticks error: %s", e)
            self._connected = False
            return {}

    async def subscribe_to_ticks(self, callback: Callable, symbols: list[str] = None):
        """
        Subscribe to Redis keyspace notifications for tick updates.
        Calls callback(symbol, tick) whenever a tick is written.
        """
        if not self._connected or not self._client:
            logger.warning("Redis not connected, cannot subscribe to ticks")
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
            logger.error("Redis subscription error: %s", e)


# Global singleton instance
redis_tick_store = RedisTickStore()