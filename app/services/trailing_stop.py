"""
Trailing Stop Loss (TSL) Logic

Rules:
1. Once a trade hits 1R (1x risk) in profit, move SL to entry price (breakeven).
2. After breakeven, trail SL using fixed points or ATR-based method.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

logger = logging.getLogger(__name__)


class TSLState(str, Enum):
    INACTIVE = "INACTIVE"
    ARMED = "ARMED"          # In profit but not yet at 1R
    BREAKEVEN = "BREAKEVEN"  # Hit 1R, SL moved to entry
    TRAILING = "TRAILING"    # Actively trailing SL


@dataclass
class TrailingStop:
    symbol: str
    entry_price: float
    stop_loss: float
    target: float
    quantity: int
    side: str  # "BUY" or "SELL"
    risk_per_unit: float = field(init=False)
    one_r_profit: float = field(init=False)
    state: TSLState = TSLState.INACTIVE
    current_sl: float = field(init=False)
    highest_profit_price: float = field(init=False)
    lowest_profit_price: float = field(init=False)
    breakeven_reached_at: Optional[datetime] = None
    trail_points: float = 0.0
    atr_value: Optional[float] = None
    use_atr: bool = False

    def __post_init__(self):
        if self.side.upper() == "BUY":
            self.risk_per_unit = self.entry_price - self.stop_loss
            self.one_r_profit = self.entry_price + self.risk_per_unit
            self.current_sl = self.stop_loss
            self.highest_profit_price = self.entry_price
            self.lowest_profit_price = self.entry_price
        else:  # SELL
            self.risk_per_unit = self.stop_loss - self.entry_price
            self.one_r_profit = self.entry_price - self.risk_per_unit
            self.current_sl = self.stop_loss
            self.highest_profit_price = self.entry_price
            self.lowest_profit_price = self.entry_price

        if self.risk_per_unit <= 0:
            raise ValueError("Invalid stop loss: risk_per_unit must be positive")

    def update_price(self, current_price: float) -> dict:
        """
        Update TSL state based on current market price.

        Returns a dict with:
        - state: current TSLState
        - sl_updated: bool
        - new_sl: float | None
        - action: str (description of what happened)
        """
        result = {
            "state": self.state,
            "sl_updated": False,
            "new_sl": None,
            "action": "no_change",
        }

        if self.side.upper() == "BUY":
            self.highest_profit_price = max(self.highest_profit_price, current_price)
            self.lowest_profit_price = min(self.lowest_profit_price, current_price)

            # Check 1R profit hit
            if self.state in (TSLState.INACTIVE, TSLState.ARMED):
                if current_price >= self.one_r_profit:
                    self.state = TSLState.BREAKEVEN
                    self.current_sl = self.entry_price
                    self.breakeven_reached_at = datetime.now(IST)
                    result.update({
                        "state": self.state,
                        "sl_updated": True,
                        "new_sl": self.current_sl,
                        "action": "moved_to_breakeven",
                    })
                    logger.info(
                        f"TSL {self.symbol}: Hit 1R, moved SL to breakeven {self.entry_price}"
                    )
                    return result

            # Trailing after breakeven
            if self.state == TSLState.BREAKEVEN:
                # Calculate trail distance
                if self.use_atr and self.atr_value:
                    trail_dist = self.atr_value
                else:
                    trail_dist = self.trail_points

                new_sl = self.highest_profit_price - trail_dist
                if new_sl > self.current_sl:
                    self.current_sl = new_sl
                    self.state = TSLState.TRAILING
                    result.update({
                        "state": self.state,
                        "sl_updated": True,
                        "new_sl": self.current_sl,
                        "action": "trailing_sl_updated",
                    })
                    logger.info(
                        f"TSL {self.symbol}: Trailing SL updated to {self.current_sl}"
                    )

            # Check SL hit
            if current_price <= self.current_sl:
                result["action"] = "sl_hit"

        else:  # SELL
            self.highest_profit_price = max(self.highest_profit_price, current_price)
            self.lowest_profit_price = min(self.lowest_profit_price, current_price)

            if self.state in (TSLState.INACTIVE, TSLState.ARMED):
                if current_price <= self.one_r_profit:
                    self.state = TSLState.BREAKEVEN
                    self.current_sl = self.entry_price
                    self.breakeven_reached_at = datetime.now(IST)
                    result.update({
                        "state": self.state,
                        "sl_updated": True,
                        "new_sl": self.current_sl,
                        "action": "moved_to_breakeven",
                    })
                    logger.info(
                        f"TSL {self.symbol}: Hit 1R, moved SL to breakeven {self.entry_price}"
                    )
                    return result

            if self.state == TSLState.BREAKEVEN:
                if self.use_atr and self.atr_value:
                    trail_dist = self.atr_value
                else:
                    trail_dist = self.trail_points

                new_sl = self.lowest_profit_price + trail_dist
                if new_sl < self.current_sl:
                    self.current_sl = new_sl
                    self.state = TSLState.TRAILING
                    result.update({
                        "state": self.state,
                        "sl_updated": True,
                        "new_sl": self.current_sl,
                        "action": "trailing_sl_updated",
                    })
                    logger.info(
                        f"TSL {self.symbol}: Trailing SL updated to {self.current_sl}"
                    )

            if current_price >= self.current_sl:
                result["action"] = "sl_hit"

        return result

    def is_sl_hit(self, current_price: float) -> bool:
        if self.side.upper() == "BUY":
            return current_price <= self.current_sl
        return current_price >= self.current_sl

    def is_target_hit(self, current_price: float) -> bool:
        if self.side.upper() == "BUY":
            return current_price >= self.target
        return current_price <= self.target

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "quantity": self.quantity,
            "side": self.side,
            "risk_per_unit": self.risk_per_unit,
            "one_r_profit": self.one_r_profit,
            "state": self.state.value,
            "current_sl": self.current_sl,
            "highest_profit_price": self.highest_profit_price,
            "lowest_profit_price": self.lowest_profit_price,
            "breakeven_reached_at": (
                self.breakeven_reached_at.isoformat()
                if self.breakeven_reached_at
                else None
            ),
            "trail_points": self.trail_points,
            "use_atr": self.use_atr,
            "atr_value": self.atr_value,
        }
