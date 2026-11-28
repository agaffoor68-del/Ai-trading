"""
Fyers WebSocket Service using official FyersDataSocket from fyers_apiv3.

Only dashboard indices and active option strikes around the current ATM are
subscribed. Instrument.symbol contains the canonical Fyers symbol_ticker from
the Symbol Master, so those values are sent to the SDK unchanged.
"""

import asyncio
import logging
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Callable, List

try:
    from fyers_apiv3.FyersWebsocket.data_ws import FyersDataSocket
except Exception:  # pragma: no cover - SDK absent on constrained hosts
    # The broker SDK pulls native deps that are not installable everywhere.
    # Import must not fail: the app stays up and the WS status reports the
    # precise reason instead of the whole backend refusing to boot.
    FyersDataSocket = None  # type: ignore[assignment,misc]

from app.services.redis_ws import redis_tick_store
from app.services.fyers_api import INDEX_MAP

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

DASHBOARD_INDEX_SYMBOLS = list(dict.fromkeys(INDEX_MAP.values()))
OPTION_UNDERLYINGS = {
    "NIFTY": INDEX_MAP["NIFTY"],
    "BANKNIFTY": INDEX_MAP["BANKNIFTY"],
}
OPTION_STRIKES_EACH_SIDE = 10


def _get_active_nearest_option_symbols(spot_prices: dict[str, float]) -> list[str]:
    """Return CE and PE tickers for ATM plus five listed strikes on each side."""
    from app.core.database import Instrument, SessionLocal

    db = SessionLocal()
    try:
        today = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        subscriptions: list[str] = []
        for underlying, index_symbol in OPTION_UNDERLYINGS.items():
            spot = spot_prices.get(index_symbol)
            if spot is None or spot <= 0:
                logger.critical("Skipping %s option subscriptions: no valid positive spot price", underlying)
                continue

            rows = db.query(
                Instrument.symbol,
                Instrument.strike,
                Instrument.expiry,
                Instrument.option_type,
            ).filter(
                Instrument.is_active == 1,
                Instrument.symbol.ilike(f"NSE:{underlying}%"),
            ).all()

            import re as _re
            valid_rows = []
            for symbol, strike_value, expiry, option_type in rows:
                # Ignore old malformed exchange_segment:symbol entries.
                if not symbol or not symbol.startswith("NSE:") or strike_value is None:
                    continue
                # Derive CE/PE from the symbol suffix when option_type is
                # stored as a numeric code or is missing entirely.
                sym_upper = symbol.upper()
                if sym_upper.endswith("CE"):
                    option_type = "CE"
                elif sym_upper.endswith("PE"):
                    option_type = "PE"
                else:
                    continue
                try:
                    strike = float(strike_value)
                except (TypeError, ValueError):
                    continue
                # Derive expiry from the symbol ticker when the DB column
                # is NULL (e.g. NIFTY26DEC25800CE -> 26-DEC-2026).
                if expiry is None:
                    m = _re.search(r"(\d{2})([A-Z]{3})(\d{3,})", sym_upper)
                    if m:
                        dd, mon, _yy = m.groups()
                        try:
                            expiry = datetime.strptime(f"{dd}-{mon}-{today.year}", "%d-%b-%Y")
                        except ValueError:
                            pass
                if expiry is None or expiry.date() < today.date():
                    continue
                valid_rows.append((symbol, strike, expiry, option_type))

            if not valid_rows:
                logger.critical("No active option symbols found for %s", underlying)
                continue

            nearest_expiry = min(row[2] for row in valid_rows)
            expiry_rows = [row for row in valid_rows if row[2] == nearest_expiry]
            listed_strikes = sorted({row[1] for row in expiry_rows})
            atm_index = min(range(len(listed_strikes)), key=lambda index: abs(listed_strikes[index] - spot))
            first_index = max(0, atm_index - OPTION_STRIKES_EACH_SIDE)
            last_index = min(len(listed_strikes), atm_index + OPTION_STRIKES_EACH_SIDE + 1)
            selected_strikes = set(listed_strikes[first_index:last_index])

            # Add both call and put contracts at ATM and each selected ITM/OTM
            # strike. Keep the official symbol_ticker exactly as stored.
            subscriptions.extend(
                symbol for symbol, strike, _expiry, option_type in expiry_rows
                if strike in selected_strikes and option_type in {"CE", "PE"}
            )
            logger.info(
                "Selected %d strikes (%d contracts) for %s expiry %s; spot=%s ATM=%s",
                len(selected_strikes),
                sum(1 for row in expiry_rows if row[1] in selected_strikes),
                underlying,
                nearest_expiry.date(),
                spot,
                listed_strikes[atm_index],
            )
        return subscriptions
    finally:
        db.close()


