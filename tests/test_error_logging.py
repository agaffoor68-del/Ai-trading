"""Tests for error classification and secret redaction (Part 7).

The rule under test is simple: a log line must be diagnosable *and* must never
contain a credential.  Both properties are asserted directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.error_log import (  # noqa: E402
    ErrorCategory,
    classify_fyers_message,
    log_error,
    redact,
)


def test_record_has_every_required_field():
    record = log_error(
        ErrorCategory.FYERS_HISTORY,
        "boom",
        endpoint="/data/history",
        status_code=502,
        context={"symbol": "NSE:NIFTY50-INDEX"},
    ).to_dict()

    for field in ("timestamp", "endpoint", "category", "message", "context"):
        assert field in record
    assert record["category"] == "fyers_history"
    assert record["status_code"] == 502


def test_access_token_is_never_logged():
    line = log_error(
        ErrorCategory.FYERS_AUTH,
        "nope",
        context={"access_token": "super-secret-value", "symbol": "NSE:SBIN-EQ"},
    ).to_log_line()

    assert "super-secret-value" not in line
    assert "[redacted]" in line
    # Non-secret context survives.
    assert "NSE:SBIN-EQ" in line


def test_nested_secrets_are_redacted():
    redacted = redact(
        {
            "outer": {
                "client_secret": "shh",
                "client_id": "CID123",
                "deep": {"password": "hunter2"},
            }
        }
    )
    flat = str(redacted)
    assert "shh" not in flat
    assert "hunter2" not in flat
    assert redacted["outer"]["client_id"] == "CID123"


def test_authorization_header_value_is_redacted():
    assert redact({"Authorization": "CID:abcdef123456"})["Authorization"] == "[redacted]"


def test_exception_type_and_message_are_captured():
    record = log_error(
        ErrorCategory.DATABASE,
        "insert failed",
        exc=ValueError("duplicate key"),
    )
    assert record.exception == "ValueError: duplicate key"


def test_provider_message_classification():
    assert classify_fyers_message("Invalid input") is ErrorCategory.FYERS_SYMBOL
    assert classify_fyers_message("token expired") is ErrorCategory.FYERS_AUTH
    assert classify_fyers_message("Too many requests") is ErrorCategory.FYERS_RATE_LIMIT
    assert classify_fyers_message("Invalid resolution") is ErrorCategory.FYERS_HISTORY


def test_fyers_history_failure_is_logged_with_context(monkeypatch):
    """A provider rejection must produce a record carrying the real message."""
    import asyncio

    from app.services import fyers_api

    class _Resp:
        status = 400

        async def json(self, content_type=None):
            return {"s": "error", "code": 99, "message": "Invalid input"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    class _Session:
        def get(self, *args, **kwargs):
            return _Resp()

    client = fyers_api.FyersAPIClient()
    client._get_auth_header = lambda: "CID:TOKEN"

    async def _get_session():
        return _Session()

    client._get_session = _get_session

    records = []
    monkeypatch.setattr(
        "app.services.fyers_api.log_error",
        lambda *args, **kwargs: records.append((args, kwargs)) or None,
    )

    result = asyncio.run(client.get_history("NSE:NIFTY50-INDEX", "5", 1, 2))

    assert result["error"] == "Invalid input"
    assert records, "the failure must be logged"
    args, kwargs = records[0]
    assert args[0] is ErrorCategory.FYERS_SYMBOL
    assert kwargs["status_code"] == 400
    assert kwargs["context"]["symbol"] == "NSE:NIFTY50-INDEX"
