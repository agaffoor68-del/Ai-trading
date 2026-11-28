"""Options-chain intelligence (Task 3).

Everything here is derived from **broker-provided chain rows**.  The module is
deliberately strict about provenance:

* ``source="broker"``      — the value came from the broker response verbatim;
* ``source="calculated"``  — we derived it (Black-Scholes IV/Greeks, max pain,
  PCR).  Never presented as broker data;
* ``source="unavailable"`` — the input was missing, so the field is ``None``.

No value is ever synthesised to fill a gap.  A missing OI stays missing and the
analysis reports which conclusions it could not draw.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.core.datetime_utils import now_ist

logger = logging.getLogger(__name__)

RISK_FREE_RATE = 0.065  # India 91-day T-bill proxy; documented, not hidden.
TRADING_DAYS = 252
SECONDS_PER_YEAR = 365 * 24 * 3600


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------
def _norm_cdf(x: float) -> float:
    """Standard normal CDF (Abramowitz & Stegun 7.1.26 via erf)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _as_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def years_to_expiry(expiry: date, reference: Optional[datetime] = None) -> float:
    """Calendar time to expiry in years (never negative, never zero-length)."""
    ref = reference or now_ist()
    if isinstance(expiry, datetime):
        expiry = expiry.date()
    expiry_dt = datetime.combine(expiry, datetime.min.time()).replace(tzinfo=ref.tzinfo)
    seconds = (expiry_dt - ref).total_seconds()
    # Expiry-day sessions still carry time value until the close; floor at a
    # small positive fraction so the model stays defined.
    return max(seconds / SECONDS_PER_YEAR, 1.0 / SECONDS_PER_YEAR)


# ---------------------------------------------------------------------------
# Black-Scholes (calculated estimates — labelled as such everywhere)
# ---------------------------------------------------------------------------
def black_scholes(
    spot: float,
    strike: float,
    time_years: float,
    volatility: float,
    rate: float = RISK_FREE_RATE,
    is_call: bool = True,
) -> Dict[str, Optional[float]]:
    """Price and Greeks for a European option.

    Returns ``None`` values when the inputs cannot produce a meaningful result
    (non-positive spot/strike/volatility or no time left).
    """
    if spot <= 0 or strike <= 0 or time_years <= 0 or volatility <= 0:
        return {
            "price": None, "delta": None, "gamma": None,
            "theta": None, "vega": None, "rho": None,
        }

    sqrt_t = math.sqrt(time_years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * volatility ** 2) * time_years) / (volatility * sqrt_t)
    d2 = d1 - volatility * sqrt_t
    discount = math.exp(-rate * time_years)

    if is_call:
        price = spot * _norm_cdf(d1) - strike * discount * _norm_cdf(d2)
        delta = _norm_cdf(d1)
        rho = strike * time_years * discount * _norm_cdf(d2) / 100.0
    else:
        price = strike * discount * _norm_cdf(-d2) - spot * _norm_cdf(-d1)
        delta = _norm_cdf(d1) - 1.0
        rho = -strike * time_years * discount * _norm_cdf(-d2) / 100.0

    gamma = _norm_pdf(d1) / (spot * volatility * sqrt_t)
    vega = spot * _norm_pdf(d1) * sqrt_t / 100.0
    # Theta per calendar day.
    theta_annual = (
        -(spot * _norm_pdf(d1) * volatility) / (2 * sqrt_t)
        - rate * strike * discount * (_norm_cdf(d2) if is_call else -_norm_cdf(-d2))
    )
    theta = theta_annual / 365.0

    return {
        "price": round(price, 4),
        "delta": round(delta, 5),
        "gamma": round(gamma, 7),
        "theta": round(theta, 5),
        "vega": round(vega, 5),
        "rho": round(rho, 5),
    }


def implied_volatility(
    market_price: Optional[float],
    spot: float,
    strike: float,
    time_years: float,
    rate: float = RISK_FREE_RATE,
    is_call: bool = True,
    tolerance: float = 1e-4,
    max_iterations: int = 60,
) -> Optional[float]:
    """Solve for IV by bisection on Black-Scholes price.

    Bisection is used instead of Newton-Raphson because it cannot diverge on
    deep ITM/OTM quotes.  Returns ``None`` when no solution exists in the
    searched band, rather than returning a misleading number.
    """
    if market_price is None or market_price <= 0 or spot <= 0 or strike <= 0:
        return None
    if time_years <= 0:
        return None

    intrinsic = max(0.0, (spot - strike) if is_call else (strike - spot))
    if market_price < intrinsic * 0.98:
        # Below intrinsic: no positive volatility can reproduce this quote.
        return None

    low, high = 0.0001, 5.0
    for _ in range(max_iterations):
        mid = (low + high) / 2.0
        model = black_scholes(spot, strike, time_years, mid, rate, is_call)["price"]
        if model is None:
            return None
        if abs(model - market_price) < tolerance:
            return round(mid, 6)
        if model > market_price:
            high = mid
        else:
            low = mid
    return round((low + high) / 2.0, 6)


