"""Robust options-chain endpoint for Fyers Symbol Master instruments.

Two surfaces:

* ``GET /options/chain``       — the raw CE/PE rows (unchanged legacy shape,
  now enriched with OI/volume/bid/ask when the broker sends them);
* ``GET /options/intelligence`` — the analysed chain (PCR, max pain, IV,
  Greeks, OI walls) with explicit broker-vs-calculated provenance.
"""

import logging
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.datetime_utils import now_ist
from app.core.database import Instrument, SessionLocal
from app.services import options_intelligence
from app.services.fyers_api import fyers_api_client
from app.services.fyers_token import get_fyers_token

logger = logging.getLogger(__name__)
router = APIRouter(tags=["market-data"])

UNDERLYINGS = {
    "NIFTY": ("NSE", "NIFTY", "NSE:NIFTY50-INDEX"),
    "NIFTY 50": ("NSE", "NIFTY", "NSE:NIFTY50-INDEX"),
    "BANKNIFTY": ("NSE", "BANKNIFTY", "NSE:NIFTYBANK-INDEX"),
    "BANK NIFTY": ("NSE", "BANKNIFTY", "NSE:NIFTYBANK-INDEX"),
    "FINNIFTY": ("NSE", "FINNIFTY", "NSE:FINNIFTY-INDEX"),
    "MIDCPNIFTY": ("NSE", "MIDCPNIFTY", "NSE:MIDCPNIFTY-INDEX"),
    "SENSEX": ("BSE", "SENSEX", "BSE:SENSEX-INDEX"),
}


