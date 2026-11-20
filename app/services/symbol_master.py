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

# Current Fyers symbol-master schema: headerless, 21 fields per record.
FYERS_COLUMNS = [
    "fytoken",
    "symbol_description",
    "instrument_type",
    "lot_size",
    "tick_size",
    "ISIN",
    "trading_session",
    "last_update_date",
    "expiry_date",
    "symbol_ticker",
    "exchange_code",
    "segment",
    "scrip_code",
    "underlying_symbol",
    "underlying_scrip_code",
    "strike_price",
    "option_type",
    "underlying_fytoken",
    "reserved_1",
    "reserved_2",
    "reserved_3",
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
        logger.info("Downloading %s", url)

        async with session.get(url) as resp:
            if resp.status != 200:
                logger.warning("Failed to download %s: HTTP %s - %s", filename, resp.status, url)
                return ""
            return await resp.text(encoding="utf-8-sig")

    def parse_csv(self, csv_content: str, exchange: str) -> list[dict]:
        """Parse the current headerless Fyers 21-column CSV safely."""
        if not csv_content.strip():
            logger.warning("Empty CSV content for %s", exchange)
            return []

        try:
            # csv.reader counts fields correctly even when a quoted value contains a comma.
            reader = csv.reader(io.StringIO(csv_content.lstrip("\ufeff")))
            valid_rows = []
            bad_rows = 0
            for line_number, row in enumerate(reader, start=1):
                if not row or all(not field.strip() for field in row):
                    continue
                if len(row) != len(FYERS_COLUMNS):
                    bad_rows += 1
                    if bad_rows <= 5:
                        logger.warning(
                            "Skipping malformed %s CSV record at logical row %s: expected %s fields, got %s",
                            exchange, line_number, len(FYERS_COLUMNS), len(row),
                        )
                    continue
                valid_rows.append(row)

            if bad_rows:
                logger.warning("Skipped %s malformed CSV records for %s", bad_rows, exchange)
            if not valid_rows:
                logger.error("No rows matched the %s-field Fyers schema for %s", len(FYERS_COLUMNS), exchange)
                return []

            normalized_csv = io.StringIO()
            csv.writer(normalized_csv, lineterminator="\n").writerows(valid_rows)
            normalized_csv.seek(0)
            df = pd.read_csv(
                normalized_csv,
                header=None,
                names=FYERS_COLUMNS,
                dtype=str,
                skipinitialspace=True,
                encoding="utf-8-sig",
                on_bad_lines="warn",
            )

            logger.info("Raw DataFrame shape for %s: %s", exchange, df.shape)
            logger.info("Columns for %s: %s", exchange, list(df.columns))

            for col in df.select_dtypes(include=["object"]).columns:
                df[col] = df[col].str.strip()
            # Keep blank cells as None rather than pandas NaN (which is truthy and
            # can otherwise reach datetime parsing as a float).
            df = df.astype(object).where(pd.notna(df), None)

            df["instrument_type"] = df["instrument_type"].fillna("").str.strip()
            df["segment"] = df["segment"].fillna("").str.strip()
            logger.info(
                "Fyers instrument_type counts for %s: %s",
                exchange,
                df["instrument_type"].replace("", pd.NA).value_counts(dropna=False).to_dict(),
            )

            df = df.replace("", None)
            df = df[df["fytoken"].notna() & df["fytoken"].str.isnumeric()]
            df = df[df["symbol_ticker"].notna()]

            # Current Fyers Exchange Instrument Type codes: 0 = cash-market equity;
            # 11/12 are futures/options in the F&O master. Trading series (EQ/BE/BZ)
            # are suffixes of symbol_ticker and are intentionally not stored as this code.
            if exchange == "NSE_CM":
                df = df[df["instrument_type"].isin(["0", "10", "EQ", "EQUITY", "STK"])]
                logger.info("Filtered cash-market instrument types for %s", exchange)
            elif exchange == "NSE_FO":
                df = df[df["instrument_type"].isin(["11", "11.0", "12", "12.0", "FUT", "OPT", "FUTURE", "OPTION"])]
                logger.info("Filtered FUT/OPT instrument types for %s", exchange)

            logger.info(f"Filtered DataFrame shape for {exchange}: {df.shape}")

            if not df.empty:
                logger.info("Sample filtered rows for %s:\n%s", exchange, df[
                    ['fytoken', 'symbol_ticker', 'symbol_description',
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
                            "name": row.get('symbol_description') or row.get('underlying_symbol') or symbol_ticker,
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