# ---------------------------------------------------------------------------
# Chain model
# ---------------------------------------------------------------------------
@dataclass
class OptionLeg:
    """One side of a strike, with per-field provenance."""

    strike: float
    side: str  # CE | PE
    symbol: Optional[str] = None
    ltp: Optional[float] = None
    oi: Optional[float] = None
    oi_change: Optional[float] = None
    volume: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    iv: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    # provenance
    oi_source: str = "unavailable"
    greeks_source: str = "unavailable"
    iv_source: str = "unavailable"

    @property
    def spread(self) -> Optional[float]:
        if self.bid is None or self.ask is None:
            return None
        return round(self.ask - self.bid, 4)

    @property
    def spread_pct(self) -> Optional[float]:
        if self.bid is None or self.ask is None or self.ask <= 0:
            return None
        return round((self.ask - self.bid) / self.ask * 100.0, 3)

    @property
    def is_liquid(self) -> bool:
        """A leg is tradable when it has OI, volume and a tight-enough spread."""
        if self.oi is None or self.oi <= 0:
            return False
        if self.volume is None or self.volume <= 0:
            return False
        if self.spread_pct is not None and self.spread_pct > 5.0:
            return False
        return True

    def as_dict(self) -> Dict[str, Any]:
        return {
            "strike": self.strike,
            "side": self.side,
            "symbol": self.symbol,
            "ltp": self.ltp,
            "oi": self.oi,
            "oi_change": self.oi_change,
            "volume": self.volume,
            "bid": self.bid,
            "ask": self.ask,
            "spread": self.spread,
            "spread_pct": self.spread_pct,
            "iv": self.iv,
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "liquid": self.is_liquid,
            "source": {
                "oi": self.oi_source,
                "iv": self.iv_source,
                "greeks": self.greeks_source,
            },
        }


@dataclass
class StrikeRow:
    strike: float
    call: Optional[OptionLeg] = None
    put: Optional[OptionLeg] = None
    is_atm: bool = False

    @property
    def call_itm(self) -> bool:
        return False  # filled by the analyzer, which knows the spot

    def as_dict(self, spot: Optional[float] = None) -> Dict[str, Any]:
        call_itm = spot is not None and self.strike < spot
        put_itm = spot is not None and self.strike > spot
        return {
            "strike": self.strike,
            "is_atm": self.is_atm,
            "call_itm": call_itm,
            "put_itm": put_itm,
            "call": self.call.as_dict() if self.call else None,
            "put": self.put.as_dict() if self.put else None,
            "call_oi": self.call.oi if self.call else None,
            "put_oi": self.put.oi if self.put else None,
        }


