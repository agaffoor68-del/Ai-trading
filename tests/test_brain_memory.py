"""Memory, news and freshness tests.

News is fed from a local XML fixture through ``_store``/``_extract_items`` so
no network call is made and nothing is presented as a real headline.
"""

from __future__ import annotations

import asyncio

import pytest

from app.core import market_time as mt
from app.core.brain_models import MemoryEntry, NewsItem
from app.core.database import SessionLocal
from app.services.brain.memory_service import search_memory, similar_situations, write_memory
from app.services.brain.news_service import (
    NewsIntelligence,
    classify,
    content_hash,
    sanitize,
)

RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Fixture</title>
<item><title>RBI holds repo rate at 6.5 percent</title>
<link>https://example.org/rbi</link><pubDate>{recent}</pubDate>
<description><![CDATA[<p>Policy statement</p>]]></description></item>
<item><title>Nifty ends higher as banks rally</title>
<link>https://example.org/nifty</link><pubDate>{recent2}</pubDate>
<description>Market wrap</description></item>
<item><title>No link item</title><description>ignored</description></item>
</channel></rss>
"""


def rss_fixture() -> str:
    """Feed XML with timestamps relative to now (the runner clock may be ahead)."""
    from datetime import timedelta

    now = mt.ist_now()
    fmt = "%a, %d %b %Y %H:%M:%S +0000"
    return RSS_FIXTURE.format(
        recent=(now - timedelta(hours=2)).strftime(fmt),
        recent2=(now - timedelta(hours=1)).strftime(fmt),
    )


# ------------------------------------------------------------------- freshness
def test_parse_timestamp_variants():
    assert mt.parse_timestamp(1_700_000_000) is not None
    assert mt.parse_timestamp("1700000000") is not None
    assert mt.parse_timestamp("2026-02-02T09:00:00+05:30") is not None
    assert mt.parse_timestamp("not-a-date") is None
    assert mt.parse_timestamp(None) is None


def test_age_and_freshness():
    now = mt.ist_now()
    fresh = now.isoformat()
    old = (now - mt.timedelta(minutes=5)).isoformat() if hasattr(mt, "timedelta") else None
    assert mt.is_fresh(fresh, 90) is True
    assert mt.age_seconds(fresh) is not None and mt.age_seconds(fresh) < 5
    from datetime import timedelta as _td

    stale = (now - _td(minutes=5)).isoformat()
    assert mt.is_fresh(stale, 90) is False
    assert mt.is_fresh(None, 90) is False


def test_bar_is_closed_respects_interval():
    from datetime import timedelta as _td

    now = mt.ist_now()
    open_bar = now.isoformat()
    closed_bar = (now - _td(minutes=10)).isoformat()
    assert mt.bar_is_closed(closed_bar, "5m") is True
    assert mt.bar_is_closed(open_bar, "5m") is False


# ---------------------------------------------------------------------- news
def test_sanitize_strips_control_characters():
    dirty = "Head\x00line\x07 with  spaces"
    clean = sanitize(dirty, 100)
    assert "\x00" not in clean and "\x07" not in clean
    assert "Head line" in clean


def test_classify_instruments_and_sentiment():
    meta = classify("RBI holds repo rate, bank nifty rallies", "")
    assert "BANKNIFTY" in meta["instruments"]
    assert meta["sentiment"] == "positive"
    bearish = classify("Company plunges after fraud probe", "")
    assert bearish["sentiment"] == "negative"
    assert bearish["impact"] == "high"


def test_classify_does_not_invent_instruments():
    """No keyword match must leave instruments empty rather than guessed."""
    meta = classify("RBI holds repo rate at 6.5 percent", "")
    assert meta["instruments"] == []
    assert meta["sectors"], "the banking sector keyword should still match"


def test_extract_items_from_fixture():
    items = NewsIntelligence._extract_items(rss_fixture(), 10) if hasattr(
        NewsIntelligence, "_extract_items"
    ) else None
    if items is None:
        from app.services.brain.news_service import _extract_items

        items = _extract_items(rss_fixture(), 10)
    headlines = [i["headline"] for i in items]
    assert any("repo rate" in h for h in headlines)
    assert any("Nifty ends higher" in h for h in headlines)


def test_store_dedupes_and_classifies(clean_db, user_id):
    from app.services.brain.news_service import _extract_items

    service = NewsIntelligence()
    items = _extract_items(rss_fixture(), 10)
    for item in items:
        item["source"] = "FixtureWire"
        item["region"] = "india"
        item["reliability"] = "secondary"
    stored, dupes, failed = service._store(items, user_id)
    assert stored >= 2
    assert dupes == 0
    assert failed == 0
    again, dupes2, failed2 = service._store(items, user_id)
    assert again == 0
    assert dupes2 == stored
    assert failed2 == 0


def test_content_hash_is_stable():
    a = content_hash("Same headline", "Source", "https://x/y")
    b = content_hash("same headline", "source", "https://x/y")
    c = content_hash("Different", "Source", None)
    assert a == b
    assert a != c


def test_recent_filters_by_region_and_instrument(clean_db, user_id):
    from app.services.brain.news_service import _extract_items

    service = NewsIntelligence()
    items = _extract_items(rss_fixture(), 10)
    for item in items:
        item["source"] = "FixtureWire"
        item["region"] = "india"
        item["reliability"] = "secondary"
    service._store(items, user_id)
    india = service.recent(regions=["india"], hours=48, limit=10)
    assert india, "stored fixture news must be retrievable"
    assert all(row["region"] == "india" for row in india)
    assert service.recent(regions=["global"], hours=48, limit=10) == []


def test_impact_summary_reports_no_news_honestly(clean_db):
    summary = NewsIntelligence().market_impact_summary(["NIFTY"], hours=1)
    assert summary["items"] == 0
    assert summary["sentiment"] == "unknown"


# -------------------------------------------------------------------- memory
def test_write_and_search_memory(clean_db, user_id):
    write_memory(
        memory_type="losing_trade",
        title="LOSS NIFTY 100->95 (stop_loss)",
        content="Stop loss placement was too tight; ATR multiple 1.5 failed in volatile regime.",
        user_id=user_id,
        symbol="NIFTY",
        outcome="LOSS",
        pnl=-50.0,
        tags=["loss", "stop_loss"],
    )
    write_memory(
        memory_type="winning_trade",
        title="WIN BANKNIFTY 200->230 (target)",
        content="Trend continuation with RSI confirmation worked well.",
        user_id=user_id,
        symbol="BANKNIFTY",
        outcome="WIN",
        pnl=300.0,
        tags=["win", "target"],
    )
    hits = asyncio.run(search_memory("stop loss placement volatile", user_id=user_id, limit=5))
    assert hits, "relevant memory must be retrieved"
    assert "stop loss" in hits[0]["content"].lower()


def test_similar_situations_counts_outcomes(clean_db, user_id):
    write_memory(
        memory_type="winning_trade",
        title="WIN NIFTY trend_up",
        content="Trend up with volume confirmation.",
        user_id=user_id,
        symbol="NIFTY",
        outcome="WIN",
        tags=["win"],
    )
    result = asyncio.run(similar_situations("NIFTY", "trend_up", user_id=user_id))
    assert result["summary"]["matches"] >= 1
    assert result["summary"]["wins"] >= 1


def test_unknown_memory_type_is_refused(clean_db):
    assert write_memory(memory_type="not_a_type", title="t", content="c") is None
