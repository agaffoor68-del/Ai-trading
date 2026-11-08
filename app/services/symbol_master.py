"""
Phase 1: Symbol Master Downloader

Downloads and parses Fyers Symbol Master CSVs (NSE_CM.csv, NSE_FO.csv)
into the local PostgreSQL database.

Non-Negotiable Rule: Fyers API v3 is the ONLY data source.
"""

import asyncio
import csv
import io
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp

from app.core.config import settings
from app.core.database import SessionLocal, Instrument, init_db

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)

# Fyers Symbol Master CSV URLs (NSE only)
SYMBOL_MASTER_FILES = {
    "NSE_CM": "NSE_CM.csv",
    "NSE_FO": "NSE_FO.csv",
}


class SymbolMasterDownloader:
    """
    Downloads and parses Fyers Symbol Master CSVs into PostgreSQL.
    Only NSE segments are supported (Fyers data source).
    """

    def __init__(self):
        self.base_url = settings.FYERS_SYMBOL_MASTER_BASE
        self.session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60)
            )
        return self.session

    async def download_csv(self, filename: str) -> str:
        """Download a symbol master CSV from Fyers."""
        session = await self._get_session()
        url = f"{self.base_url}/{filename}"
        logger.info(f"Downloading {url}")

        async with session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"Failed to download {filename}: HTTP {resp.status}")
            return await resp.text()

    def parse_csv(self, csv_content: str, exchange: str) -> list[dict]:
        """Parse Fyers Symbol Master CSV content into instrument records."""
        instruments = []
        reader = csv.DictReader(io.StringIO(csv_content))

        for row in reader:
            try:
                symbol = row.get("symbol", "").strip()
                if not symbol:
                    continue

                instruments.append(
                    {
                        "symbol": symbol,
                        "name": row.get("name", "").strip() or None,
                        "exchange": exchange,
                        "segment": row.get("segment", "").strip() or None,
                        "lot_size": int(row.get("lot_size", 0) or 0) or None,
                        "tick_size": row.get("tick_size", "").strip() or None,
                        "instrument_type": row.get("instrument_type", "").strip() or None,
                        "expiry": self._parse_date(row.get("expiry")),
                        "strike": row.get("strike", "").strip() or None,
                        "option_type": row.get("option_type", "").strip() or None,
                        "fyers_token": row.get("token", "").strip() or None,
                        "is_active": 1,
                        "created_at": datetime.now(IST),
                        "updated_at": datetime.now(IST),
                    }
                )
            except Exception as e:
                logger.warning(f"Skipping row due to parse error: {e}")
                continue

        return instruments

    @staticmethod
    def _parse_date(date_str: str):
        if not date_str or date_str.strip() == "":
            return None
        try:
            return datetime.strptime(date_str.strip(), "%Y-%m-%d")
        except ValueError:
            try:
                return datetime.strptime(date_str.strip(), "%d-%b-%Y")
            except ValueError:
                return None

    async def load_all(self):
        """Download and load all symbol master files into PostgreSQL."""
        init_db()  # Ensure tables exist

        db = SessionLocal()
        try:
            for exchange, filename in SYMBOL_MASTER_FILES.items():
                logger.info(f"Processing {exchange} symbol master...")

                csv_content = await self.download_csv(filename)
                instruments = self.parse_csv(csv_content, exchange)
                logger.info(f"Parsed {len(instruments)} instruments from {filename}")

                # Clear existing instruments for this exchange
                db.query(Instrument).filter(Instrument.exchange == exchange).delete()
                db.commit()

                # Batch insert
                batch_size = 1000
                for i in range(0, len(instruments), batch_size):
                    batch = instruments[i : i + batch_size]
                    db.bulk_insert_mappings(Instrument, batch)
                    db.commit()
                    logger.info(
                        f"Inserted {min(i + batch_size, len(instruments))}/{len(instruments)} "
                        f"{exchange} instruments"
                    )

            total = db.query(Instrument).count()
            logger.info(f"Symbol master load complete: {total} total instruments")
            return total
        finally:
            db.close()

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


async def main():
    downloader = SymbolMasterDownloader()
    try:
        await downloader.load_all()
    finally:
        await downloader.close()


if __name__ == "__main__":
    asyncio.run(main())
