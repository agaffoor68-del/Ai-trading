"""
Fyers Live Data WebSocket Service Module 2

Provides real-time WebSocket connection for Fyers live ticks,
historical candles, and symbol search functionality.
"""
import asyncio, json, logging
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp, pandas as pd

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")
FWS_URL = "wss://api.fyers.in/apiws/v3/"


class FyersWebSocket:
    """Fyers WebSocket connection manager for live market data."""

    def __init__(self, access_token, symbols=None, session=None):
        self.access_token = access_token
        self.symbols = symbols or []
        self.session = session
        self.ws_connection = None
        self.is_connected = False
        self.tick_callbacks = []
        self._connected_event = asyncio.Event()
        self._disconnect_event = asyncio.Event()

    async def connect(self):
        """Establish WebSocket connection to Fyers."""
        try:
            import wsproto, websockets

            async with websockets.connect(
                FWS_URL,
                extra_headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                ping_interval=20,
                ping_timeout=60,
            ) as ws:
                self.ws_connection = ws
                self.is_connected = True
                self._connected_event.set()
                logger.info(f"Fyers WS connected. Subscribing to: {self.symbols}")

                if self.symbols:
                    msg = {"action": "subscribe", "tokens": self.symbols}
                    await ws.send(json.dumps(msg))

                await self._listen_loop()
        except Exception as e:
            logger.error(f"Fyers WS connection error: {str(e)}")
            self.is_connected = False
            self._connected_event.clear()
            return False

    async def _listen_loop(self):
        """Main message listening loop."""
        try:
            while self.is_connected:
                msg = await self.ws_connection.recv()
                await self._handle_message(msg)
        except Exception:
            pass
        finally:
            self.is_connected = False
            self._connected_event.clear()

    async def _handle_message(self, message):
        """Handle incoming WebSocket message."""
        try:
            if isinstance(message, bytes):
                message = message.decode("utf-8")
            data = json.loads(message)
            if "ltp" in data or "depth" in data:
                await self._process_tick(data)
        except Exception as e:
            logger.error(f"Handle message error: {str(e)}")

    async def _process_tick(self, tick_data):
        """Process individual tick data."""
        try:
            ts = tick_data.get("ts", tick_data.get("timestamp", ""))
            symbol = tick_data.get("symbol", "unknown")

            if isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts, tz=IST)
            elif isinstance(ts, str):
                dt = datetime.fromisoformat(ts).replace(tzinfo=IST)
            else:
                dt = datetime.now(IST)

            tick = {
                "symbol": symbol,
                "ltp": float(tick_data.get("ltp", 0) or 0),
                "volume": int(tick_data.get("volume", 0) or 0),
                "bid": float(tick_data.get("bid_price", 0) or 0),
                "ask": float(tick_data.get("ask_price", 0) or 0),
                "timestamp": dt,
                "ohlc": {
                    "open": float(tick_data.get("open", 0) or 0),
                    "high": float(tick_data.get("high", 0) or 0),
                    "low": float(tick_data.get("low", 0) or 0),
                    "close": float(tick_data.get("close", 0) or 0),
                },
                "exchange": self._extract_exchange(symbol),
            }

            for cb in self.tick_callbacks:
                try:
                    await cb(tick)
                except Exception as cb_err:
                    logger.error(f"Tick callback error: {str(cb_err)}")
        except Exception as e:
            logger.error(f"Process tick error: {str(e)}")

    def _extract_exchange(self, symbol):
        """Extract exchange from Fyers symbol."""
        if symbol.startswith("NSE:"):
            return "NSE"
        if symbol.startswith("BSE:"):
            return "BSE"
        if symbol.startswith("FO:"):
            return "NSE_FO"
        return "UNKNOWN"

    def on_tick(self, callback):
        """Register tick callback."""
        self.tick_callbacks.append(callback)
        return self

    async def subscribe(self, symbols):
        """Subscribe to live tick data."""
        self.symbols = symbols
        if not self.is_connected or not self.ws_connection:
            return False
        try:
            await self.ws_connection.send(json.dumps({"action": "subscribe", "tokens": symbols}))
            logger.info(f"Subscribed to: {symbols}")
            return True
        except Exception as e:
            logger.error(f"Subscribe error: {str(e)}")
            return False

    async def disconnect(self):
        """Gracefully disconnect."""
        self.is_connected = False
        if self.ws_connection:
            try:
                await self.ws_connection.close()
            except Exception:
                pass
        self._connected_event.set()
        async def fetch_historical_candles(
    access_token, symbol, timeframe="1min", date_from=None, date_to=None, session=None
):
    """Fetch historical candles from Fyers API v3."""
    if session is None:
        session = aiohttp.ClientSession()

    try:
        base_url = "https://api.fyers.in/api/v3/historical-data"
        params = {
            "symbol": symbol,
            "resolution": timeframe,
            "date_format": "1",
            "ohlc": "true",
            "history_type": "2",
            "strikeprice": "",
            "expiry": "",
            "timestamp": "",
            "type": "2",
        }
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to

        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        async with session.get(
            base_url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status != 200:
                logger.error(f"Fyers candles API error: Status {resp.status}")
                return None
            data = await resp.json()

        if data.get("code") != "200":
            logger.error(f"Fyers error code: {data.get('code')}")
            return None

        candle_data = data.get("candle", [])
        if not candle_data:
            return pd.DataFrame()

        df = pd.DataFrame(candle_data, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
        df["open"] = pd.to_numeric(df["open"], errors="coerce")
        df["high"] = pd.to_numeric(df["high"], errors="coerce")
        df["low"] = pd.to_numeric(df["low"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        df = df.sort_values("timestamp").reset_index(drop=True)
        df["timestamp"] = df["timestamp"].apply(
            lambda ts: datetime.fromtimestamp(ts, tz=IST) if pd.notna(ts) else pd.NaT
        )
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]
        logger.info(f"Fetched {len(df)} candles for {symbol} ({timeframe})")
        return df
    except Exception as e:
        logger.error(f"Fetch candles error: {str(e)}")
        return None
    finally:
        if session and not session._closed:
            await session.close()


async def search_symbols_db(query, db_session, exchange=None):
    """Search symbols from PostgreSQL instruments table."""
    from sqlalchemy import or_

    try:
        filter_condition = or_(
            Instrument.symbol.ilike(f"%{query}%"),
            Instrument.name.ilike(f"%{query}%"),
        )
        if exchange:
            filter_condition &= Instrument.exchange == exchange
        results = db_session.query(Instrument).filter(filter_condition).limit(20).all()
        return [
            {
                "symbol": inst.symbol,
                "exchange": inst.exchange,
                "name": inst.name,
                "token": inst.token,
                "id": inst.id,
            }
            for inst in results
        ]
    except Exception as e:
        logger.error(f"Search symbols error: {str(e)}")
        return []


async def fyers_ws_message_handler(ws_message, tick_callbacks):
    """Handle incoming WebSocket messages in FastAPI context."""
    try:
        data = json.loads(ws_message)

        if "ltp" in data or "depth" in data:
            for callback in tick_callbacks:
                try:
                    await callback(data)
                except Exception as cb_err:
                    logger.error(f"WS message callback error: {str(cb_err)}")
        elif data.get("action") == "subscribe":
            logger.info(f"Fyers subscription confirmed: {data}")
        elif data.get("action") == "unsubscribe":
            logger.info(f"Fyers unsubscription confirmed: {data}")
        else:
            logger.debug(f"Fyers WS message: {list(data.keys())}")

    except json.JSONDecodeError:
        logger.error("Failed to parse Fyers WebSocket message as JSON")
    except Exception as e:
        logger.error(f"Error in Fyers WS message handler: {str(e)}")
