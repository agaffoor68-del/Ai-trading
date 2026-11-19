"""
Phase 1: Symbol Master Downloader

Downloads and parses Fyers Symbol Master CSVs (NSE_CM.csv, NSE_FO.csv)
into the local PostgreSQL database.

Non-Negotiable Rule: Fyers API v3 is the ONLY data source.
"""

import asyncio
import io
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp
import pandas as pd

from app.core.config import settings
from app.core.database import SessionLocal, Instrument, init_db

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)

# Fyers Symbol Master CSV URLs (NSE only)
SYMBOL_MASTER_FILES = {
    "NSE_CM": "NSE_CM.csv",
    "NSE_FO": "NSE_FO.csv",
}

# Fyers CSVs are headerless and contain 19 columns in this exact order.
FYERS_COLUMNS = [
    "fytoken",
    "symbol_ticker",
    "symbol_description",
    "symbol_shortname",
    "ISIN",
    "lot_size",
    "tick_size",
    "trading_session",
    "last_update_date",
    "expiry_date",
    "instrument_type",
    "scrip_code",
    "segment",
    "strike_price",
    "option_type",
    "underlying_symbol",
    "underlying_scrip_code",
    "underlying_fytoken",
    "reserved",
]


class SymbolMasterDownloader:
    """
    Downloads and parses Fyers Symbol Master CSVs into PostgreSQL.
    Only NSE segments are supported (Fyers data source).
    """

    def __init__(self):
        # Strip trailing slash to avoid double-slash in URL construction
        self.base_url = settings.FYERS_SYMBOL_MASTER_BASE.rstrip('/')
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
                logger.warning(f"Failed to download {filename}: HTTP {resp.status} - {url}")
                # Return empty CSV content to allow graceful degradation
                return ""
            return await resp.text()

    def parse_csv(self, csv_content: str, exchange: str) -> list[dict]:
        """Parse Fyers Symbol Master CSV content into instrument records."""
        if not csv_content.strip():
            logger.warning(f"Empty CSV content for {exchange}")
            return []

        try:
            # Read headerless CSV with the exact 19-column Fyers schema.
            df = pd.read_csv(
                io.StringIO(csv_content),
                header=None,
                names=FYERS_COLUMNS,
                dtype=str,
                skipinitialspace=True,
            )

            logger.info(f"Raw DataFrame shape for {exchange}: {df.shape}")
            logger.info(f"Columns: {list(df.columns)}")

            # Strip whitespace from all string columns before filtering.
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].str.strip()

            df['instrument_type'] = df['instrument_type'].str.upper()
            df['segment'] = df['segment'].str.upper()

            # Replace empty strings with None.
            df = df.replace('', None)

            # The canonical Fyers ticker is symbol_ticker; shortname and
            # description are separate display fields, not ticker substitutes.
            df = df[df['fytoken'].notna() & df['fytoken'].str.isnumeric()]
            df = df[df['symbol_ticker'].notna()]

            # For NSE_CM, keep EQ instruments; for NSE_FO, keep all FUT/OPT.
            if exchange == "NSE_CM":
                df = df[df['instrument_type'].isin(['10', 'EQ', 'EQUITY', 'STK'])]
                logger.info(f"Filtered for EQ instruments (code 10) in {exchange}")
            elif exchange == "NSE_FO":
                df = df[df['instrument_type'].isin(['11', '12', 'FUT', 'OPT', 'FUTURE', 'OPTION'])]
                logger.info(f"Filtered for FUT/OPT instruments (codes 11/12) in {exchange}")

            logger.info(f"Filtered DataFrame shape for {exchange}: {df.shape}")

            if not df.empty:
                logger.info("Sample filtered rows for %s:\n%s", exchange, df[
                    ['fytoken', 'symbol_ticker', 'symbol_description', 'symbol_shortname',
                     'instrument_type', 'segment', 'expiry_date', 'strike_price', 'option_type']
                ].head(10).to_string())

            if df.empty:
                logger.warning(f"No valid instrument rows found for {exchange} after filtering")
                return []

            instruments = []
            for _, row in df.iterrows():
                try:
                    if not row.get('symbol_ticker') or not row.get('fytoken'):
                        continue

                    # Preserve the canonical ticker supplied by Fyers. If a
                    # ticker lacks its exchange prefix, use the NSE prefix.
                    symbol_ticker = row['symbol_ticker']
                    if ':' not in symbol_ticker:
                        symbol_ticker = f"NSE:{symbol_ticker}"

                    lot_size_value = row.get('lot_size')
                    lot_size = int(lot_size_value) if lot_size_value and lot_size_value.isdigit() else None
                    strike_value = row.get('strike_price')
                    try:
                        strike = float(strike_value) if strike_value else None
                    except (TypeError, ValueError):
                        strike = None

                    # Parse expiry date - handle multiple formats.
                    expiry = None
                    expiry_value = row.get('expiry_date')
                    if expiry_value:
                        for date_format in ("%Y-%m-%d", "%d-%b-%Y"):
                            try:
                                expiry = datetime.strptime(expiry_value, date_format)
                                break
                            except ValueError:
                                continue

                    instruments.append(
                        {
                            "symbol": symbol_ticker,
                            "name": row.get('symbol_shortname') or row.get('symbol_description') or symbol_ticker,
                            "exchange": exchange,
                            "segment": row.get('segment'),
                            "lot_size": lot_size,
                            "tick_size": row.get('tick_size'),
                            "instrument_type": row.get('instrument_type'),
                            "expiry": expiry,
                            "strike": strike,
                            "option_type": row.get('option_type'),
                            "fyers_token": row['fytoken'],
                            "is_active": 1,
                            "created_at": datetime.now(IST),
                            "updated_at": datetime.now(IST),
                        }
                    )
                except Exception as e:
                    logger.warning(f"Skipping row due to parse error: {e}")
                    continue

            logger.info(f"Successfully parsed {len(instruments)} instruments from {exchange}")
            return instruments

        except Exception as e:
            logger.error(f"Failed to parse CSV for {exchange}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    async def load_all(self):
        """Download and load all symbol master files into PostgreSQL."""
        init_db()  # Ensure tables exist

        db = SessionLocal()
        try:
            total_instruments = 0
            for exchange, filename in SYMBOL_MASTER_FILES.items():
                logger.info(f"Processing {exchange} symbol master...")

                csv_content = await self.download_csv(filename)
                if not csv_content.strip():
                    logger.warning(f"Empty CSV content for {filename}, skipping...")
                    continue

                instruments = self.parse_csv(csv_content, exchange)
                logger.info(f"Parsed {len(instruments)} instruments from {filename}")

                if not instruments:
                    logger.warning(f"No valid instruments parsed from {filename}")
                    continue

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

                total_instruments += len(instruments)

            logger.info(f"Symbol master load complete: {total_instruments} total instruments")
            return total_instruments
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
