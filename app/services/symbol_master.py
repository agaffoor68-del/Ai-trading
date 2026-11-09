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

# Correct Fyers Symbol Master column names (headerless/positional)
FYERS_COLUMNS = [
    "fytoken",
    "symbol",
    "instrumentType",
    "lotSize",
    "tickSize",
    "ISIN",
    "tradingSession",
    "lastUpdate",
    "expiryDate",
    "symbolTicker",
    "exchange",
    "segment",
    "scripCode",
    "scripName",
    "scripToken",
    "strikePrice",
    "optionType",
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
            # Read headerless CSV with explicit column names
            df = pd.read_csv(
                io.StringIO(csv_content),
                header=None,
                names=FYERS_COLUMNS,
                dtype=str,  # Read all as strings first
                skipinitialspace=True,
            )
            
            logger.info(f"Raw DataFrame shape for {exchange}: {df.shape}")
            logger.info(f"Columns: {list(df.columns)}")
            
            # Skip metadata rows - filter rows where fytoken is numeric (valid instrument rows)
            # Fyers metadata rows typically have non-numeric fytoken
            df = df[df['fytoken'].str.isnumeric()]
            
            logger.info(f"Filtered DataFrame shape for {exchange}: {df.shape}")
            
            if df.empty:
                logger.warning(f"No valid instrument rows found for {exchange}")
                return []

            # Strip whitespace from all string columns
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].str.strip()
            
            # Replace empty strings with None
            df = df.replace('', None)

            instruments = []
            for _, row in df.iterrows():
                try:
                    # Skip rows with missing required fields
                    if not row.get('symbol') or not row.get('fytoken'):
                        continue
                    
                    # Parse numeric fields
                    lot_size = int(row['lotSize']) if row['lotSize'] and row['lotSize'].isdigit() else None
                    strike = float(row['strikePrice']) if row['strikePrice'] else None
                    
                    # Parse expiry date
                    expiry = None
                    if row['expiryDate']:
                        try:
                            expiry = datetime.strptime(row['expiryDate'], "%Y-%m-%d")
                        except ValueError:
                            try:
                                expiry = datetime.strptime(row['expiryDate'], "%d-%b-%Y")
                            except ValueError:
                                pass
                    
                    instruments.append(
                        {
                            "symbol": row['symbol'],
                            "name": row['scripName'],
                            "exchange": exchange,
                            "segment": row['segment'],
                            "lot_size": lot_size,
                            "tick_size": row['tickSize'],
                            "instrument_type": row['instrumentType'],
                            "expiry": expiry,
                            "strike": strike,
                            "option_type": row['optionType'],
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