def _leg_payload(symbol: Optional[str], quote: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Quote for one option leg, with missing broker fields left as None."""
    if not symbol:
        return None
    quote = quote or {}
    return {
        "symbol": symbol,
        "ltp": quote.get("ltp"),
        "oi": quote.get("oi"),
        "oi_change": quote.get("oi_change"),
        "volume": quote.get("volume"),
        "bid": quote.get("bid"),
        "ask": quote.get("ask"),
        "change": quote.get("change"),
        "change_percent": quote.get("change_percent"),
    }


async def fetch_chain_data(
    symbol: str,
    expiry: Optional[str] = None,
    strike_count: int = 10,
) -> Dict[str, Any]:
    """Load one expiry's chain from the broker.

    Raises ``HTTPException`` for an unsupported underlying, a missing token or a
    provider failure — the caller must surface those, never substitute data.
    """
    import asyncio
    import re

    normalized = " ".join(symbol.upper().split())
    mapping = UNDERLYINGS.get(normalized)
    if mapping is None:
        raise HTTPException(status_code=400, detail=f"Unsupported underlying: {symbol}")

    exchange, underlying, underlying_ticker = mapping
    requested_expiry = None
    if expiry:
        try:
            requested_expiry = datetime.strptime(expiry, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="expiry must be YYYY-MM-DD") from exc

    token = await asyncio.to_thread(get_fyers_token)
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"code": "FYERS_NOT_CONNECTED", "message": "Fyers not authenticated"},
        )

    quotes = await fyers_api_client.get_quotes([underlying_ticker])
    if isinstance(quotes, dict) and quotes.get("error"):
        raise HTTPException(
            status_code=502,
            detail={"code": "FYERS_ERROR", "message": str(quotes["error"])},
        )
    underlying_quote = (quotes or {}).get(underlying_ticker) or {}
    try:
        spot_price = float(underlying_quote.get("ltp"))
    except (TypeError, ValueError):
        spot_price = 0.0
    if spot_price <= 0:
        raise HTTPException(
            status_code=502,
            detail={"code": "FYERS_ERROR", "message": "Underlying LTP unavailable"},
        )

    def load_contracts():
        db = SessionLocal()
        try:
            today = now_ist().date()
            query = db.query(Instrument).filter(
                Instrument.exchange == ("NSE_FO" if exchange == "NSE" else "BSE_FO"),
                Instrument.symbol.ilike(f"{exchange}:{underlying}%"),
                Instrument.is_active == 1,
                Instrument.expiry.is_not(None),
                Instrument.expiry >= datetime.combine(today, time.min),
            ).order_by(Instrument.expiry.asc())

            instruments = query.all()
            candidates = []
            for item in instruments:
                ticker = (item.symbol or "").strip()
                ticker_upper = ticker.upper()
                side = (item.option_type or "").strip().upper()
                if side not in {"CE", "PE"} and ticker_upper.endswith(("CE", "PE")):
                    side = ticker_upper[-2:]

                # Fyers uses a numeric option instrument code (normally 12).
                # CE/PE is the option side, stored separately as option_type.
                code = str(item.instrument_type or "").strip().upper()
                has_option_code = code in {"12", "12.0", "OPT", "OPTION"}
                has_option_suffix = ticker_upper.endswith(("CE", "PE"))
                # Only accept contracts for this exact underlying. A broad
                # ilike("NIFTY%") can otherwise mix other index products or
                # stale/malformed rows into the chain.
                expected_prefix = f"{exchange}:{underlying}".upper()
                if (
                    side in {"CE", "PE"}
                    and (has_option_code or has_option_suffix)
                    and ticker_upper.startswith(expected_prefix)
                ):
                    # Derive expiry from the symbol ticker when the DB
                    # column is NULL (e.g. NIFTY26DEC25800CE -> 26-DEC-2026).
                    if item.expiry is None:
                        m = re.search(r"(\d{2})([A-Z]{3})(\d{3,})", ticker_upper)
                        if m:
                            dd, mon, _ = m.groups()
                            try:
                                item.expiry = datetime.strptime(f"{dd}-{mon}-{today.year}", "%d-%b-%Y")
                            except ValueError:
                                pass
                    candidates.append((item, side))

            active_expiries = sorted({
                item.expiry.date()
                for item, _ in candidates
                if item.expiry and item.expiry.date() >= today
            })
            logger.info(
                "options-chain: %s total=%d candidates=%d expiries=%s requested=%s spot=%s",
                normalized, len(instruments), len(candidates), active_expiries,
                requested_expiry, spot_price,
            )
            if requested_expiry is None:
                if not active_expiries:
                    return {}, None, active_expiries
                chosen_expiry = active_expiries[0]
            else:
                if requested_expiry not in active_expiries:
                    return {}, None, active_expiries
                chosen_expiry = requested_expiry

            by_strike: Dict[float, Dict[str, str]] = {}
            for item, side in candidates:
                if item.expiry is None or item.expiry.date() != chosen_expiry:
                    continue
                try:
                    strike = float(item.strike)
                except (TypeError, ValueError):
                    continue
                # Exclude obviously stale/mismapped strikes before finding ATM.
                # The wide bound accommodates deep ITM/OTM listings while
                # preventing obsolete index strike series from dominating.
                if abs(strike - spot_price) > max(spot_price * 0.20, 5000):
                    continue
                month_code = item.expiry.strftime("%y%b").upper()
                canonical_symbol = f"{exchange}:{underlying}{month_code}{strike:g}{side}"
                by_strike.setdefault(strike, {})[side] = canonical_symbol
            return by_strike, chosen_expiry, active_expiries
        finally:
            db.close()

    contracts, chosen_expiry, active_expiries = await asyncio.to_thread(load_contracts)
    available_strikes = sorted(contracts)
    if not available_strikes or chosen_expiry is None:
        logger.warning(
            "No active option contracts found for %s expiry=%s",
            normalized, expiry or "nearest",
        )
        return {
            "symbol": normalized,
            "expiry": expiry,
            "spot_price": spot_price,
            "atm_strike": None,
            "strike_interval": None,
            "option_chain": [],
            "expiries": [d.isoformat() for d in active_expiries],
            "timestamp": now_ist().isoformat(),
            "data_available": False,
            "message": "No active option contracts for this underlying/expiry.",
        }

    rounded_atm = int(spot_price / 50 + 0.5) * 50
    atm_index = min(
        range(len(available_strikes)), key=lambda index: abs(available_strikes[index] - rounded_atm)
    )
    atm_strike = available_strikes[atm_index]
    selected_strikes = available_strikes[
        max(0, atm_index - strike_count): min(len(available_strikes), atm_index + strike_count + 1)
    ]

    option_symbols = list(dict.fromkeys(
        contracts[strike].get(side)
        for strike in selected_strikes
        for side in ("CE", "PE")
        if contracts[strike].get(side)
    ))
    option_quotes: Dict[str, Any] = {}
    for offset in range(0, len(option_symbols), 50):
        batch = await fyers_api_client.get_quotes(option_symbols[offset:offset + 50])
        if isinstance(batch, dict) and not batch.get("error"):
            option_quotes.update(batch)

    intervals = [
        round(b - a, 4)
        for a, b in zip(available_strikes, available_strikes[1:])
        if b - a > 0
    ]
    strike_interval = min(intervals) if intervals else None

    rows: List[Dict[str, Any]] = []
    for strike in selected_strikes:
        legs = contracts[strike]
        call_symbol = legs.get("CE")
        put_symbol = legs.get("PE")
        call = _leg_payload(call_symbol, option_quotes.get(call_symbol))
        put = _leg_payload(put_symbol, option_quotes.get(put_symbol))
        rows.append(
            {
                "strike_price": strike,
                "call_symbol": call_symbol,
                "put_symbol": put_symbol,
                "call_ltp": (call or {}).get("ltp"),
                "put_ltp": (put or {}).get("ltp"),
                "call": call,
                "put": put,
                "is_atm": strike == atm_strike,
            }
        )

    return {
        "symbol": normalized,
        "expiry": chosen_expiry.isoformat(),
        "spot_price": spot_price,
        "atm_strike": atm_strike,
        "strike_interval": strike_interval,
        "option_chain": rows,
        "expiries": [d.isoformat() for d in active_expiries],
        "timestamp": now_ist().isoformat(),
        "data_available": bool(rows),
    }


@router.get("/options/chain")
async def get_options_chain(
    symbol: str = Query(..., min_length=1, max_length=32),
    expiry: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to nearest expiry"),
    strike_count: int = Query(10, ge=1, le=50),
):
    """Return CE/PE quotes for ATM and up to strike_count strikes each side."""
    data = await fetch_chain_data(symbol, expiry, strike_count)
    # Legacy consumers read the bare array; keep that shape but expose the
    # richer envelope too so newer callers get spot/expiry/ATM.
    rows = data.get("option_chain", [])
    for row in rows:
        row.setdefault("expiries", data.get("expiries", []))
    return rows


@router.get("/options/chain/full")
async def get_options_chain_full(
    symbol: str = Query(..., min_length=1, max_length=32),
    expiry: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to nearest expiry"),
    strike_count: int = Query(10, ge=1, le=50),
):
    """Envelope form: metadata + rows, for the dashboard chain table."""
    return await fetch_chain_data(symbol, expiry, strike_count)


@router.get("/options/intelligence")
async def get_options_intelligence(
    symbol: str = Query(..., min_length=1, max_length=32),
    expiry: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to nearest expiry"),
    strike_count: int = Query(10, ge=1, le=50),
    include_chain: bool = Query(False),
):
    """Analysed chain: PCR, max pain, IV, Greeks, OI walls, liquidity.

    Every derived field carries its provenance (broker / calculated /
    unavailable) so the UI never presents an estimate as broker data.
    """
    data = await fetch_chain_data(symbol, expiry, strike_count)
    if not data.get("data_available"):
        return {
            "symbol": data.get("symbol"),
            "expiry": data.get("expiry"),
            "available": False,
            "message": data.get("message", "options data unavailable"),
            "expiries": data.get("expiries", []),
            "timestamp": data.get("timestamp"),
        }

    analysis = options_intelligence.analyze_chain(
        symbol=data["symbol"],
        rows=data["option_chain"],
        spot=float(data["spot_price"]),
        expiry=datetime.strptime(data["expiry"], "%Y-%m-%d").date(),
        atm_strike=data.get("atm_strike"),
    )
    payload = analysis.as_dict(include_chain=include_chain)
    payload["expiries"] = data.get("expiries", [])
    payload["strike_interval"] = data.get("strike_interval")
    return payload