# ---------------------------------------------------------------------------
# Chain construction
# ---------------------------------------------------------------------------
def _leg_from_quote(
    strike: float,
    side: str,
    quote: Optional[Dict[str, Any]],
    spot: float,
    time_years: float,
    rate: float = RISK_FREE_RATE,
) -> Optional[OptionLeg]:
    """Build a leg, marking every field's provenance honestly."""
    if not quote:
        return None

    is_call = side == "CE"
    leg = OptionLeg(strike=strike, side=side, symbol=quote.get("symbol"))
    leg.ltp = _as_float(quote.get("ltp"))

    oi = _as_float(quote.get("oi"))
    if oi is not None:
        leg.oi = oi
        leg.oi_source = "broker"
    oi_change = _as_float(quote.get("oi_change"))
    if oi_change is None and oi is not None:
        previous = _as_float(quote.get("prev_oi"))
        if previous is not None:
            oi_change = oi - previous
    if oi_change is not None:
        leg.oi_change = oi_change

    leg.volume = _as_float(quote.get("volume"))
    leg.bid = _as_float(quote.get("bid"))
    leg.ask = _as_float(quote.get("ask"))

    # Broker IV/Greeks first — only if the broker actually sent them.
    broker_iv = _as_float(quote.get("iv"))
    if broker_iv is not None and broker_iv > 0:
        # Fyers-style feeds sometimes send IV as a percentage.
        leg.iv = broker_iv / 100.0 if broker_iv > 3.0 else broker_iv
        leg.iv_source = "broker"

    broker_greeks = quote.get("greeks") if isinstance(quote.get("greeks"), dict) else {}
    for name in ("delta", "gamma", "theta", "vega"):
        value = _as_float(quote.get(name)) or _as_float(broker_greeks.get(name))
        if value is not None:
            setattr(leg, name, value)
            leg.greeks_source = "broker"

    # Fall back to calculated values, clearly labelled.
    if leg.iv is None and leg.ltp and leg.ltp > 0:
        solved = implied_volatility(leg.ltp, spot, strike, time_years, rate, is_call)
        if solved is not None:
            leg.iv = solved
            leg.iv_source = "calculated"

    if leg.greeks_source != "broker" and leg.iv and leg.iv > 0:
        model = black_scholes(spot, strike, time_years, leg.iv, rate, is_call)
        leg.delta = model["delta"]
        leg.gamma = model["gamma"]
        leg.theta = model["theta"]
        leg.vega = model["vega"]
        if any(v is not None for v in (leg.delta, leg.gamma, leg.theta, leg.vega)):
            leg.greeks_source = "calculated"

    return leg


def build_chain(
    rows: Iterable[Dict[str, Any]],
    spot: float,
    expiry: date,
    reference: Optional[datetime] = None,
    rate: float = RISK_FREE_RATE,
    atm_strike: Optional[float] = None,
) -> List[StrikeRow]:
    """Turn raw chain rows into ``StrikeRow`` objects.

    Each row is ``{"strike": float, "call": quote|None, "put": quote|None}``
    (the shape produced by the options endpoint) or the flattened
    ``call_symbol``/``put_symbol`` form; both are accepted.
    """
    time_years = years_to_expiry(expiry, reference)
    strikes: Dict[float, StrikeRow] = {}

    for row in rows or []:
        strike = _as_float(row.get("strike") or row.get("strike_price"))
        if strike is None or strike <= 0:
            continue
        entry = strikes.setdefault(strike, StrikeRow(strike=strike))

        call_quote = row.get("call") if isinstance(row.get("call"), dict) else None
        put_quote = row.get("put") if isinstance(row.get("put"), dict) else None

        # Flattened shape: only an LTP per side was supplied.
        if call_quote is None and row.get("call_ltp") is not None:
            call_quote = {"symbol": row.get("call_symbol"), "ltp": row.get("call_ltp")}
        if put_quote is None and row.get("put_ltp") is not None:
            put_quote = {"symbol": row.get("put_symbol"), "ltp": row.get("put_ltp")}

        entry.call = _leg_from_quote(strike, "CE", call_quote, spot, time_years, rate)
        entry.put = _leg_from_quote(strike, "PE", put_quote, spot, time_years, rate)

    if atm_strike is None and spot > 0:
        atm_strike = min(strikes, key=lambda s: abs(s - spot)) if strikes else None

    for strike, entry in strikes.items():
        entry.is_atm = atm_strike is not None and strike == atm_strike

    return [strikes[s] for s in sorted(strikes)]


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
def max_pain(chain: Sequence[StrikeRow]) -> Optional[float]:
    """Strike at which option writers' total payout is minimised.

    Computed over strikes that actually carry OI.  Returns ``None`` when no
    strike has usable OI (rather than inventing a level).
    """
    strikes = [row.strike for row in chain]
    if not strikes:
        return None
    has_oi = any(
        (row.call and row.call.oi) or (row.put and row.put.oi) for row in chain
    )
    if not has_oi:
        return None

    best_strike: Optional[float] = None
    best_pain = math.inf
    for candidate in strikes:
        pain = 0.0
        for row in chain:
            call_oi = (row.call.oi or 0.0) if row.call else 0.0
            put_oi = (row.put.oi or 0.0) if row.put else 0.0
            if call_oi:
                pain += max(0.0, candidate - row.strike) * call_oi
            if put_oi:
                pain += max(0.0, row.strike - candidate) * put_oi
        if pain < best_pain:
            best_pain = pain
            best_strike = candidate
    return best_strike


