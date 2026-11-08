"""
API Rate Limiter & Retry Queue

TokenBucket rate limiter for broker API calls (Fyers: 10 req/sec, Kotak: configurable).
Automatic retry with exponential backoff (2s, 4s, 8s) on failures (network, HTTP 429, 5xx).
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class Broker(str, Enum):
    FYERS = "fyers"
    KOTAK = "kotak"


@dataclass
class RateLimitConfig:
    """Rate limit configuration per broker."""
    max_rate: float = 10.0  # requests per second
    max_retries: int = 3
    base_delay: float = 2.0  # seconds
    max_delay: float = 8.0  # seconds


@dataclass
class RetryResult:
    success: bool
    result: Optional[any] = None
    error: Optional[str] = None
    attempts: int = 0
    total_delay: float = 0.0


class TokenBucket:
    """
    Token bucket rate limiter.

    Tokens are added at `rate` tokens per second. Each API call consumes 1 token.
    If no tokens available, the caller waits until a token is available.
    """

    def __init__(self, rate: float = 10.0, capacity: Optional[float] = None):
        self.rate = rate  # tokens per second
        self.capacity = capacity if capacity is not None else rate
        self.tokens = float(self.capacity)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            while self.tokens < 1.0:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_update = now

                if self.tokens < 1.0:
                    wait_time = (1.0 - self.tokens) / self.rate
                    await asyncio.sleep(wait_time)
                    # Recalculate after sleep
                    now = time.monotonic()
                    elapsed = now - self.last_update
                    self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                    self.last_update = now

            self.tokens -= 1.0

    def try_acquire(self) -> bool:
        """Try to acquire a token without waiting. Returns True if acquired."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    def get_available_tokens(self) -> float:
        """Return current available tokens (approximate)."""
        now = time.monotonic()
        elapsed = now - self.last_update
        return min(self.capacity, self.tokens + elapsed * self.rate)


class APIRetryHandler:
    """
    Retry handler with exponential backoff.

    Retries on: network errors, HTTP 429 (rate limited), HTTP 5xx (server errors).
    Backoff: base_delay * 2^(attempt-1) capped at max_delay.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 2.0,
        max_delay: float = 8.0,
        retryable_statuses: Optional[set[int]] = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.retryable_statuses = retryable_statuses or {429, 500, 502, 503, 504}

    async def execute(
        self,
        func: Callable,
        *args,
        rate_limiter: Optional[TokenBucket] = None,
        **kwargs,
    ) -> RetryResult:
        """
        Execute an async function with rate limiting and retry logic.

        Args:
            func: Async callable to execute
            rate_limiter: TokenBucket to acquire token before each attempt
        """
        last_error = None
        total_delay = 0.0

        for attempt in range(1, self.max_retries + 1):
            # Acquire rate limit token before each attempt
            if rate_limiter:
                await rate_limiter.acquire()

            try:
                result = await func(*args, **kwargs)
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempt,
                    total_delay=total_delay,
                )
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check if retryable
                is_retryable = self._is_retryable(e, error_str)

                if attempt < self.max_retries and is_retryable:
                    delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
                    total_delay += delay
                    logger.warning(
                        f"API call failed (attempt {attempt}/{self.max_retries}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"API call failed after {attempt} attempt(s): {e}"
                    )
                    break

        return RetryResult(
            success=False,
            error=str(last_error) if last_error else "Unknown error",
            attempts=self.max_retries,
            total_delay=total_delay,
        )

    def _is_retryable(self, exception: Exception, error_str: str) -> bool:
        """Determine if an exception is retryable."""
        # HTTP status codes
        if hasattr(exception, "status") and exception.status in self.retryable_statuses:
            return True
        if hasattr(exception, "code") and exception.code in self.retryable_statuses:
            return True

        # Network errors
        network_keywords = [
            "connection refused",
            "connection reset",
            "timeout",
            "timed out",
            "network unreachable",
            "failed to establish",
            "server disconnected",
        ]
        for kw in network_keywords:
            if kw in error_str:
                return True

        # Rate limit keywords
        rate_limit_keywords = ["429", "rate limit", "too many requests", "throttl"]
        for kw in rate_limit_keywords:
            if kw in error_str:
                return True

        # Server error keywords
        server_error_keywords = ["500", "502", "503", "504", "internal server error", "bad gateway", "service unavailable"]
        for kw in server_error_keywords:
            if kw in error_str:
                return True

        return False


class RateLimitManager:
    """
    Manages separate TokenBucket rate limiters per broker.

    Provides a unified interface for rate-limited API calls with retry.
    """

    def __init__(
        self,
        fyers_config: Optional[RateLimitConfig] = None,
        kotak_config: Optional[RateLimitConfig] = None,
    ):
        self.fyers_config = fyers_config or RateLimitConfig(
            max_rate=10.0, max_retries=3, base_delay=2.0, max_delay=8.0
        )
        self.kotak_config = kotak_config or RateLimitConfig(
            max_rate=5.0, max_retries=3, base_delay=2.0, max_delay=8.0
        )

        self._buckets: dict[Broker, TokenBucket] = {
            Broker.FYERS: TokenBucket(rate=self.fyers_config.max_rate),
            Broker.KOTAK: TokenBucket(rate=self.kotak_config.max_rate),
        }
        self._retry_handlers: dict[Broker, APIRetryHandler] = {
            Broker.FYERS: APIRetryHandler(
                max_retries=self.fyers_config.max_retries,
                base_delay=self.fyers_config.base_delay,
                max_delay=self.fyers_config.max_delay,
            ),
            Broker.KOTAK: APIRetryHandler(
                max_retries=self.kotak_config.max_retries,
                base_delay=self.kotak_config.base_delay,
                max_delay=self.kotak_config.max_delay,
            ),
        }

    def get_bucket(self, broker: Broker) -> TokenBucket:
        return self._buckets[broker]

    def get_retry_handler(self, broker: Broker) -> APIRetryHandler:
        return self._retry_handlers[broker]

    async def execute_with_broker_limit(
        self,
        broker: Broker,
        func: Callable,
        *args,
        **kwargs,
    ) -> RetryResult:
        """Execute a function with broker-specific rate limiting and retry."""
        bucket = self.get_bucket(broker)
        handler = self.get_retry_handler(broker)
        return await handler.execute(func, *args, rate_limiter=bucket, **kwargs)

    def get_stats(self) -> dict:
        """Return current rate limiter stats."""
        return {
            broker.value: {
                "available_tokens": round(bucket.get_available_tokens(), 2),
                "rate": bucket.rate,
                "capacity": bucket.capacity,
            }
            for broker, bucket in self._buckets.items()
        }


# Global singleton instance
rate_limit_manager = RateLimitManager()