async def _fetch_spot_prices() -> dict[str, float]:
    """Read current index ticks from Redis first, then fetch any misses via REST."""
    from app.services.fyers_api import fyers_api_client

    index_symbols = list(OPTION_UNDERLYINGS.values())
    spot_prices: dict[str, float] = {}
    for symbol in index_symbols:
        tick = await redis_tick_store.get_tick(symbol)
        try:
            price = float(tick.get("ltp")) if tick and tick.get("ltp") is not None else 0
        except (TypeError, ValueError):
            price = 0
        if price > 0:
            spot_prices[symbol] = price

    missing_symbols = [symbol for symbol in index_symbols if symbol not in spot_prices]
    if missing_symbols:
        logger.info("Fetching missing index spot prices from Fyers REST: %s", missing_symbols)
        rest_quotes = await fyers_api_client.get_quotes(missing_symbols)
        if isinstance(rest_quotes, dict) and not rest_quotes.get("error"):
            for symbol in missing_symbols:
                quote = rest_quotes.get(symbol)
                try:
                    price = float(quote.get("ltp")) if isinstance(quote, dict) and quote.get("ltp") is not None else 0
                except (TypeError, ValueError):
                    price = 0
                if price > 0:
                    spot_prices[symbol] = price

    for symbol in index_symbols:
        if symbol not in spot_prices:
            logger.critical("Unable to retrieve a positive spot price for %s; its option subscriptions will be skipped", symbol)
    return spot_prices


async def _build_dashboard_subscription_symbols() -> list[str]:
    """Build index plus nearest-expiry ATM/ITM/OTM option subscriptions."""
    symbols = list(DASHBOARD_INDEX_SYMBOLS)
    spot_prices = await _fetch_spot_prices()
    try:
        option_symbols = await asyncio.to_thread(_get_active_nearest_option_symbols, spot_prices)
        symbols.extend(option_symbols)
    except Exception:
        logger.exception("Failed to find active ATM option subscriptions; subscribing to indices only")
    # Keep order, remove duplicates, and require exchange-prefixed canonical tickers.
    return list(dict.fromkeys(symbol for symbol in symbols if isinstance(symbol, str) and ":" in symbol))