def put_call_ratio(chain: Sequence[StrikeRow], use_volume: bool = False) -> Optional[float]:
    """Total put / total call, by OI or by volume. ``None`` when unavailable."""
    calls = 0.0
    puts = 0.0
    for row in chain:
        for leg, is_call in ((row.call, True), (row.put, False)):
            if leg is None:
                continue
            value = leg.volume if use_volume else leg.oi
            if value is None:
                continue
            if is_call:
                calls += value
            else:
                puts += value
    if calls <= 0:
        return None
    return round(puts / calls, 4)


def oi_walls(
    chain: Sequence[StrikeRow], top_n: int = 3
) -> Dict[str, List[Dict[str, Any]]]:
    """Highest-OI strikes: call walls act as resistance, put walls as support."""
    call_rows = [
        {"strike": row.strike, "oi": row.call.oi, "oi_change": row.call.oi_change}
        for row in chain
        if row.call and row.call.oi
    ]
    put_rows = [
        {"strike": row.strike, "oi": row.put.oi, "oi_change": row.put.oi_change}
        for row in chain
        if row.put and row.put.oi
    ]
    call_rows.sort(key=lambda r: r["oi"], reverse=True)
    put_rows.sort(key=lambda r: r["oi"], reverse=True)
    return {"resistance": call_rows[:top_n], "support": put_rows[:top_n]}


def classify_buildup(leg: Optional[OptionLeg], price_change: Optional[float]) -> str:
    """OI/price build-up label for one leg.

    Standard four-way classification.  Returns ``unknown`` when either input is
    missing — a build-up cannot be inferred from one side alone.
    """
    if leg is None or leg.oi_change is None or price_change is None:
        return "unknown"
    if leg.oi_change > 0 and price_change > 0:
        return "long_buildup"
    if leg.oi_change > 0 and price_change < 0:
        return "short_buildup"
    if leg.oi_change < 0 and price_change > 0:
        return "short_covering"
    if leg.oi_change < 0 and price_change < 0:
        return "long_unwinding"
    return "flat"


@dataclass
class OptionsIntelligence:
    """Aggregate read of one expiry's chain."""

    symbol: str
    expiry: str
    spot: float
    atm_strike: Optional[float]
    timestamp: str
    chain: List[StrikeRow] = field(default_factory=list)
    pcr_oi: Optional[float] = None
    pcr_volume: Optional[float] = None
    total_call_oi: Optional[float] = None
    total_put_oi: Optional[float] = None
    total_call_volume: Optional[float] = None
    total_put_volume: Optional[float] = None
    max_pain: Optional[float] = None
    atm_iv: Optional[float] = None
    atm_iv_source: str = "unavailable"
    expected_move: Optional[float] = None
    support: List[Dict[str, Any]] = field(default_factory=list)
    resistance: List[Dict[str, Any]] = field(default_factory=list)
    bias: str = "neutral"
    bias_reason: str = ""
    liquid_strikes: int = 0
    warnings: List[str] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return bool(self.chain) and self.pcr_oi is not None

    def as_dict(self, include_chain: bool = True) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "symbol": self.symbol,
            "expiry": self.expiry,
            "spot": self.spot,
            "atm_strike": self.atm_strike,
            "timestamp": self.timestamp,
            "available": self.available,
            "pcr_oi": self.pcr_oi,
            "pcr_volume": self.pcr_volume,
            "total_call_oi": self.total_call_oi,
            "total_put_oi": self.total_put_oi,
            "total_call_volume": self.total_call_volume,
            "total_put_volume": self.total_put_volume,
            "max_pain": self.max_pain,
            "atm_iv": self.atm_iv,
            "atm_iv_source": self.atm_iv_source,
            "expected_move": self.expected_move,
            "support": self.support,
            "resistance": self.resistance,
            "bias": self.bias,
            "bias_reason": self.bias_reason,
            "liquid_strikes": self.liquid_strikes,
            "warnings": self.warnings,
        }
        if include_chain:
            payload["chain"] = [row.as_dict(self.spot) for row in self.chain]
        return payload


