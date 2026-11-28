"""Tests for options-chain intelligence (Task 3).

Fixtures are hand-built chain rows representing a plausible NSE expiry.  They
are test inputs, not market data, and no test asserts on live prices.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import pytest

from app.core import market_time as mt
from app.services import options_intelligence as oi


SPOT = 22000.0
EXPIRY = date(2099, 1, 29)  # far future keeps time-to-expiry positive


def make_rows(spot: float = SPOT, strikes: list[float] | None = None) -> list[dict]:
    """Build a symmetric-ish chain around ``spot`` with realistic OI."""
    strikes = strikes or [spot + (i - 5) * 50 for i in range(11)]
    rows = []
    for strike in strikes:
        distance = abs(strike - spot) / spot
        # OI peaks a few strikes away from ATM, as in a real chain.
        call_oi = max(1000.0, 200_000 * (1 - distance * 12))
        put_oi = max(1000.0, 240_000 * (1 - distance * 12))
        call_ltp = max(2.0, (spot - strike) + 120 * math.exp(-distance * 25))
        put_ltp = max(2.0, (strike - spot) + 120 * math.exp(-distance * 25))
        rows.append(
            {
                "strike": strike,
                "call": {
                    "symbol": f"NSE:NIFTY{strike:g}CE",
                    "ltp": round(call_ltp, 2),
                    "oi": round(call_oi),
                    "oi_change": 1500.0,
                    "volume": 50_000.0,
                    "bid": round(call_ltp - 0.5, 2),
                    "ask": round(call_ltp + 0.5, 2),
                },
                "put": {
                    "symbol": f"NSE:NIFTY{strike:g}PE",
                    "ltp": round(put_ltp, 2),
                    "oi": round(put_oi),
                    "oi_change": -800.0,
                    "volume": 60_000.0,
                    "bid": round(put_ltp - 0.5, 2),
                    "ask": round(put_ltp + 0.5, 2),
                },
            }
        )
    return rows


# ------------------------------------------------------------ Black-Scholes
def test_black_scholes_call_put_parity():
    call = oi.black_scholes(22000, 22000, 0.05, 0.15, 0.065, is_call=True)
    put = oi.black_scholes(22000, 22000, 0.05, 0.15, 0.065, is_call=False)

    # Put-call parity: C - P = S - K*e^(-rT)
    expected = 22000 - 22000 * math.exp(-0.065 * 0.05)
    assert call["price"] is not None and put["price"] is not None
    assert call["price"] - put["price"] == pytest.approx(expected, abs=1e-2)


def test_black_scholes_greeks_have_expected_signs():
    call = oi.black_scholes(22000, 22000, 0.05, 0.15, is_call=True)
    put = oi.black_scholes(22000, 22000, 0.05, 0.15, is_call=False)

    assert 0 < call["delta"] < 1
    assert -1 < put["delta"] < 0
    assert call["gamma"] > 0 and put["gamma"] > 0
    assert call["theta"] < 0  # long options decay
    assert call["vega"] > 0


def test_black_scholes_returns_none_for_invalid_input():
    result = oi.black_scholes(0, 22000, 0.05, 0.15)

    assert result["price"] is None
    assert result["delta"] is None


def test_implied_volatility_round_trips():
    price = oi.black_scholes(22000, 22000, 0.05, 0.18, is_call=True)["price"]

    solved = oi.implied_volatility(price, 22000, 22000, 0.05, is_call=True)

    assert solved == pytest.approx(0.18, abs=1e-3)


def test_implied_volatility_returns_none_below_intrinsic():
    # A call worth far less than its intrinsic value has no valid IV.
    assert oi.implied_volatility(5.0, 23000, 22000, 0.05, is_call=True) is None


def test_implied_volatility_returns_none_without_price():
    assert oi.implied_volatility(None, 22000, 22000, 0.05) is None
    assert oi.implied_volatility(0.0, 22000, 22000, 0.05) is None


# ---------------------------------------------------------------- chain build
def test_build_chain_marks_atm_and_itm():
    chain = oi.build_chain(make_rows(), SPOT, EXPIRY, reference=datetime.now(mt.IST))

    atm = [row for row in chain if row.is_atm]
    assert len(atm) == 1
    assert atm[0].strike == SPOT

    row = chain[0].as_dict(SPOT)
    assert row["call_itm"] is True  # lowest strike is ITM for a call
    assert row["put_itm"] is False


def test_build_chain_provenance_is_honest():
    chain = oi.build_chain(make_rows(), SPOT, EXPIRY, reference=datetime.now(mt.IST))
    leg = chain[0].call

    assert leg.oi_source == "broker"
    # No broker IV was supplied, so it must be marked calculated (or unavailable).
    assert leg.iv_source in ("calculated", "unavailable")
    assert leg.greeks_source in ("calculated", "unavailable")


def test_broker_greeks_are_not_overwritten_by_estimates():
    rows = [
        {
            "strike": 22000.0,
            "call": {
                "ltp": 120.0, "oi": 1000.0, "volume": 500.0,
                "iv": 0.14, "delta": 0.51, "gamma": 0.00012,
                "theta": -8.5, "vega": 12.0,
            },
        }
    ]
    chain = oi.build_chain(rows, SPOT, EXPIRY, reference=datetime.now(mt.IST))
    leg = chain[0].call

    assert leg.greeks_source == "broker"
    assert leg.iv_source == "broker"
    assert leg.delta == 0.51
    assert leg.theta == -8.5


def test_missing_oi_is_marked_unavailable_not_zero():
    rows = [{"strike": 22000.0, "call": {"ltp": 120.0}}]
    chain = oi.build_chain(rows, SPOT, EXPIRY, reference=datetime.now(mt.IST))
    leg = chain[0].call

    assert leg.oi is None
    assert leg.oi_source == "unavailable"


def test_flat_chain_rows_are_accepted():
    rows = [{"strike_price": 22000.0, "call_ltp": 120.0, "put_ltp": 110.0}]
    chain = oi.build_chain(rows, SPOT, EXPIRY, reference=datetime.now(mt.IST))

    assert chain[0].call.ltp == 120.0
    assert chain[0].put.ltp == 110.0


def test_leg_spread_and_liquidity():
    rows = [
        {
            "strike": 22000.0,
            "call": {"ltp": 120.0, "oi": 5000.0, "volume": 900.0,
                     "bid": 119.5, "ask": 120.5},
        }
    ]
    chain = oi.build_chain(rows, SPOT, EXPIRY, reference=datetime.now(mt.IST))
    leg = chain[0].call

    assert leg.spread == pytest.approx(1.0)
    assert leg.spread_pct is not None
    assert leg.is_liquid is True


def test_leg_without_oi_is_not_liquid():
    rows = [{"strike": 22000.0, "call": {"ltp": 120.0, "volume": 900.0}}]
    chain = oi.build_chain(rows, SPOT, EXPIRY, reference=datetime.now(mt.IST))

    assert chain[0].call.is_liquid is False


# ------------------------------------------------------------------ analytics
def test_put_call_ratio_from_oi():
    chain = oi.build_chain(make_rows(), SPOT, EXPIRY, reference=datetime.now(mt.IST))

    pcr = oi.put_call_ratio(chain)

    assert pcr is not None
    assert pcr > 1.0  # fixture has heavier put OI


def test_put_call_ratio_none_without_oi():
    rows = [{"strike": 22000.0, "call": {"ltp": 100.0}, "put": {"ltp": 90.0}}]
    chain = oi.build_chain(rows, SPOT, EXPIRY, reference=datetime.now(mt.IST))

    assert oi.put_call_ratio(chain) is None


def test_max_pain_is_inside_the_strike_range():
    chain = oi.build_chain(make_rows(), SPOT, EXPIRY, reference=datetime.now(mt.IST))

    pain = oi.max_pain(chain)

    assert pain is not None
    assert min(r.strike for r in chain) <= pain <= max(r.strike for r in chain)


def test_max_pain_none_without_oi():
    rows = [{"strike": 22000.0, "call": {"ltp": 100.0}, "put": {"ltp": 90.0}}]
    chain = oi.build_chain(rows, SPOT, EXPIRY, reference=datetime.now(mt.IST))

    assert oi.max_pain(chain) is None


def test_oi_walls_identify_support_and_resistance():
    chain = oi.build_chain(make_rows(), SPOT, EXPIRY, reference=datetime.now(mt.IST))

    walls = oi.oi_walls(chain)

    assert walls["support"] and walls["resistance"]
    assert all(w["oi"] > 0 for w in walls["support"])


def test_classify_buildup_matrix():
    def leg(change: float) -> oi.OptionLeg:
        return oi.OptionLeg(strike=22000, side="CE", oi_change=change)

    assert oi.classify_buildup(leg(100), 5) == "long_buildup"
    assert oi.classify_buildup(leg(100), -5) == "short_buildup"
    assert oi.classify_buildup(leg(-100), 5) == "short_covering"
    assert oi.classify_buildup(leg(-100), -5) == "long_unwinding"
    assert oi.classify_buildup(leg(0), 5) == "flat"
    assert oi.classify_buildup(None, 5) == "unknown"
    assert oi.classify_buildup(leg(100), None) == "unknown"


# -------------------------------------------------------------- full analysis
def test_analyze_chain_populates_core_metrics():
    result = oi.analyze_chain(
        "NIFTY", make_rows(), SPOT, EXPIRY, reference=datetime.now(mt.IST)
    )

    assert result.available is True
    assert result.pcr_oi is not None
    assert result.max_pain is not None
    assert result.total_call_oi is not None
    assert result.total_put_oi is not None
    assert result.support and result.resistance
    assert result.atm_strike is None or isinstance(result.atm_strike, float)
    assert result.bias in ("bullish", "bearish", "neutral")
    assert result.bias_reason


def test_analyze_chain_reports_unavailable_fields():
    rows = [{"strike": 22000.0, "call": {"ltp": 120.0}, "put": {"ltp": 110.0}}]

    result = oi.analyze_chain("NIFTY", rows, SPOT, EXPIRY, reference=datetime.now(mt.IST))

    assert result.pcr_oi is None
    assert result.max_pain is None
    assert any("open interest unavailable" in w for w in result.warnings)


def test_analyze_chain_with_no_rows_is_unavailable():
    result = oi.analyze_chain("NIFTY", [], SPOT, EXPIRY, reference=datetime.now(mt.IST))

    assert result.available is False
    assert result.warnings
    assert result.bias == "neutral"


def test_analysis_serialises_to_json():
    import json

    result = oi.analyze_chain(
        "NIFTY", make_rows(), SPOT, EXPIRY, reference=datetime.now(mt.IST)
    )

    payload = result.as_dict()
    json.dumps(payload)  # must not raise
    assert "chain" in payload
    assert "pcr_oi" in payload


def test_expected_move_uses_atm_iv():
    result = oi.analyze_chain(
        "NIFTY", make_rows(), SPOT, EXPIRY, reference=datetime.now(mt.IST)
    )

    if result.atm_iv is not None:
        assert result.expected_move == pytest.approx(SPOT * result.atm_iv, rel=1e-6)


def test_years_to_expiry_is_positive_on_expiry_day():
    today = datetime.now(mt.IST)
    years = oi.years_to_expiry(today.date(), reference=today)

    assert years > 0
