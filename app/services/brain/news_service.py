"""Global + India financial news intelligence (Part 7).

Design notes:

* **Untrusted content.**  Headlines and article text come from the internet.  The
  moment they enter the platform they are wrapped as data: every prompt that
  includes news labels it untrusted and the decision engine's system prompt
  forbids news from changing risk limits or permissions.  This module also
  strips control characters and caps stored excerpt length.
* **No invented news.**  Items are only stored when they came from a real fetch
  that returned a headline, a source and a URL.  A failed fetch stores nothing
  and is reported in ``errors``; nothing is generated locally.
* **Provenance.**  ``content_hash`` dedupes; ``published_at``/``event_at`` are
  parsed when the provider supplies them and left ``None`` otherwise (never
  guessed).
* **Confirmation.**  ``confirmation`` is ``single_source`` until the same event
  is reported by a second, independent source; only then ``multi_source``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import insert

from app.core import market_time as mt
from app.core.brain_models import NewsItem
from app.core.database import SessionLocal
from app.core.datetime_utils import naive_as_ist, now_ist

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

MAX_EXCERPT_CHARS = 600
MAX_HEADLINE_CHARS = 400

# --------------------------------------------------------------------- sources
# Each provider is a list of public RSS/Atom feeds.  ``region`` drives the
# India/Global split; ``sector``/``instruments`` are inferred from keywords.
NEWS_SOURCES: Tuple[Dict[str, Any], ...] = (
    # ------------------------------------------------------------------ India
    {"name": "RBI", "region": "india", "url": "https://www.rbi.org.in/pressrelease/rss/pressreleases.xml",
     "reliability": "primary", "sectors": ["banking", "macro"]},
    {"name": "NSE", "region": "india", "url": "https://www.nseindia.com/rss/corporate-announcements.xml",
     "reliability": "primary", "sectors": ["corporate"]},
    {"name": "BSE", "region": "india", "url": "https://www.bseindia.com/rss/corporate-announcements.xml",
     "reliability": "primary", "sectors": ["corporate"]},
    {"name": "SEBI", "region": "india", "url": "https://www.sebi.gov.in/rss/sebispeeches.xml",
     "reliability": "primary", "sectors": ["regulation"]},
    {"name": "Economic Times Markets", "region": "india",
     "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
     "reliability": "secondary", "sectors": ["markets"]},
    {"name": "Moneycontrol", "region": "india",
     "url": "https://www.moneycontrol.com/rss/business.xml",
     "reliability": "secondary", "sectors": ["markets"]},
    {"name": "Business Standard", "region": "india",
     "url": "https://www.business-standard.com/rss/markets-1.xml",
     "reliability": "secondary", "sectors": ["markets"]},
    {"name": "PIB", "region": "india", "url": "https://pib.gov.in/RssMainPage.aspx?lang=1",
     "reliability": "primary", "sectors": ["policy"]},
    # ----------------------------------------------------------------- Global
    {"name": "Federal Reserve", "region": "global",
     "url": "https://www.federalreserve.gov/feeds/press_all.xml",
     "reliability": "primary", "sectors": ["central_bank", "macro"]},
    {"name": "Reuters Markets", "region": "global",
     "url": "https://www.reutersagency.com/feed/?best-topics=markets",
     "reliability": "secondary", "sectors": ["markets"]},
    {"name": "CNBC", "region": "global", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
     "reliability": "secondary", "sectors": ["markets"]},
    {"name": "Market Watch", "region": "global",
     "url": "http://feeds.marketwatch.com/marketwatch/topstories/",
     "reliability": "secondary", "sectors": ["markets"]},
    {"name": "Investing.com", "region": "global",
     "url": "https://www.investing.com/rss/news_1.rss",
     "reliability": "secondary", "sectors": ["markets"]},
    {"name": "ECB", "region": "global", "url": "https://www.ecb.europa.eu/rss/press.html",
     "reliability": "primary", "sectors": ["central_bank"]},
)

# Keyword → instruments/sectors.  Deliberately conservative: no match means the
# item stays unclassified and therefore cannot trigger a trade on its own.
INSTRUMENT_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "NIFTY": ("nifty", "nifty 50", "nifty50"),
    "BANKNIFTY": ("bank nifty", "banknifty", "nifty bank"),
    "FINNIFTY": ("finnifty", "fin nifty"),
    "SENSEX": ("sensex",),
    "RELIANCE": ("reliance",),
    "HDFCBANK": ("hdfc bank",),
    "ICICIBANK": ("icici bank",),
    "INFY": ("infosys",),
    "TCS": ("tcs", "tata consultancy"),
    "SBIN": ("sbi", "state bank"),
    "BHARTIARTL": ("airtel",),
    "ITC": ("itc",),
    "TATAMOTORS": ("tata motors",),
    "GOLD": ("gold", "bullion", "mcx gold"),
    "SILVER": ("silver",),
    "CRUDE": ("crude", "brent", "wti", "oil price"),
    "USDINR": ("rupee", "usd/inr", "dollar-rupee"),
    "DXY": ("dollar index", "dxy"),
    "BTC": ("bitcoin", "btc"),
    "ETH": ("ethereum", "ether"),
}

SECTOR_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "banking": ("bank", "rbi", "repo", "npa", "credit growth"),
    "it": ("infosys", "tcs", "wipro", "hcl", "tech spending"),
    "pharma": ("pharma", "drug", "usfda"),
    "auto": ("auto", "car sales", "maruti", "tata motors"),
    "fmcg": ("fmcg", "hindustan unilever", "nestle", "britannia"),
    "energy": ("crude", "oil", "gas", "coal", "renewable"),
    "metals": ("steel", "copper", "aluminium", "metal"),
    "regulation": ("sebi", "regulation", "penalty", "ban"),
    "policy": ("budget", "gst", "policy", "government", "parliament"),
    "central_bank": ("fed", "federal reserve", "ecb", "boj", "pboc", "rate decision", "repo rate"),
    "macro": ("inflation", "cpi", "wpi", "gdp", "employment", "payroll", "pmi"),
    "geopolitics": ("war", "conflict", "sanction", "strike", "tariff"),
}

HIGH_IMPACT_KEYWORDS = (
    "rate hike", "rate cut", "repo rate", "crisis", "war", "conflict", "sanction",
    "default", "bankruptcy", "fraud", "sebi ban", "rbi action", "election",
    "tariff", "recession", "crash", "circuit", "slaughter", "attack",
)

SENTIMENT_POSITIVE = (
    "surge", "surges", "soar", "soars", "rally", "rallies", "rallied",
    "gain", "gains", "jump", "jumps", "beat", "beats", "record high",
    "upgrade", "upgraded", "profit rise", "growth", "approval", "win",
    "deal", "bonus", "split",
)
SENTIMENT_NEGATIVE = (
    "plunge", "plunges", "fall", "falls", "drop", "drops", "slump",
    "slumps", "loss", "losses", "miss", "misses", "downgrade",
    "downgraded", "cut", "cuts", "fraud", "probe", "penalty", "ban",
    "banned", "default", "bankruptcy", "weak",
)


# ------------------------------------------------------------------ utilities
@dataclass
class IngestReport:
    fetched: int = 0
    stored: int = 0
    duplicates: int = 0
    failed: int = 0
    sources_ok: List[str] = field(default_factory=list)
    errors: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fetched": self.fetched,
            "stored": self.stored,
            "duplicates": self.duplicates,
            "failed": self.failed,
            "sources_ok": self.sources_ok,
            "errors": self.errors,
        }


_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WS_RE = re.compile(r"\s+")


def sanitize(text: str, limit: int) -> str:
    """Strip control characters/normalise whitespace and cap length."""
    if not text:
        return ""
    cleaned = unicodedata.normalize("NFKC", str(text))
    cleaned = _CONTROL_RE.sub(" ", cleaned)
    cleaned = _WS_RE.sub(" ", cleaned).strip()
    return cleaned[:limit]


def content_hash(headline: str, source: str, url: Optional[str]) -> str:
    basis = f"{(headline or '').strip().lower()}|{(source or '').strip().lower()}"
    return hashlib.sha256(basis.encode("utf-8", "ignore")).hexdigest()


def _contains(text: str, keyword: str) -> bool:
    """Word-boundary match for single words, substring for phrases.

    Without this, short keywords match inside unrelated words (``ban`` in
    ``bank``, ``cut`` in ``cute``) and the sentiment would be wrong.
    """
    if " " in keyword or "-" in keyword or "/" in keyword:
        return keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def classify(headline: str, summary: str = "") -> Dict[str, Any]:
    """Keyword-based instruments/sectors/sentiment/impact.  Never a guess."""
    text = f"{headline} {summary}".lower()
    instruments = sorted(
        name for name, keys in INSTRUMENT_KEYWORDS.items() if any(_contains(text, k) for k in keys)
    )
    sectors = sorted(
        name for name, keys in SECTOR_KEYWORDS.items() if any(_contains(text, k) for k in keys)
    )
    positive = sum(1 for k in SENTIMENT_POSITIVE if _contains(text, k))
    negative = sum(1 for k in SENTIMENT_NEGATIVE if _contains(text, k))
    if positive > negative:
        sentiment, score = "positive", min(1.0, 0.5 + 0.1 * (positive - negative))
    elif negative > positive:
        sentiment, score = "negative", max(-1.0, -0.5 - 0.1 * (negative - positive))
    else:
        sentiment, score = "neutral", 0.0
    high = any(_contains(text, k) for k in HIGH_IMPACT_KEYWORDS)
    impact = "high" if high else ("medium" if (instruments or sectors) else "low")
    duration = "intraday" if impact == "high" else ("swing" if instruments else "long-term")
    return {
        "instruments": instruments,
        "sectors": sectors,
        "sentiment": sentiment,
        "sentiment_score": round(score, 3),
        "impact": impact,
        "impact_duration": duration,
    }


def _parse_rss_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=IST)
        return parsed.astimezone(IST)
    return mt.parse_timestamp(text)


def _strip_html(text: str) -> str:
    return sanitize(re.sub(r"<[^>]+>", " ", text or ""), MAX_EXCERPT_CHARS)


def _extract_items(xml_text: str, limit: int) -> List[Dict[str, Any]]:
    """Minimal RSS/Atom item extraction (no extra dependency).

    Returns dicts with ``headline``, ``summary``, ``url``, ``published_at``.
    Only real feed content is returned; an empty list means the feed was
    unusable and nothing will be stored.
    """
    items: List[Dict[str, Any]] = []
    for block in re.findall(r"<item\b[^>]*>(.*?)</item>", xml_text, re.S | re.I)[:limit]:
        items.append(_item_from_block(block))
    if not items:
        for block in re.findall(r"<entry\b[^>]*>(.*?)</entry>", xml_text, re.S | re.I)[:limit]:
            items.append(_item_from_block(block))
    return [i for i in items if i.get("headline")]


def _tag(block: str, *names: str) -> Optional[str]:
    for name in names:
        match = re.search(rf"<{name}\b[^>]*>(.*?)</{name}>", block, re.S | re.I)
        if match:
            value = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", match.group(1), flags=re.S)
            return _strip_html(value)
    return None


def _item_from_block(block: str) -> Dict[str, Any]:
    headline = _tag(block, "title")
    url = _tag(block, "link")
    if not url:
        href = re.search(r'<link\b[^>]*href="([^"]+)"', block, re.I)
        url = href.group(1) if href else None
    return {
        "headline": sanitize(headline or "", MAX_HEADLINE_CHARS),
        "summary": _tag(block, "description", "summary", "content:encoded") or "",
        "url": sanitize(url or "", 500) or None,
        "published_at": _parse_rss_date(_tag(block, "pubDate", "published", "updated", "dc:date")),
    }


# --------------------------------------------------------------------- service
class NewsIntelligence:
    """Fetches, classifies, dedupes and stores financial news."""

    def __init__(self, sources: Optional[Sequence[Dict[str, Any]]] = None) -> None:
        self.sources = list(sources or NEWS_SOURCES)

    async def ingest(
        self,
        regions: Optional[Sequence[str]] = None,
        user_id: Optional[int] = None,
        per_source: int = 15,
    ) -> Dict[str, Any]:
        """Fetch every configured feed and persist new items."""
        import asyncio

        import aiohttp

        wanted = {r.lower() for r in (regions or ["india", "global"])}
        report = IngestReport()
        timeout = aiohttp.ClientTimeout(total=20)
        headers = {
            "User-Agent": "AiTradingBrain/1.0 (+https://github.com/agaffoor68-del/Ai-trading)",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            tasks = {
                source["name"]: asyncio.create_task(
                    self._fetch(session, source, per_source), name=f"news-{source['name']}"
                )
                for source in self.sources
                if source["region"].lower() in wanted
            }
            for name, task in tasks.items():
                try:
                    items = await task
                except Exception as exc:
                    report.errors.append({"source": name, "error": str(exc)})
                    continue
                if items is None:
                    report.errors.append({"source": name, "error": "fetch failed or empty feed"})
                    continue
                report.sources_ok.append(name)
                report.fetched += len(items)
                stored, dupes, failed = self._store(items, user_id)
                report.stored += stored
                report.duplicates += dupes
                report.failed += failed
        if report.stored:
            self._promote_confirmations()
        return report.to_dict()

    async def _fetch(
        self, session, source: Dict[str, Any], limit: int
    ) -> Optional[List[Dict[str, Any]]]:
        try:
            async with session.get(source["url"]) as response:
                if response.status != 200:
                    logger.info("News source %s returned HTTP %s", source["name"], response.status)
                    return None
                body = await response.text(errors="ignore")
        except Exception as exc:
            logger.info("News source %s failed: %s", source["name"], exc)
            return None
        items = _extract_items(body, limit)
        for item in items:
            item["source"] = source["name"]
            item["region"] = source["region"]
            item["reliability"] = source.get("reliability", "secondary")
        return items

    def _store(
        self, items: Iterable[Dict[str, Any]], user_id: Optional[int]
    ) -> Tuple[int, int, int]:
        stored = 0
        duplicates = 0
        failed = 0
        if not items:
            return stored, duplicates, failed
        with SessionLocal() as db:
            # Determine dialect for upsert compatibility
            dialect_name = "sqlite"
            try:
                dialect_name = db.get_bind().engine.dialect.name
            except Exception:
                pass
            try:
                for item in items:
                    headline = item.get("headline") or ""
                    if not headline:
                        continue
                    if item.get("url") is None:
                        continue
                    digest = content_hash(headline, item.get("source") or "", item.get("url"))
                    exists = db.query(NewsItem).filter(NewsItem.content_hash == digest).first()
                    if exists is not None:
                        duplicates += 1
                        continue
                    meta = classify(headline, item.get("summary") or "")
                    stmt = insert(NewsItem).values(
                        user_id=user_id,
                        headline=headline,
                        source=item.get("source") or "unknown",
                        url=item.get("url"),
                        region=item.get("region") or "global",
                        published_at=item.get("published_at"),
                        instruments=meta["instruments"],
                        sectors=meta["sectors"],
                        sentiment=meta["sentiment"],
                        sentiment_score=meta["sentiment_score"],
                        impact=meta["impact"],
                        reliability=item.get("reliability") or "secondary",
                        confirmation="single_source",
                        impact_duration=meta["impact_duration"],
                        summary=(item.get("summary") or "")[:MAX_EXCERPT_CHARS] or None,
                        raw_excerpt=item.get("raw_excerpt") or "",
                        ingested_at=now_ist(),
                        content_hash=digest,
                    )
                    if dialect_name.startswith("postgresql"):
                        stmt = stmt.on_conflict_do_nothing(index_elements=["content_hash"])
                    try:
                        db.execute(stmt)
                        stored += 1
                    except Exception as exc:
                        logger.error(f"Failed to insert news item '{headline}': {exc}")
                        duplicates += 1
                        failed += 1
                db.commit()
            except Exception as exc:
                db.rollback()
                logger.exception("News batch persistence failed; discarding batch")
                return 0, duplicates, failed
        return stored, duplicates, failed

    def _promote_confirmations(self) -> int:
        """Mark events reported by 2+ independent sources as multi_source."""
        promoted = 0
        with SessionLocal() as db:
            rows = (
                db.query(NewsItem)
                .filter(NewsItem.confirmation == "single_source")
                .order_by(NewsItem.published_at.desc().nullslast())
                .limit(500)
                .all()
            )
            by_event: Dict[str, List[NewsItem]] = {}
            for row in rows:
                key = (row.headline or "").strip().lower()[:120]
                by_event.setdefault(key, []).append(row)
            for key, group in by_event.items():
                sources = {(r.source or "").lower() for r in group}
                if len(sources) < 2:
                    continue
                for row in group:
                    if row.confirmation != "multi_source":
                        row.confirmation = "multi_source"
                        promoted += 1
            if promoted:
                db.commit()
        return promoted

    # ------------------------------------------------------------------ queries
    def recent(
        self,
        instruments: Optional[Sequence[str]] = None,
        regions: Optional[Sequence[str]] = None,
        hours: int = 24,
        limit: int = 25,
        min_impact: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        from sqlalchemy import select

        cutoff = now_ist() - timedelta(hours=max(1, min(hours, 336)))
        wanted = {i.upper() for i in (instruments or [])}
        region_filter = {r.lower() for r in (regions or [])}
        order = {"high": 0, "medium": 1, "low": 2}
        rows: List[Dict[str, Any]] = []
        with SessionLocal() as db:
            stmt = select(NewsItem).order_by(NewsItem.published_at.desc().nullslast()).limit(300)
            for item in db.execute(stmt).scalars():
                published = naive_as_ist(item.published_at) if item.published_at else None
                if published and published < cutoff:
                    continue
                if region_filter and (item.region or "").lower() not in region_filter:
                    continue
                if min_impact and order.get(item.impact or "low", 3) > order.get(min_impact, 3):
                    continue
                if wanted and not wanted.intersection({str(i).upper() for i in (item.instruments or [])}):
                    continue
                rows.append(self._row(item))
                if len(rows) >= limit:
                    break
        return rows

    def market_impact_summary(
        self,
        instruments: Optional[Sequence[str]] = None,
        hours: int = 12,
        limit: int = 40,
    ) -> Dict[str, Any]:
        """Aggregate sentiment/impact for the decision engine.

        The summary is descriptive only: it never authorises a trade.
        """
        items = self.recent(instruments=instruments, hours=hours, limit=limit)
        if not items:
            return {
                "items": 0,
                "sentiment": "unknown",
                "net_score": 0.0,
                "high_impact": 0,
                "note": "no stored news in the window",
            }
        scores = [float(i.get("sentiment_score") or 0.0) for i in items]
        net = sum(scores) / len(scores)
        high = [i for i in items if i.get("impact") == "high"]
        return {
            "items": len(items),
            "sentiment": "positive" if net > 0.15 else "negative" if net < -0.15 else "neutral",
            "net_score": round(net, 3),
            "high_impact": len(high),
            "headlines": [i["headline"] for i in high[:5]],
            "note": "keyword-derived sentiment; confirm important items before acting",
        }

    @staticmethod
    def _row(item: NewsItem) -> Dict[str, Any]:
        return {
            "headline": item.headline,
            "source": item.source,
            "url": item.url,
            "region": item.region,
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "instruments": item.instruments or [],
            "sectors": item.sectors or [],
            "sentiment": item.sentiment,
            "sentiment_score": item.sentiment_score,
            "impact": item.impact,
            "reliability": item.reliability,
            "confirmation": item.confirmation,
            "impact_duration": item.impact_duration,
            "summary": item.summary,
        }


_service: Optional[NewsIntelligence] = None


def get_news_service() -> NewsIntelligence:
    global _service
    if _service is None:
        _service = NewsIntelligence()
    return _service


__all__ = [
    "HIGH_IMPACT_KEYWORDS",
    "IngestReport",
    "NEWS_SOURCES",
    "NewsIntelligence",
    "classify",
    "content_hash",
    "get_news_service",
    "sanitize",
]
