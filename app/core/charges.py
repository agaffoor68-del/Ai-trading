"""
Charges & Slippage Engine - Indian Markets (NSE/BSE)

Calculates exact brokerage, taxes, and regulatory charges for Options and Futures.
All charges are per the NSE/Fyers/Fyers-style discount broker model.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class InstrumentType(str, Enum):
    OPTIONS = "OPTIONS"
    FUTURES = "FUTURES"


class TradeSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class ChargeBreakdown:
    brokerage: float = 0.0
    stt: float = 0.0
    exchange_txn_charges: float = 0.0
    sebi_turnover_charges: float = 0.0
    gst: float = 0.0
    stamp_duty: float = 0.0
    slippage: float = 0.0
    total_charges: float = 0.0


class ChargesCalculator:
    """
    Calculates all statutory and broker charges for Indian F&O trades.

    Default rates (Fyers / discount broker model):
    - Brokerage: ₹20 per executed order (flat)
    - STT: Options sell 0.0625% of premium; Futures sell 0.0125% of value
    - Exchange Txn Charges: Futures 0.0032%, Options 0.053%
    - SEBI Turnover: 0.0001% (₹10 per crore)
    - GST: 18% on (brokerage + exchange txn charges)
    - Stamp Duty: Futures 0.002%, Options 0.003%
    - Slippage: 0.5 points per order (configurable)
    """

    def __init__(
        self,
        brokerage_per_order: float = 20.0,
        stt_options_sell_pct: float = 0.0625,
        stt_futures_sell_pct: float = 0.0125,
        exchange_txn_futures_pct: float = 0.0032,
        exchange_txn_options_pct: float = 0.053,
        sebi_turnover_pct: float = 0.0001,
        gst_pct: float = 18.0,
        stamp_duty_futures_pct: float = 0.002,
        stamp_duty_options_pct: float = 0.003,
        slippage_points: float = 0.5,
        lot_size: Optional[int] = None,
    ):
        self.brokerage_per_order = brokerage_per_order
        self.stt_options_sell_pct = stt_options_sell_pct
        self.stt_futures_sell_pct = stt_futures_sell_pct
        self.exchange_txn_futures_pct = exchange_txn_futures_pct
        self.exchange_txn_options_pct = exchange_txn_options_pct
        self.sebi_turnover_pct = sebi_turnover_pct
        self.gst_pct = gst_pct
        self.stamp_duty_futures_pct = stamp_duty_futures_pct
        self.stamp_duty_options_pct = stamp_duty_options_pct
        self.slippage_points = slippage_points
        self.lot_size = lot_size

    def calculate(
        self,
        instrument_type: InstrumentType,
        side: TradeSide,
        price: float,
        quantity: int,
        premium_or_value: Optional[float] = None,
        lot_size: Optional[int] = None,
        slippage_points: Optional[float] = None,
    ) -> ChargeBreakdown:
        """
        Calculate all charges for a single trade leg.

        Args:
            instrument_type: OPTIONS or FUTURES
            side: BUY or SELL
            price: Entry/exit price per unit
            quantity: Number of units (shares/contracts)
            premium_or_value: For options, the premium total (price * qty * lot_size).
                              For futures, the contract value (price * qty * lot_size).
            lot_size: Override lot size for this calculation
            slippage_points: Override slippage in points per order
        """
        ls = lot_size if lot_size is not None else self.lot_size or 1
        total_qty = quantity * ls
        slip = slippage_points if slippage_points is not None else self.slippage_points

        # Notional value
        notional = price * total_qty
        if premium_or_value is not None:
            notional = premium_or_value

        # Brokerage - flat per executed order (buy + sell = 2 orders)
        brokerage = self.brokerage_per_order

        # STT - charged on sell side only
        if side == TradeSide.SELL:
            if instrument_type == InstrumentType.OPTIONS:
                stt = notional * (self.stt_options_sell_pct / 100.0)
            else:
                stt = notional * (self.stt_futures_sell_pct / 100.0)
        else:
            stt = 0.0

        # Exchange Transaction Charges
        if instrument_type == InstrumentType.OPTIONS:
            exchange_txn = notional * (self.exchange_txn_options_pct / 100.0)
        else:
            exchange_txn = notional * (self.exchange_txn_futures_pct / 100.0)

        # SEBI Turnover Charges
        sebi_turnover = notional * (self.sebi_turnover_pct / 100.0)

        # GST - 18% on (brokerage + exchange transaction charges)
        gst = (brokerage + exchange_txn) * (self.gst_pct / 100.0)

        # Stamp Duty - charged on buy side only
        if side == TradeSide.BUY:
            if instrument_type == InstrumentType.OPTIONS:
                stamp_duty = notional * (self.stamp_duty_options_pct / 100.0)
            else:
                stamp_duty = notional * (self.stamp_duty_futures_pct / 100.0)
        else:
            stamp_duty = 0.0

        # Slippage cost in rupees (points * lot_size * quantity)
        slippage_cost = slip * total_qty

        total = (
            brokerage
            + stt
            + exchange_txn
            + sebi_turnover
            + gst
            + stamp_duty
            + slippage_cost
        )

        return ChargeBreakdown(
            brokerage=round(brokerage, 2),
            stt=round(stt, 2),
            exchange_txn_charges=round(exchange_txn, 2),
            sebi_turnover_charges=round(sebi_turnover, 2),
            gst=round(gst, 2),
            stamp_duty=round(stamp_duty, 2),
            slippage=round(slippage_cost, 2),
            total_charges=round(total, 2),
        )

    def calculate_round_trip(
        self,
        instrument_type: InstrumentType,
        entry_price: float,
        exit_price: float,
        quantity: int,
        lot_size: Optional[int] = None,
        slippage_points: Optional[float] = None,
    ) -> dict:
        """
        Calculate total charges for a complete round trip (entry + exit).

        Returns a dict with entry charges, exit charges, and net PnL impact.
        """
        ls = lot_size if lot_size is not None else self.lot_size or 1
        total_qty = quantity * ls

        entry_charges = self.calculate(
            instrument_type=instrument_type,
            side=TradeSide.BUY,
            price=entry_price,
            quantity=quantity,
            lot_size=ls,
            slippage_points=slippage_points,
        )
        exit_charges = self.calculate(
            instrument_type=instrument_type,
            side=TradeSide.SELL,
            price=exit_price,
            quantity=quantity,
            lot_size=ls,
            slippage_points=slippage_points,
        )

        gross_pnl = (exit_price - entry_price) * total_qty
        net_pnl = gross_pnl - entry_charges.total_charges - exit_charges.total_charges

        return {
            "entry_charges": entry_charges,
            "exit_charges": exit_charges,
            "total_charges": round(
                entry_charges.total_charges + exit_charges.total_charges, 2
            ),
            "gross_pnl": round(gross_pnl, 2),
            "net_pnl": round(net_pnl, 2),
            "charges_impact_pct": round(
                (entry_charges.total_charges + exit_charges.total_charges)
                / (entry_price * total_qty)
                * 100,
                4,
            ),
        }
