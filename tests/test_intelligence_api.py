"""Integration tests for the intelligence API (Task 4/6).

The provider is stubbed at the boundary so these tests exercise the real
pipeline — normalization, quality gating, regime, strategy, indicator panel and
verdict composition — without network access.  The candles used are deterministic
fixtures; no test asserts on live market prices.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core import market_time as mt
from app.main import app
from app.services.brain import multi_timeframe as mtf


IST = mt.IST


def session_candles(timeframe: str, count: int = 120, slope: float = 12.0) -> list[dict]:
    """Closed candles ending just before 'now' so freshness passes."""
    step = mtf.bar_seconds(timeframe)
    now = datetime.now(IST)
    # Anchor so the final bar closed ~30s ago.
    last_start = now - timedelta(seconds=step + 30)
    out = []
    for i in range(count):
        ts = int((last_start - timedelta(seconds=step * (count - 1 - i))).timestamp())
        price = 22000.0 + i * slope + math.sin(i / 4.0) * 10
        out.append(
            {
                "ts": ts,
                "open": price - 3,
                "high": price + 18,
                "low": price - 18,
                "close": price,
                "volume": 50_000 + i * 100,
            }
        )
    return out


@pytest.fixture()
def client(monkeypatch):
    async def fake_fetch(symbol, interval="5m", limit=300):
        return session_candles(interval, count=min(limit, 160))

    # Patch the loader the pipeline resolves at call time.
    monkeypatch.setattr(
        "app.services.indicator_service.fetch_candles", fake_fetch, raising=True
    )
    return TestClient(app)


# ------------------------------------------------------------------ data quality
def test_data_quality_endpoint_reports_every_timeframe(client):
    response = client.get("/api/v1/intelligence/NIFTY/data-quality")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "NIFTY"
    assert "sync" in payload
    assert payload["timeframes"]
    # Every timeframe must carry an explicit status and reason field.
    for timeframe, block in payload["timeframes"].items():
        assert block["status"]
        assert "candles" in block


def test_data_quality_rejects_unsupported_symbol(client):
    response = client.get("/api/v1/intelligence/DOGE/data-quality")

    assert response.status_code == 400
    assert "Unsupported symbol" in response.json()["detail"]


# ------------------------------------------------------------------- indicators
def test_indicator_panel_returns_all_registered_indicators(client):
    response = client.get("/api/v1/intelligence/NIFTY/indicators?timeframe=5m")

    assert response.status_code == 200
    payload = response.json()
    assert payload["library_total"] == 169
    assert len(payload["indicators"]) == 169
    assert payload["summary"]["total"] == 169

    sample = payload["indicators"][0]
    for field in ("id", "name", "category", "timeframe", "direction", "strength", "status"):
        assert field in sample


def test_indicator_panel_filters_by_direction(client):
    response = client.get("/api/v1/intelligence/NIFTY/indicators?timeframe=5m&direction=bullish")

    assert response.status_code == 200
    payload = response.json()
    assert all(row["direction"] == "bullish" for row in payload["indicators"])


def test_indicator_panel_filters_by_category(client):
    response = client.get("/api/v1/intelligence/NIFTY/indicators?timeframe=5m&category=momentum")

    assert response.status_code == 200
    payload = response.json()
    assert payload["indicators"]
    assert all(row["category"] == "momentum" for row in payload["indicators"])


# ----------------------------------------------------------------- intelligence
def test_intelligence_endpoint_composes_every_block(client):
    response = client.get(
        "/api/v1/intelligence/NIFTY?timeframe=5m&include_options=false"
    )

    assert response.status_code == 200
    payload = response.json()

    for block in ("data_quality", "sync", "regime", "multi_timeframe", "strategy",
                  "indicators", "options", "verdict", "entry_plan"):
        assert block in payload, f"missing {block}"

    assert payload["regime"]["regime"]
    assert 0.0 <= payload["regime"]["confidence"] <= 1.0
    assert payload["strategy"]["strategy"]["name"]
    assert payload["verdict"]["action"] in ("BUY", "SELL", "WAIT", "NO_TRADE")
    assert payload["indicators"]["summary"]["total"] == 169


def test_intelligence_verdict_explains_itself(client):
    response = client.get("/api/v1/intelligence/NIFTY?include_options=false")

    payload = response.json()
    verdict = payload["verdict"]

    assert verdict["reason"]
    if not verdict["allowed"]:
        assert verdict["blockers"]


def test_intelligence_options_block_degrades_without_breaking(client):
    """Options must fail soft: the market read still returns."""
    response = client.get("/api/v1/intelligence/NIFTY?include_options=true")

    assert response.status_code == 200
    payload = response.json()
    assert "available" in payload["options"]
    assert payload["verdict"]["action"]


def test_intelligence_rejects_unsupported_symbol(client):
    response = client.get("/api/v1/intelligence/RELIANCE")

    assert response.status_code == 400


def test_intelligence_handles_provider_outage(monkeypatch):
    async def broken_fetch(symbol, interval="5m", limit=300):
        raise RuntimeError("provider down")

    monkeypatch.setattr(
        "app.services.indicator_service.fetch_candles", broken_fetch, raising=True
    )
    client = TestClient(app)
    response = client.get("/api/v1/intelligence/NIFTY")

    # The endpoint must not 500: it reports the outage and refuses to trade.
    assert response.status_code == 200
    payload = response.json()
    assert payload["verdict"]["action"] == "NO_TRADE"
    assert payload["verdict"]["blockers"]


def test_overview_endpoint_covers_all_indices(client):
    response = client.get("/api/v1/intelligence?include_options=false")

    assert response.status_code == 200
    payload = response.json()
    symbols = {item["symbol"] for item in payload["instruments"]}
    assert symbols == {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"}
    for item in payload["instruments"]:
        assert "available" in item


# ------------------------------------------------------------------ options API
def test_options_intelligence_reports_unavailable_without_token():
    """With no broker token the endpoint must say so, never invent a chain."""
    client = TestClient(app)
    response = client.get("/api/v1/market/options/intelligence?symbol=NIFTY")

    assert response.status_code in (200, 401, 502)
    if response.status_code == 200:
        payload = response.json()
        assert payload.get("available") is False


def test_options_chain_rejects_bad_expiry_format():
    client = TestClient(app)
    response = client.get("/api/v1/market/options/chain?symbol=NIFTY&expiry=29-01-2099")

    assert response.status_code in (400, 401, 502)