class FyersWebSocketManager:
    """Manage the official FyersDataSocket in a background thread."""

    def __init__(self):
        self._socket: FyersDataSocket | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._restart_backoff = 5
        self._max_backoff = 300
        self._symbols: List[str] = []
        self._tick_callbacks: List[Callable] = []
        self._last_tick_time: str | None = None
        self._sample_tick_logged = False
        self._last_error: str | None = None
        self._connected = False
        self._symbols_subscribed = 0
        self._client_id: str | None = None
        self._access_token: str | None = None
        self._token_validated = False

    def _validate_token_format(self, token: str) -> tuple[bool, str]:
        """Validate token structure and required JWT claims without logging it."""
        if not token:
            return False, "Empty token"
        parts = token.split(".")
        if len(parts) != 3:
            return False, f"Token is not a JWT (has {len(parts)} parts, expected 3)"
        try:
            import base64
            import json
            payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode())
            if "hsm_key" not in payload:
                return False, "Token payload missing 'hsm_key' claim"
            if "exp" not in payload:
                return False, "Token payload missing 'exp' claim"
            exp_time = datetime.fromtimestamp(payload["exp"], tz=IST)
            if payload["exp"] < int(datetime.now(IST).timestamp()):
                return False, f"Token expired at {exp_time.isoformat()}"
            return True, ""
        except Exception as error:
            return False, f"Failed to decode token payload: {error}"

    def _build_sdk_token(self, client_id: str, access_token: str) -> str:
        """Build the SDK token string: '<client_id>:<access_token>'."""
        return f"{client_id}:{access_token}"

    def _on_connect(self):
        """Subscribe to the configured dashboard symbols after connecting."""
        logger.info("Fyers WS connected")
        self._connected = True
        self._last_error = None
        if self._symbols:
            try:
                logger.info("Subscribing to WS symbols: %s", self._symbols)
                self._socket.subscribe(self._symbols, data_type="SymbolUpdate")
                self._symbols_subscribed = len(self._symbols)
                logger.info("subscribed %d symbols", self._symbols_subscribed)
            except Exception as error:
                logger.error("Failed to subscribe: %s", error)
                self._last_error = f"Subscribe failed: {error}"

    def _on_message(self, message: dict):
        """Process ticks and send them to registered callbacks."""
        try:
            if message.get("type") != "SymbolUpdate":
                return
            symbol = message.get("symbol", "unknown")
            ltp = message.get("ltp")
            if ltp is None:
                return
            ch, chp, vol = message.get("ch"), message.get("chp"), message.get("vol")
            bid, ask = message.get("bid"), message.get("ask")
            open_price, high, low, close = message.get("open"), message.get("high"), message.get("low"), message.get("close")
            ts = message.get("ts")
            dt = datetime.fromtimestamp(ts, tz=IST) if isinstance(ts, (int, float)) else datetime.now(IST)
            self._last_tick_time = datetime.now(IST).isoformat()
            if not self._sample_tick_logged:
                logger.info("Fyers sample tick: symbol=%s ltp=%s", symbol, ltp)
                self._sample_tick_logged = True
            tick = {
                "symbol": symbol,
                "ltp": float(ltp),
                "change": float(ch) if ch is not None else 0.0,
                "change_percent": float(chp) if chp is not None else 0.0,
                "volume": int(vol) if vol is not None else 0,
                "bid": float(bid) if bid is not None else 0.0,
                "ask": float(ask) if ask is not None else 0.0,
                "timestamp": dt,
                "ohlc": {
                    "open": float(open_price) if open_price is not None else 0.0,
                    "high": float(high) if high is not None else 0.0,
                    "low": float(low) if low is not None else 0.0,
                    "close": float(close) if close is not None else 0.0,
                },
            }
            for callback in self._tick_callbacks:
                try:
                    callback(tick)
                except Exception as callback_error:
                    logger.error("Tick callback error: %s", callback_error)
        except Exception as error:
            logger.error("Process tick error: %s", error)

    def _on_error(self, message: dict):
        error_msg = str(message)
        logger.error("Fyers WS error: %s", error_msg)
        self._last_error = error_msg

    def _on_close(self, message: dict):
        close_msg = str(message)
        logger.warning("Fyers WS closed: %s", close_msg)
        self._connected = False
        self._last_error = f"Connection closed: {close_msg}"

    def _run_socket(self):
        """Run the blocking SDK connection loop on its own thread."""
        try:
            if self._socket:
                self._socket.connect()
                self._socket.keep_running()
        except Exception as error:
            logger.exception("Fyers SDK thread error: %s", error)
            self._last_error = f"SDK thread error: {error}"
        finally:
            self._connected = False

    def start(self, client_id: str, access_token: str, symbols: List[str]) -> bool:
        """Start Fyers WebSocket with Fyers-formatted subscription symbols."""
        is_valid, error = self._validate_token_format(access_token)
        if not is_valid:
            logger.error("Fyers token validation failed: %s", error)
            self._last_error = f"Token validation failed: {error}"
            return False
        logger.info("Fyers token validated: length=%d, parts=3, has hsm_key=True", len(access_token))
        self._client_id = client_id
        self._access_token = access_token
        self._symbols = list(dict.fromkeys(symbol for symbol in symbols if isinstance(symbol, str) and ":" in symbol))
        self._symbols_subscribed = 0
        self._sample_tick_logged = False
        self._last_error = None
        self._token_validated = True
        self._stop_event.clear()
        sdk_token = self._build_sdk_token(client_id, access_token)
        self._socket = FyersDataSocket(
            access_token=sdk_token,
            write_to_file=False,
            log_path=None,
            litemode=False,
            reconnect=True,
            on_message=self._on_message,
            on_error=self._on_error,
            on_connect=self._on_connect,
            on_close=self._on_close,
            reconnect_retry=5,
        )
        self._thread = threading.Thread(target=self._run_socket, name="fyers-ws", daemon=True)
        self._thread.start()
        time.sleep(2)
        if self._connected:
            logger.info("Fyers WebSocket manager started successfully")
        else:
            logger.warning("Fyers WebSocket not connected yet, will retry in background")
        return True

    def stop(self):
        """Stop the WebSocket manager and clean up."""
        logger.info("Stopping Fyers WebSocket manager...")
        self._stop_event.set()
        if self._socket:
            try:
                self._socket.close_connection()
            except Exception as error:
                logger.error("Error closing Fyers socket: %s", error)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._connected = False
        self._socket = None
        self._thread = None
        logger.info("Fyers WebSocket manager stopped")

    def is_connected(self) -> bool:
        return self._connected

    def get_status(self) -> dict:
        return {
            "connected": self._connected,
            "last_tick_time": self._last_tick_time,
            "symbols_subscribed": self._symbols_subscribed,
            "last_error": self._last_error,
        }

    def on_tick(self, callback: Callable):
        """Register a callback for incoming ticks."""
        self._tick_callbacks.append(callback)
        return self


