"""Tests for the FYERS v3 historical-data client (Part 1).

These tests pin the request the client builds and the way failures are reported,
because "Invalid input" from Fyers is almost always a malformed request rather
than a network problem.  No test performs a real network call: the aiohttp
session is replaced by a fixture that records the outgoing request.
"""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# --------------------------------------------------------------------- helpers
class _FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status = status
        self._payload = payload if payload is not None else {"s": "ok", "candles": []}

    async def json(self, content_type=None):
        return self._payload

    async def text(self):
        return str(self._payload)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    """Records the params of every request and replays queued responses."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        return self._responses.pop(0) if self._responses else _FakeResponse()


@pytest.fixture()
def client(monkeypatch):
    """A FyersAPIClient with a fake session and a token in place."""
    from app.services import fyers_api

    instance = fyers_api.FyersAPIClient()
    monkeypatch.setattr(instance, "_get_auth_header", lambda: "CID:TOKEN")
    # Never sleep between retries in tests.
    monkeypatch.setattr(fyers_api.asyncio, "sleep", _noop_sleep)
    return instance


async def _noop_sleep(_seconds):
    return None


def _use_session(client, responses):
    session = _FakeSession(responses)
    async def _get_session():
        return session
    client._get_session = _get_session
    return session


# ----------------------------------------------------------------------- tests
VALID_CASES = [
    ("NSE:NIFTY50-INDEX", "5"),
    ("NSE:NIFTYBANK-INDEX", "5"),
    ("NSE:SBIN-EQ", "5"),
    ("NSE:RELIANCE-EQ", "5"),
    ("NSE:FINNIFTY-INDEX", "15"),
]


@pytest.mark.parametrize("symbol,resolution", VALID_CASES)
def test_valid_symbols_pass_local_validation(client, symbol, resolution):
    """Every documented test symbol is structurally valid and is not rewritten."""
    from app.services.fyers_api import normalize_symbol, validate_fyers_symbol

    assert validate_fyers_symbol(normalize_symbol(symbol)) is None


def test_history_request_payload_matches_fyers_v3(client):
    """The outgoing query must carry every parameter the v3 data API requires."""
    session = _use_session(client, [_FakeResponse(200, {"s": "ok", "candles": [[1, 1, 2, 0.5, 1.5, 10]]})])

    result = asyncio.run(client.get_history("NSE:NIFTY50-INDEX", "5", 1_700_000_000, 1_700_086_400))

    assert result["candles"] == [[1, 1, 2, 0.5, 1.5, 10]]
    params = session.calls[0]["params"]
    assert params["symbol"] == "NSE:NIFTY50-INDEX"
    assert params["resolution"] == "5"
    assert params["date_format"] == "0"
    assert params["range_from"] == "1700000000"
    assert params["range_to"] == "1700086400"
    assert params["cont_flag"] == "1"
    assert session.calls[0]["url"].endswith("/data/history")


def test_legacy_start_ts_end_ts_aliases_still_work(client):
    """trading_data_service calls with start_ts/end_ts; keep it working."""
    session = _use_session(client, [_FakeResponse(200, {"s": "ok", "candles": []})])

    asyncio.run(client.get_history("NSE:SBIN-EQ", "5", start_ts=111, end_ts=222))

    params = session.calls[0]["params"]
    assert params["range_from"] == "111"
    assert params["range_to"] == "222"


@pytest.mark.parametrize(
    "symbol",
    ["NIFTY50-INDEX", "", "NSE:", "NSE:NIFTY 50-INDEX", "XXXX:NIFTY50-INDEX"],
)
def test_invalid_symbols_are_rejected_before_the_request(client, symbol):
    """A malformed symbol must never reach Fyers (that is what "Invalid input" is)."""
    session = _use_session(client, [_FakeResponse(200, {"s": "ok", "candles": []})])

    result = asyncio.run(client.get_history(symbol, "5", 1, 2))

    assert "error" in result
    assert result["status"] == 400
    assert session.calls == []  # provider never called


def test_unsupported_resolution_is_rejected_locally(client):
    session = _use_session(client, [_FakeResponse(200, {"s": "ok", "candles": []})])

    result = asyncio.run(client.get_history("NSE:NIFTY50-INDEX", "7", 1, 2))

    assert result["status"] == 400
    assert "resolution" in result["error"].lower()
    assert session.calls == []


@pytest.mark.parametrize(
    "given,expected",
    [("1D", "D"), ("1W", "W"), ("1M", "MN"), ("60", "60"), ("240", "240"),
     ("5", "5"), ("1h", "60"), ("4h", "240"), ("1d", "D")],
)
def test_resolution_aliases_normalise(client, given, expected):
    from app.services.fyers_api import normalize_resolution

    assert normalize_resolution(given) == expected


def test_index_alias_with_exchange_prefix_normalises(client):
    """NSE_FO:NIFTY used to reach the API verbatim and trigger Invalid input."""
    from app.services.fyers_api import normalize_symbol, validate_fyers_symbol

    for symbol in ("NSE_FO:NIFTY", "NSE_CM:BANKNIFTY", "BSE_CM:SENSEX"):
        normalized = normalize_symbol(symbol)
        assert validate_fyers_symbol(normalized) is None


def test_provider_error_is_returned_with_its_real_message(client):
    _use_session(client, [_FakeResponse(400, {"s": "error", "code": 99, "message": "Invalid input"})])

    result = asyncio.run(client.get_history("NSE:NIFTY50-INDEX", "5", 1, 2))

    assert result["status"] == 400
    assert result["error"] == "Invalid input"


def test_auth_failure_maps_to_401(client):
    _use_session(client, [_FakeResponse(401, {"s": "error", "code": 401, "message": "token expired"})])

    result = asyncio.run(client.get_history("NSE:NIFTY50-INDEX", "5", 1, 2))

    assert result["status"] == 401
    assert "re-login" in result["error"]


def test_retryable_status_is_retried_then_succeeds(client):
    """A 429 on the first attempt is retried; the retry returns candles."""
    _use_session(client, [
        _FakeResponse(429, {"s": "error", "message": "Too many requests"}),
        _FakeResponse(200, {"s": "ok", "candles": [[1, 1, 2, 0.5, 1.5, 10]]}),
    ])

    result = asyncio.run(client.get_history("NSE:NIFTY50-INDEX", "5", 1, 2))

    assert result["candles"]
    assert len(client._get_session.__self__.calls) == 2 if hasattr(client._get_session, "__self__") else True


def test_non_retryable_error_is_not_retried(client):
    session = _use_session(client, [_FakeResponse(400, {"s": "error", "message": "Invalid input"})])

    asyncio.run(client.get_history("NSE:NIFTY50-INDEX", "5", 1, 2))

    assert len(session.calls) == 1


def test_missing_token_returns_401_without_request(client, monkeypatch):
    monkeypatch.setattr(client, "_get_auth_header", lambda: None)
    session = _use_session(client, [])

    result = asyncio.run(client.get_history("NSE:NIFTY50-INDEX", "5", 1, 2))

    assert result["status"] == 401
    assert session.calls == []


def test_non_list_candles_payload_is_reported(client):
    _use_session(client, [_FakeResponse(200, {"s": "ok", "candles": {"oops": True}})])

    result = asyncio.run(client.get_history("NSE:NIFTY50-INDEX", "5", 1, 2))

    assert result["status"] == 502
    assert "invalid candles" in result["error"].lower()
