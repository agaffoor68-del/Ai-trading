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
            # Fyers masters are headerless; assigning the schema during parsing
            # prevents pandas from inferring a first-row header or shifting names.
            df = pd.read_csv(
                io.StringIO(csv_content.lstrip("\ufeff")),
                header=None,
                names=FYERS_COLUMNS,
                dtype=str,
                skipinitialspace=True,
                encoding="utf-8-sig",
                on_bad_lines="warn",
            )
            if df.empty:
                logger.warning("No rows found in %s symbol master", exchange)
                return []

            logger.info("Raw DataFrame shape for %s: %s", exchange, df.shape)
            logger.info("Columns for %s: %s", exchange, list(df.columns))

            for col in df.select_dtypes(include=["object"]).columns:
                df[col] = df[col].str.strip()
            # Keep blank cells as None rather than pandas NaN (which is truthy and
            # can otherwise reach datetime parsing as a float).
            df = df.astype(object).where(pd.notna(df), None)

            df["instrument_type"] = df["instrument_type"].fillna("").astype(str).str.strip()
            df["option_type"] = df["option_type"].fillna("").astype(str).str.strip().str.upper()
            df["symbol_ticker"] = df["symbol_ticker"].fillna("").astype(str).str.strip()
            df["segment"] = df["segment"].fillna("").astype(str).str.strip()

            # Fyers has shipped FO master revisions where the instrument code
            # is blank or represented differently. The CE/PE field and the
            # canonical ticker suffix are authoritative for option contracts.
            is_option = (
                df["option_type"].isin(["CE", "PE"])
                | df["symbol_ticker"].str.upper().str.endswith(("CE", "PE"))
            )
            df.loc[is_option, "instrument_type"] = "12"
            df.loc[
                is_option & ~df["option_type"].isin(["CE", "PE"]), "option_type"
            ] = df.loc[
                is_option & ~df["option_type"].isin(["CE", "PE"]), "symbol_ticker"
            ].str.upper().str[-2:]
            is_future = (
                df["symbol_ticker"].str.upper().str.endswith("FUT")
                & ~is_option
            )
            df.loc[is_future & df["instrument_type"].eq(""), "instrument_type"] = "11"
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
                        for date_format in ("%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y", "%Y/%m/%d", "%d/%m/%Y", "%d-%b-%y", "%d-%b-%Y"):
                            try:
                                expiry = datetime.strptime(expiry_value, date_format)
                                break
                            except ValueError:
                                continue
                    # Fallback: derive expiry from the symbol ticker when the
                    # CSV expiry column is empty or unparseable (e.g. NIFTY26DEC25800CE).
                    if expiry is None:
                        try:
                            import re
                            m = re.search(r"(\d{2})([A-Z]{3})\d{3,}", symbol_ticker)
                            if m:
                                yy, mon = m.groups()
                                # Symbol master only encodes month+year; use the
                                # 15th as a placeholder so the row still sorts.
                                expiry = datetime.strptime(f"15-{mon}-20{yy}", "%d-%b-%Y")
                        except Exception:
                            pass

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


async def get_options_chain(symbol: str, expiry: str, strikes_each_side: int = 10) -> dict:
    """Return available CE/PE contracts nearest to the live ATM strike."""
    from app.services.fyers_api import fyers_api_client

    index_symbols = {
        "NIFTY": "NSE:NIFTY50-INDEX",
        "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
        "FINNIFTY": "NSE:FINNIFTY-INDEX",
        "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
        "SENSEX": "BSE:SENSEX-INDEX",
    }
    normalized_symbol = symbol.strip().upper()
    index_ticker = index_symbols.get(normalized_symbol)
    if not index_ticker:
        raise ValueError(f"Unsupported options underlying: {symbol}")
    if not 1 <= strikes_each_side <= 50:
        raise ValueError("strikes_each_side must be between 1 and 50")

    quote = await fyers_api_client.get_quotes([index_ticker])
    spot_price = (quote or {}).get(index_ticker, {}).get("ltp")
    if spot_price is None and quote:
        spot_price = next(iter(quote.values())).get("ltp") if not any(
            key == "error" for key in quote
        ) else None
    if not isinstance(spot_price, (int, float)) or spot_price <= 0:
        raise RuntimeError(f"Live LTP unavailable for {normalized_symbol}")

    expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()

    def load_contracts() -> list[dict]:
        db = SessionLocal()
        try:
            candidates = db.query(Instrument).filter(
                Instrument.symbol.ilike(f"%{normalized_symbol}%"),
                Instrument.expiry >= datetime.combine(expiry_date, datetime.min.time()),
                Instrument.expiry < datetime.combine(expiry_date, datetime.max.time()),
                Instrument.instrument_type.in_(["12", "12.0", "OPT", "OPTION"]),
                Instrument.option_type.in_(["CE", "PE"]),
                Instrument.is_active == 1,
            ).all()
            by_strike: dict[float, dict] = {}
            for instrument in candidates:
                try:
                    strike = float(instrument.strike)
                except (TypeError, ValueError):
                    continue
                legs = by_strike.setdefault(strike, {"strike": strike, "call": None, "put": None})
                option_type = (instrument.option_type or "").upper()
                legs["call" if option_type == "CE" else "put"] = {
                    "symbol": instrument.symbol,
                    "fyers_token": instrument.fyers_token,
                }
            return list(by_strike.values())
        finally:
            db.close()

    contracts = await asyncio.to_thread(load_contracts)
    available_strikes = sorted(row["strike"] for row in contracts)
    if not available_strikes:
        return {"symbol": normalized_symbol, "expiry": expiry, "spot_price": spot_price, "atm_strike": None, "option_chain": []}

    atm_strike = min(available_strikes, key=lambda strike: abs(strike - spot_price))
    atm_index = available_strikes.index(atm_strike)
    start = max(0, atm_index - strikes_each_side)
    end = min(len(available_strikes), atm_index + strikes_each_side + 1)
    selected = set(available_strikes[start:end])
    return {
        "symbol": normalized_symbol,
        "expiry": expiry,
        "spot_price": spot_price,
        "atm_strike": atm_strike,
        "option_chain": [row for row in contracts if row["strike"] in selected],
    }


async def main():
    downloader = SymbolMasterDownloader()
    try:
        await downloader.load_all()
    finally:
        await downloader.close()


if __name__ == "__main__":
    asyncio.run(main())