_fyers_ws_manager: FyersWebSocketManager | None = None


def get_fyers_ws_manager() -> FyersWebSocketManager:
    global _fyers_ws_manager
    if _fyers_ws_manager is None:
        _fyers_ws_manager = FyersWebSocketManager()
    return _fyers_ws_manager


async def start_fyers_websocket(client_id: str, access_token: str, symbols: List[str]) -> bool:
    """Fetch current spots, then start with indices and nearest ATM options.

    ``symbols`` remains accepted for compatibility with the startup caller but
    is ignored: arbitrary caller-provided equity symbols are not subscribed.
    """
    manager = get_fyers_ws_manager()
    dashboard_symbols = list(DASHBOARD_INDEX_SYMBOLS)
    try:
        spot_prices = await _fetch_spot_prices()
        option_symbols = await asyncio.to_thread(_get_active_nearest_option_symbols, spot_prices)
        dashboard_symbols.extend(option_symbols)
    except Exception:
        logger.exception("Failed to build option subscription list; proceeding with index symbols only")

    logger.info("Using dashboard subscription list (ignoring %d caller-provided symbols)", len(symbols or []))

    async def redis_tick_callback(tick: dict):
        try:
            await redis_tick_store.write_tick(tick["symbol"], tick)
        except Exception as error:
            logger.debug("Redis tick write failed (non-fatal): %s", error)

    manager.on_tick(redis_tick_callback)
    return manager.start(client_id, access_token, dashboard_symbols)


async def stop_fyers_websocket():
    """Stop the WebSocket manager."""
    global _fyers_ws_manager
    if _fyers_ws_manager:
        _fyers_ws_manager.stop()
        _fyers_ws_manager = None


def get_fyers_ws_status() -> dict:
    """Get current WebSocket status for API endpoint."""
    manager = get_fyers_ws_manager()
    if manager:
        return manager.get_status()
    return {"connected": False, "last_tick_time": None, "symbols_subscribed": 0, "last_error": "Manager not initialized"}