def analyze_chain(
    symbol: str,
    rows: Iterable[Dict[str, Any]],
    spot: float,
    expiry: date,
    reference: Optional[datetime] = None,
    atm_strike: Optional[float] = None,
    rate: float = RISK_FREE_RATE,
) -> OptionsIntelligence:
    """Full intelligence pass over one expiry's chain."""
    ref = reference or now_ist()
    chain = build_chain(rows, spot, expiry, ref, rate, atm_strike)

    result = OptionsIntelligence(
        symbol=symbol,
        expiry=expiry.isoformat(),
        spot=spot,
        atm_strike=atm_strike,
        timestamp=ref.isoformat(),
        chain=chain,
    )

    if not chain:
        result.warnings.append("broker returned no chain rows for this expiry")
        result.bias_reason = "no options data"
        return result

    result.pcr_oi = put_call_ratio(chain, use_volume=False)
    result.pcr_volume = put_call_ratio(chain, use_volume=True)
    result.max_pain = max_pain(chain)

    call_oi = sum(row.call.oi for row in chain if row.call and row.call.oi)
    put_oi = sum(row.put.oi for row in chain if row.put and row.put.oi)
    result.total_call_oi = round(call_oi, 0) if call_oi else None
    result.total_put_oi = round(put_oi, 0) if put_oi else None

    call_vol = sum(row.call.volume for row in chain if row.call and row.call.volume)
    put_vol = sum(row.put.volume for row in chain if row.put and row.put.volume)
    result.total_call_volume = round(call_vol, 0) if call_vol else None
    result.total_put_volume = round(put_vol, 0) if put_vol else None

    walls = oi_walls(chain)
    result.support = walls["support"]
    result.resistance = walls["resistance"]
    result.liquid_strikes = sum(
        1 for row in chain if (row.call and row.call.is_liquid) or (row.put and row.put.is_liquid)
    )

    # ATM implied volatility — prefer broker, else calculated, else unavailable.
    atm_row = next((row for row in chain if row.is_atm), None)
    if atm_row:
        for leg in (atm_row.call, atm_row.put):
            if leg and leg.iv is not None:
                result.atm_iv = round(leg.iv, 5)
                result.atm_iv_source = leg.iv_source
                break
        if result.atm_iv is not None:
            result.expected_move = round(spot * result.atm_iv, 2)

    if result.pcr_oi is None:
        result.warnings.append("open interest unavailable from broker — PCR and max pain not computed")
    if result.atm_iv is None:
        result.warnings.append("implied volatility unavailable for the ATM strike")
    if result.liquid_strikes == 0:
        result.warnings.append("no strike passed the liquidity filter (OI + volume + spread)")

    result.bias, result.bias_reason = _options_bias(result, spot)
    return result


def _options_bias(result: OptionsIntelligence, spot: float) -> Tuple[str, str]:
    """Directional read from positioning, with the evidence spelled out."""
    reasons: List[str] = []
    score = 0.0

    if result.pcr_oi is not None:
        if result.pcr_oi > 1.2:
            score += 1.0
            reasons.append(f"PCR {result.pcr_oi:.2f} (put-heavy, supportive)")
        elif result.pcr_oi < 0.7:
            score -= 1.0
            reasons.append(f"PCR {result.pcr_oi:.2f} (call-heavy, resistance)")

    if result.max_pain is not None and spot > 0:
        gap_pct = (result.max_pain - spot) / spot * 100.0
        if gap_pct > 0.3:
            score += 0.5
            reasons.append(f"max pain {result.max_pain:g} above spot ({gap_pct:+.2f}%)")
        elif gap_pct < -0.3:
            score -= 0.5
            reasons.append(f"max pain {result.max_pain:g} below spot ({gap_pct:+.2f}%)")

    if result.support and result.resistance and spot > 0:
        nearest_support = max((s["strike"] for s in result.support if s["strike"] <= spot), default=None)
        nearest_resistance = min(
            (r["strike"] for r in result.resistance if r["strike"] >= spot), default=None
        )
        if nearest_support is not None and nearest_resistance is not None:
            to_support = spot - nearest_support
            to_resistance = nearest_resistance - spot
            if to_resistance > to_support * 1.5:
                score += 0.5
                reasons.append(
                    f"more room to resistance {nearest_resistance:g} than support {nearest_support:g}"
                )
            elif to_support > to_resistance * 1.5:
                score -= 0.5
                reasons.append(
                    f"more room to support {nearest_support:g} than resistance {nearest_resistance:g}"
                )

    if not reasons:
        return "neutral", "no directional signal from OI/PCR/max pain"

    if score >= 1.0:
        return "bullish", "; ".join(reasons)
    if score <= -1.0:
        return "bearish", "; ".join(reasons)
    return "neutral", "; ".join(reasons)


__all__ = [
    "OptionLeg",
    "OptionsIntelligence",
    "RISK_FREE_RATE",
    "StrikeRow",
    "analyze_chain",
    "black_scholes",
    "build_chain",
    "classify_buildup",
    "implied_volatility",
    "max_pain",
    "oi_walls",
    "put_call_ratio",
    "years_to_expiry",
]
