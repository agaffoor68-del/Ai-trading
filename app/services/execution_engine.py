"""
Execution Engine - Production Trading Core

Integrates all missed features:
- Charges & Slippage (deducted from PnL)
- Telegram Notifications (order/SL/target/API-failed/AI-summary alerts)
- Trailing Stop Loss (1R breakeven + ATR/fixed points trailing)
- Market Calendar (no trades on weekends/holidays; auto square-off gating)
- Auto Login (APScheduler 07:00 IST token refresh)
- Redis WebSocket ticks (latest LTP to Redis, candles to PostgreSQL)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from app.core.charges import (
    ChargeBreakdown,
    ChargesCalculator,
    InstrumentType,
    TradeSide,
)
from app.core.market_calendar import MarketCalendar
from app.services.auto_login import AutoLoginManager
from app.services.redis_ws import RedisCandleAggregator, RedisTickStore
from app.services.telegram_notifier import TelegramNotifier
from app.services.trailing_stop import TSLState, TrailingStop

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)


@dataclass
class Position:
    symbol: str
    side: str
    entry_price: float
    quantity: int
    lot_size: int
    instrument_type: InstrumentType
    stop_loss: float
    target: float
    entry_charges: ChargeBreakdown = field(default_factory=ChargeBreakdown)
    exit_charges: Optional[ChargeBreakdown] = None
    trailing_stop: Optional[TrailingStop] = None
    is_open: bool = True
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    net_pnl: Optional[float] = None


@dataclass
class OrderResult:
    success: bool
    order_id: str
    symbol: str
    side: str
    quantity: int
    price: float
    message: str


class ExecutionEngine:
    """
    Central execution engine with full production feature integration.
    """

    def __init__(
        self,
        charges_calculator: Optional[ChargesCalculator] = None,
        market_calendar: Optional[MarketCalendar] = None,
        telegram: Optional[TelegramNotifier] = None,
        redis_tick_store: Optional[RedisTickStore] = None,
        candle_aggregator: Optional[RedisCandleAggregator] = None,
        auto_login: Optional[AutoLoginManager] = None,
        session_factory=None,
    ):
        self.charges = charges_calculator or ChargesCalculator()
        self.calendar = market_calendar or MarketCalendar()
        self.telegram = telegram
        self.redis = redis_tick_store
        self.aggregator = candle_aggregator
        self.auto_login = auto_login
        self.SessionLocal = session_factory

        self.positions: dict[str, Position] = {}
        self.order_counter = 0
        self.daily_pnl = 0.0
        self.trade_log: list[dict] = []

    # ------------------------------------------------------------------
    # Market gating
    # ------------------------------------------------------------------
    def can_trade(self) -> bool:
        return self.calendar.can_trade()

    def time_to_close(self) -> int:
        return self.calendar.time_to_close()

    # ------------------------------------------------------------------
    # Order execution (paper/backtest mode with charges)
    # ------------------------------------------------------------------
    async def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        instrument_type: InstrumentType = InstrumentType.OPTIONS,
        lot_size: int = 1,
        stop_loss: Optional[float] = None,
        target: Optional[float] = None,
        trail_points: float = 0.0,
        use_atr: bool = False,
        atr_value: Optional[float] = None,
    ) -> OrderResult:
        if not self.can_trade():
            return OrderResult(
                success=False,
                order_id="",
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                message="Market closed - cannot place order",
            )

        self.order_counter += 1
        order_id = f"ORD{self.order_counter:06d}"

        # Calculate entry charges (buy side: stamp duty applies)
        entry_side = TradeSide.BUY if side.upper() == "BUY" else TradeSide.SELL
        entry_charges = self.charges.calculate(
            instrument_type=instrument_type,
            side=entry_side,
            price=price,
            quantity=quantity,
            lot_size=lot_size,
        )

        position = Position(
            symbol=symbol,
            side=side.upper(),
            entry_price=price,
            quantity=quantity,
            lot_size=lot_size,
            instrument_type=instrument_type,
            stop_loss=stop_loss or price,
            target=target or price,
            entry_charges=entry_charges,
            entry_time=datetime.now(IST),
        )

        # Initialize trailing stop if SL provided
        if stop_loss and target:
            position.trailing_stop = TrailingStop(
                symbol=symbol,
                entry_price=price,
                stop_loss=stop_loss,
                target=target,
                quantity=quantity,
                side=side.upper(),
                trail_points=trail_points,
                use_atr=use_atr,
                atr_value=atr_value,
            )

        self.positions[order_id] = position

        # Telegram alert
        if self.telegram:
            await self.telegram.order_executed(
                symbol=symbol,
                side=side.upper(),
                quantity=quantity,
                price=price,
                order_id=order_id,
                instrument_type=instrument_type.value,
            )

        # Write initial tick to Redis if available
        if self.redis:
            await self.redis.write_tick(
                symbol,
                {
                    "symbol": symbol,
                    "ltp": price,
                    "volume": quantity,
                    "side": side.upper(),
                    "order_id": order_id,
                    "updated_at": datetime.now(IST).isoformat(),
                },
            )

        logger.info(
            f"Order {order_id}: {side} {quantity} {symbol} @ {price} | "
            f"Entry charges: {entry_charges.total_charges}"
        )

        return OrderResult(
            success=True,
            order_id=order_id,
            symbol=symbol,
            side=side.upper(),
            quantity=quantity,
            price=price,
            message="Order executed",
        )

    # ------------------------------------------------------------------
    # Price update - TSL + SL/Target check
    # ------------------------------------------------------------------
    async def on_price_update(self, symbol: str, price: float, volume: int = 0):
        """Called on every WebSocket tick. Updates TSL and checks SL/target."""
        # Write latest LTP to Redis
        if self.redis:
            await self.redis.write_tick(
                symbol,
                {"symbol": symbol, "ltp": price, "volume": volume},
            )

        # Check all open positions for this symbol
        for order_id, pos in list(self.positions.items()):
            if not pos.is_open or pos.symbol != symbol:
                continue

            # TSL update
            if pos.trailing_stop:
                tsl_result = pos.trailing_stop.update_price(price)
                if tsl_result["sl_updated"] and self.telegram:
                    await self.telegram.tsl_updated(
                        symbol=symbol,
                        old_sl=pos.stop_loss,
                        new_sl=pos.trailing_stop.current_sl,
                        current_price=price,
                    )
                pos.stop_loss = pos.trailing_stop.current_sl

            # SL hit
            if pos.trailing_stop and pos.trailing_stop.is_sl_hit(price):
                await self._close_position(order_id, price, reason="SL_HIT")
                continue

            # Target hit
            if pos.trailing_stop and pos.trailing_stop.is_target_hit(price):
                await self._close_position(order_id, price, reason="TARGET_HIT")

    # ------------------------------------------------------------------
    # Position close - deduct charges + slippage from PnL
    # ------------------------------------------------------------------
    async def _close_position(
        self, order_id: str, exit_price: float, reason: str = "MANUAL"
    ):
        pos = self.positions.get(order_id)
        if not pos or not pos.is_open:
            return

        # Calculate exit charges (sell side: STT applies)
        exit_side = TradeSide.SELL if pos.side == "BUY" else TradeSide.BUY
        exit_charges = self.charges.calculate(
            instrument_type=pos.instrument_type,
            side=exit_side,
            price=exit_price,
            quantity=pos.quantity,
            lot_size=pos.lot_size,
        )

        # Gross PnL
        total_qty = pos.quantity * pos.lot_size
        if pos.side == "BUY":
            gross_pnl = (exit_price - pos.entry_price) * total_qty
        else:
            gross_pnl = (pos.entry_price - exit_price) * total_qty

        # Net PnL after charges (entry + exit)
        total_charges = pos.entry_charges.total_charges + exit_charges.total_charges
        net_pnl = gross_pnl - total_charges

        pos.exit_price = exit_price
        pos.exit_charges = exit_charges
        pos.net_pnl = net_pnl
        pos.exit_time = datetime.now(IST)
        pos.is_open = False

        self.daily_pnl += net_pnl

        trade_record = {
            "order_id": order_id,
            "symbol": pos.symbol,
            "side": pos.side,
            "entry_price": pos.entry_price,
            "exit_price": exit_price,
            "quantity": pos.quantity,
            "lot_size": pos.lot_size,
            "gross_pnl": round(gross_pnl, 2),
            "entry_charges": pos.entry_charges.total_charges,
            "exit_charges": exit_charges.total_charges,
            "total_charges": round(total_charges, 2),
            "net_pnl": round(net_pnl, 2),
            "reason": reason,
            "entry_time": pos.entry_time.isoformat() if pos.entry_time else None,
            "exit_time": pos.exit_time.isoformat(),
        }
        self.trade_log.append(trade_record)

        # Telegram alert
        if self.telegram:
            if reason == "SL_HIT":
                await self.telegram.sl_hit(
                    symbol=pos.symbol,
                    side=pos.side,
                    quantity=pos.quantity,
                    exit_price=exit_price,
                    pnl=net_pnl,
                    order_id=order_id,
                )
            elif reason == "TARGET_HIT":
                await self.telegram.target_hit(
                    symbol=pos.symbol,
                    side=pos.side,
                    quantity=pos.quantity,
                    exit_price=exit_price,
                    pnl=net_pnl,
                    order_id=order_id,
                )

        logger.info(
            f"Position {order_id} closed ({reason}): {pos.symbol} "
            f"gross={gross_pnl:.2f} charges={total_charges:.2f} net={net_pnl:.2f}"
        )

    async def auto_square_off(self):
        """Square off all open positions at market close (valid trading days only)."""
        if not self.can_trade():
            logger.info("Auto square-off skipped: not a trading day")
            if self.telegram:
                await self.telegram.send_message("📴 Auto square-off skipped - market closed")
            return

        for order_id, pos in list(self.positions.items()):
            if pos.is_open:
                # Use latest LTP from Redis if available
                exit_price = pos.entry_price
                if self.redis:
                    tick = await self.redis.get_tick(pos.symbol)
                    if tick:
                        exit_price = float(tick.get("ltp", pos.entry_price))
                await self._close_position(order_id, exit_price, reason="AUTO_SQUARE_OFF")

    # ------------------------------------------------------------------
    # Daily summary
    # ------------------------------------------------------------------
    async def send_daily_summary(self, date_str: str):
        winning = sum(1 for t in self.trade_log if t["net_pnl"] > 0)
        total = len(self.trade_log)
        win_rate = (winning / total * 100) if total else 0.0
        if self.telegram:
            await self.telegram.ai_daily_summary(
                date=date_str,
                total_trades=total,
                winning_trades=winning,
                net_pnl=self.daily_pnl,
                win_rate=win_rate,
            )

    # ------------------------------------------------------------------
    # Start background services
    # ------------------------------------------------------------------
    def start_background_jobs(self):
        """Start auto-login scheduler and Redis candle aggregator."""
        if self.auto_login:
            self.auto_login.market_calendar = self.calendar
            self.auto_login.telegram = self.telegram
            self.auto_login.start()

        if self.aggregator and self.redis:
            # Aggregator runs as an asyncio task; caller must await it
            logger.info("Redis candle aggregator ready - call start_aggregator()")

    async def start_aggregator(self, symbols: list[str]):
        if self.aggregator:
            await self.aggregator.start(symbols)

    def get_position(self, order_id: str) -> Optional[Position]:
        return self.positions.get(order_id)

    def get_open_positions(self) -> list[Position]:
        return [p for p in self.positions.values() if p.is_open]

    def get_daily_pnl(self) -> float:
        return round(self.daily_pnl, 2)
