"""Structured error logging for every subsystem the platform depends on.

The goal is that a failure in production can be diagnosed from the log alone:
each record carries a timestamp, the endpoint it happened on, a stable error
category, the provider's *actual* message and the request context needed to
reproduce it.

Hard rule: secrets never reach the log.  Access tokens, client secrets,
passwords, JWTs and Authorization headers are redacted before a record is
emitted, and request bodies are not logged at all — only the parameters that
identify the call (symbol, resolution, date range, status code).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from app.core.datetime_utils import now_ist

logger = logging.getLogger("app.errors")


class ErrorCategory(str, Enum):
    """Stable machine-readable categories used by the dashboard and alerts."""

    FYERS_AUTH = "fyers_auth"
    FYERS_SYMBOL = "fyers_symbol"
    FYERS_HISTORY = "fyers_history"
    FYERS_QUOTES = "fyers_quotes"
    FYERS_RATE_LIMIT = "fyers_rate_limit"
    MARKET_DATA = "market_data"
    INDICATOR = "indicator"
    STRATEGY = "strategy"
    DATABASE = "database"
    AUTH = "auth"
    EXTERNAL_API = "external_api"
    UNKNOWN = "unknown"


# Substrings that identify a value which must never be written to a log.
_SECRET_KEYS = re.compile(
    r"(access_token|refresh_token|client_secret|secret|password|passwd|jwt|"
    r"authorization|api_key|apikey|token|encryption_key|private_key)",
    re.IGNORECASE,
)

_REDACTED = "[redacted]"


def _redact_key(key: str) -> bool:
    return bool(_SECRET_KEYS.search(str(key)))


def redact(value: Any, depth: int = 0) -> Any:
    """Recursively replace secret-looking values with ``[redacted]``.

    ``Authorization`` headers such as ``"clientid:token"`` are redacted whole,
    so a token can never be reconstructed from a log line.
    """
    if depth > 6:
        return "[truncated]"
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, item in value.items():
            if _redact_key(key):
                out[str(key)] = _REDACTED
            else:
                out[str(key)] = redact(item, depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [redact(item, depth + 1) for item in value[:50]]
    if isinstance(value, str):
        # "Authorization: <clientid>:<token>" and bare long tokens.
        if ":" in value and len(value) < 200 and _SECRET_KEYS.search(value.split(":", 1)[0] or ""):
            return _REDACTED
        return value
    return value


@dataclass
class ErrorRecord:
    """One structured failure record."""

    category: ErrorCategory
    message: str
    endpoint: Optional[str] = None
    timestamp: str = field(default_factory=lambda: now_ist().isoformat())
    context: Dict[str, Any] = field(default_factory=dict)
    status_code: Optional[int] = None
    exception: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "category": self.category.value,
            "endpoint": self.endpoint,
            "status_code": self.status_code,
            "message": self.message,
            "exception": self.exception,
            "context": redact(self.context),
        }

    def to_log_line(self) -> str:
        payload = self.to_dict()
        return (
            f"[{payload['category']}] {payload['message']} "
            f"endpoint={payload['endpoint']} status={payload['status_code']} "
            f"context={json.dumps(payload['context'], default=str)}"
        )


def log_error(
    category: ErrorCategory,
    message: str,
    *,
    endpoint: Optional[str] = None,
    status_code: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None,
    exc: Optional[BaseException] = None,
) -> ErrorRecord:
    """Emit one structured error record and return it.

    The record is logged at ERROR level with the provider's real message; the
    caller decides whether the failure is also surfaced to the API client.
    """
    record = ErrorRecord(
        category=category,
        message=str(message),
        endpoint=endpoint,
        status_code=status_code,
        context=context or {},
        exception=f"{type(exc).__name__}: {exc}" if exc is not None else None,
    )
    logger.error(record.to_log_line())
    return record


def classify_fyers_message(message: str) -> ErrorCategory:
    """Map a provider message onto a category so dashboards can group errors."""
    text = (message or "").lower()
    if any(word in text for word in ("token", "auth", "expired", "login", "unauthenticated")):
        return ErrorCategory.FYERS_AUTH
    if any(word in text for word in ("invalid input", "symbol", "instrument")):
        return ErrorCategory.FYERS_SYMBOL
    if "rate" in text or "limit" in text or "too many" in text:
        return ErrorCategory.FYERS_RATE_LIMIT
    if "history" in text or "candle" in text or "resolution" in text:
        return ErrorCategory.FYERS_HISTORY
    return ErrorCategory.EXTERNAL_API


__all__ = [
    "ErrorCategory",
    "ErrorRecord",
    "classify_fyers_message",
    "log_error",
    "redact",
]
