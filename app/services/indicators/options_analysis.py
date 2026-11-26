"""Options & derivatives analytics (H: 151-169).

All functions read the chain from ``ctx.extras``::

    extras["option_chain"] = {
        "expiry": "2026-01-29",
        "spot": 24500.0,
        "strikes": [
            {"strike": 24500,
             "call": {"oi": 1000, "change_oi": 120, "iv": 0.12, "ltp": 120,
                      "bid": 118, "ask": 122, "delta": 0.5},
             "put":  {...}},
        ],
    }
    extras["iv_history"] = [0.11, 0.12, ...]
    extras["futures_price"], extras["funding_rate"],
    extras["liquidation_levels"] = [24000, 25000]

Missing inputs produce ``data_unavailable`` — never a fabricated number.
Greeks use the Black-Scholes model with a normal CDF; that model assumption is
stated in every note so the UI can show it.
"""

from __future__ import annotations

import math
from typing import Optional

from .series import Series, sma, stdev, to_float

__all__ = [
    "put_call_ratio", "open_interest", "change_in_open_interest",
    "option_chain_analysis", "max_pain", "implied_volatility", "iv_rank",
    "iv_percentile", "delta", "gamma", "theta", "vega", "rho", "gamma_exposure",
    "delta_exposure", "futures_basis", "funding_rate", "liquidation_levels",
    "oi_weighted_price",
]

MODEL = "Black-Scholes (European, no dividends, constant volatility)"


def _env(series: dict, note: Optional[str] = None, meta: Optional[dict] = None) -> dict:
    return {"series": series, "levels": {}, "note": note, "meta": meta or {}}


def _extras(ctx) -> dict:
    return getattr(ctx, "extras", {}) or {}


def _chain(ctx):
    chain = _extras(ctx).get("option_chain")
    if not chain or not chain.get("strikes"):
        return None
    return chain


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _d1_d2(spot: float, strike: float, t: float, r: float, sigma: float):
    if spot <= 0 or strike <= 0 or t <= 0 or sigma <= 0:
        return None, None
    vt = sigma * math.sqrt(t)
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma * sigma) * t) / vt
    return d1, d1 - vt


def black_scholes(spot: float, strike: float, t: float, r: float, sigma: float, kind: str):
    """Return (price, greeks dict) for kind in {'call','put'}."""
    d1, d2 = _d1_d2(spot, strike, t, r, sigma)
    if d1 is None:
        return None, {}
    nd1 = _norm_cdf(d1)
    nd2 = _norm_cdf(d2)
    pdf = _norm_pdf(d1)
    sqrt_t = math.sqrt(t)
    if kind == "call":
        price = spot * nd1 - strike * math.exp(-r * t) * nd2
        delta = nd1
        rho = strike * t * math.exp(-r * t) * nd2 / 100.0
    else:
        price = strike * math.exp(-r * t) * (1 - nd2) - spot * (1 - nd1)
        delta = nd1 - 1.0
        rho = -strike * t * math.exp(-r * t) * (1 - nd2) / 100.0
    gamma = pdf / (spot * sigma * sqrt_t)
    vega = spot * pdf * sqrt_t / 100.0
    theta = (-(spot * pdf * sigma) / (2 * sqrt_t) - r * strike * math.exp(-r * t) * (nd2 if kind == "call" else 1 - nd2)) / 365.0
    return price, {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega, "rho": rho}


def implied_volatility(price: float, spot: float, strike: float, t: float, r: float, kind: str) -> Optional[float]:
    """Newton-Raphson IV with a bisection fallback."""
    if price is None or price <= 0 or spot <= 0 or strike <= 0 or t <= 0:
        return None
    sigma = 0.2
    for _ in range(60):
        model, greeks = black_scholes(spot, strike, t, r, sigma, kind)
        if model is None:
            return None
        diff = model - price
        vega = greeks.get("vega", 0.0) * 100.0
        if abs(diff) < 1e-6:
            return sigma
        if vega < 1e-10:
            break
        sigma -= diff / vega
        if sigma <= 1e-6 or sigma > 5.0:
            break
    low, high = 1e-6, 5.0
    for _ in range(200):
        mid = (low + high) / 2.0
        model, _g = black_scholes(spot, strike, t, r, mid, kind)
        if model is None:
            return None
        if model > price:
            high = mid
        else:
            low = mid
    return (low + high) / 2.0


def _leg(strike_row: dict, side: str) -> dict:
    leg = strike_row.get(side) or {}
    return {
        "strike": strike_row.get("strike"),
        "oi": to_float(leg.get("oi")),
        "change_oi": to_float(leg.get("change_oi")),
        "iv": to_float(leg.get("iv")),
        "ltp": to_float(leg.get("ltp")),
        "bid": to_float(leg.get("bid")),
        "ask": to_float(leg.get("ask")),
        "delta": to_float(leg.get("delta")),
    }


def _rows(ctx):
    chain = _chain(ctx)
    if chain is None:
        return None
    return [
        {"call": _leg(row, "call"), "put": _leg(row, "put")} for row in chain["strikes"]
    ]


# ---------------------------------------------------------------- 151 PCR
def put_call_ratio(ctx, p):
    rows = _rows(ctx)
    if not rows:
        return _env({}, note="data_unavailable")
    field = str(p.get("field", "oi"))
    calls = [r["call"][field] for r in rows if r["call"][field] is not None]
    puts = [r["put"][field] for r in rows if r["put"][field] is not None]
    if not calls or not puts or sum(calls) == 0:
        return _env({}, note="Chain data incomplete")
    value = sum(puts) / sum(calls)
    series: Series = [None] * max(1, len(getattr(ctx, "close", []) or [0]))
    if series:
        series[-1] = value
    return _env({"pcr": series}, meta={"pcr": value, "call_total": sum(calls), "put_total": sum(puts), "field": field})


# ---------------------------------------------------------------- 152/153 OI
def open_interest(ctx, p):
    rows = _rows(ctx)
    if not rows:
        return _env({}, note="data_unavailable")
    total = sum((r["call"]["oi"] or 0) + (r["put"]["oi"] or 0) for r in rows)
    series: Series = [None] * max(1, len(getattr(ctx, "close", []) or [0]))
    if series:
        series[-1] = total
    return _env({"total_oi": series}, meta={"total_oi": total, "by_strike": [{"strike": r["call"]["strike"], "call_oi": r["call"]["oi"], "put_oi": r["put"]["oi"]} for r in rows]})


def change_in_open_interest(ctx, p):
    rows = _rows(ctx)
    if not rows:
        return _env({}, note="data_unavailable")
    ch = [r for r in rows if r["call"]["change_oi"] is not None or r["put"]["change_oi"] is not None]
    if not ch:
        return _env({}, note="data_unavailable")
    total = sum((r["call"]["change_oi"] or 0) + (r["put"]["change_oi"] or 0) for r in rows)
    series: Series = [None] * max(1, len(getattr(ctx, "close", []) or [0]))
    if series:
        series[-1] = total
    return _env(
        {"change_oi": series},
        meta={"total_change_oi": total, "by_strike": [{"strike": r["call"]["strike"], "call": r["call"]["change_oi"], "put": r["put"]["change_oi"]} for r in rows]},
    )


# ---------------------------------------------------------------- 154 Chain analysis
def option_chain_analysis(ctx, p):
    rows = _rows(ctx)
    if not rows:
        return _env({}, note="data_unavailable")
    calls = [r for r in rows if (r["call"]["oi"] or 0) > 0]
    puts = [r for r in rows if (r["put"]["oi"] or 0) > 0]
    max_call = max(calls, key=lambda r: r["call"]["oi"])["call"]["strike"] if calls else None
    max_put = max(puts, key=lambda r: r["put"]["oi"])["put"]["strike"] if puts else None
    return _env(
        {},
        meta={
            "expiry": _extras(ctx).get("option_chain", {}).get("expiry"),
            "max_call_oi_strike": max_call,
            "max_put_oi_strike": max_put,
            "call_oi": sum((r["call"]["oi"] or 0) for r in rows),
            "put_oi": sum((r["put"]["oi"] or 0) for r in rows),
            "strikes": len(rows),
        },
        note="Aggregate OI summary; per-strike detail is returned with open_interest().",
    )


# ---------------------------------------------------------------- 155 Max pain
def max_pain(ctx, p):
    rows = _rows(ctx)
    if not rows:
        return _env({}, note="data_unavailable")
    expiries = [r for r in rows if r["call"]["oi"] is not None and r["put"]["oi"] is not None]
    if not expiries:
        return _env({}, note="Chain data incomplete")
    best = None
    for candidate in [r["call"]["strike"] for r in expiries]:
        pain = 0.0
        for r in expiries:
            strike = r["call"]["strike"]
            if strike is None:
                continue
            if strike > candidate:
                pain += (strike - candidate) * (r["call"]["oi"] or 0)
            elif strike < candidate:
                pain += (candidate - strike) * (r["put"]["oi"] or 0)
        if best is None or pain < best[1]:
            best = (candidate, pain)
    series: Series = [None] * max(1, len(getattr(ctx, "close", []) or [0]))
    if series and best:
        series[-1] = best[0]
    return _env({"max_pain": series}, meta={"max_pain": best[0] if best else None, "total_pain": best[1] if best else None})


# ---------------------------------------------------------------- 156 IV
def implied_volatility_indicator(ctx, p):
    chain = _chain(ctx)
    if chain is None:
        return _env({}, note="data_unavailable")
    spot = to_float(chain.get("spot")) or to_float(_extras(ctx).get("spot"))
    if spot is None:
        return _env({}, note="data_unavailable")
    t = float(p.get("time_to_expiry_years", 30 / 365.0))
    r = float(p.get("risk_free", 0.065))
    atm = min(chain["strikes"], key=lambda row: abs((row.get("strike") or 0) - spot))
    leg = atm.get("call") or {}
    price = to_float(leg.get("ltp"))
    iv = implied_volatility(price, spot, atm.get("strike"), t, r, "call")
    if iv is None and leg.get("iv") is not None:
        iv = to_float(leg.get("iv"))
    series: Series = [None] * max(1, len(getattr(ctx, "close", []) or [0]))
    if series and iv is not None:
        series[-1] = iv
    return _env({"iv": series}, meta={"iv": iv, "strike": atm.get("strike"), "model": MODEL} if iv is not None else {}, note=f"{MODEL}; ATM IV from the option price. Time to expiry assumed {t*365:.0f} days.")


def _iv_history(ctx):
    hist = _extras(ctx).get("iv_history")
    if not hist:
        return None
    return [to_float(v) for v in hist if to_float(v) is not None]


def iv_rank(ctx, p):
    hist = _iv_history(ctx)
    if not hist:
        return _env({}, note="data_unavailable")
    current = implied_volatility_indicator(ctx, p)["meta"].get("iv") or hist[-1]
    lo, hi = min(hist), max(hist)
    value = 0.0 if hi == lo else 100.0 * (current - lo) / (hi - lo)
    series: Series = [None] * max(1, len(getattr(ctx, "close", []) or [0]))
    if series:
        series[-1] = value
    return _env({"iv_rank": series}, meta={"iv_rank": value, "min": lo, "max": hi}, note="IV Rank = position of current IV inside the 52-week (or supplied) high/low range.")


def iv_percentile(ctx, p):
    hist = _iv_history(ctx)
    if not hist:
        return _env({}, note="data_unavailable")
    current = implied_volatility_indicator(ctx, p)["meta"].get("iv") or hist[-1]
    below = sum(1 for v in hist if v <= current)
    value = 100.0 * below / len(hist)
    series: Series = [None] * max(1, len(getattr(ctx, "close", []) or [0]))
    if series:
        series[-1] = value
    return _env({"iv_percentile": series}, meta={"iv_percentile": value, "observations": len(hist)})


# ---------------------------------------------------------------- 159-163 Greeks
def _greeks(ctx, p, side, greek):
    chain = _chain(ctx)
    if chain is None:
        return _env({}, note="data_unavailable")
    spot = to_float(chain.get("spot")) or to_float(_extras(ctx).get("spot"))
    if spot is None:
        return _env({}, note="data_unavailable")
    t = float(p.get("time_to_expiry_years", 30 / 365.0))
    r = float(p.get("risk_free", 0.065))
    rows = []
    for row in chain["strikes"]:
        leg = row.get(side) or {}
        strike = row.get("strike")
        iv = to_float(leg.get("iv"))
        if None in (strike, iv):
            continue
        _price, g = black_scholes(spot, strike, t, r, iv, side)
        if g:
            rows.append({"strike": strike, "iv": iv, **g})
    if not rows:
        return _env({}, note="Chain data incomplete")
    series: Series = [None] * max(1, len(getattr(ctx, "close", []) or [0]))
    if series:
        series[-1] = rows[0].get(greek)
    return _env({greek: series}, meta={"rows": rows, "model": MODEL}, note=f"{MODEL}; per-strike {greek} from supplied IV.")


def delta(ctx, p):
    return _greeks(ctx, p, "call", "delta")


def gamma(ctx, p):
    return _greeks(ctx, p, "call", "gamma")


def theta(ctx, p):
    return _greeks(ctx, p, "call", "theta")


def vega(ctx, p):
    return _greeks(ctx, p, "call", "vega")


def rho(ctx, p):
    return _greeks(ctx, p, "call", "rho")


# ---------------------------------------------------------------- 164/165 Exposure
def gamma_exposure(ctx, p):
    chain = _chain(ctx)
    if chain is None:
        return _env({}, note="data_unavailable")
    spot = to_float(chain.get("spot")) or to_float(_extras(ctx).get("spot"))
    if spot is None:
        return _env({}, note="data_unavailable")
    t = float(p.get("time_to_expiry_years", 30 / 365.0))
    r = float(p.get("risk_free", 0.065))
    by_strike = []
    total = 0.0
    for row in chain["strikes"]:
        strike = row.get("strike")
        gamma_sum = 0.0
        for side in ("call", "put"):
            leg = row.get(side) or {}
            iv = to_float(leg.get("iv"))
            oi = to_float(leg.get("oi"))
            if None in (strike, iv, oi):
                continue
            _price, g = black_scholes(spot, strike, t, r, iv, side)
            if g:
                gamma_sum += g.get("gamma", 0.0) * oi * 100
        if gamma_sum:
            value = gamma_sum * spot * spot * 0.01
            total += value
            by_strike.append({"strike": strike, "gex": value})
    series: Series = [None] * max(1, len(getattr(ctx, "close", []) or [0]))
    if series:
        series[-1] = total
    return _env({"gex": series}, meta={"total_gex": total, "by_strike": by_strike, "model": MODEL})


def delta_exposure(ctx, p):
    chain = _chain(ctx)
    if chain is None:
        return _env({}, note="data_unavailable")
    by_strike = []
    total = 0.0
    for row in chain["strikes"]:
        strike = row.get("strike")
        delta_sum = 0.0
        for side, sign in (("call", 1.0), ("put", -1.0)):
            leg = row.get(side) or {}
            d = to_float(leg.get("delta"))
            oi = to_float(leg.get("oi"))
            if None in (strike, d, oi):
                continue
            delta_sum += sign * d * oi * 100
        if delta_sum:
            total += delta_sum
            by_strike.append({"strike": strike, "dex": delta_sum})
    series: Series = [None] * max(1, len(getattr(ctx, "close", []) or [0]))
    if series:
        series[-1] = total
    return _env({"dex": series}, meta={"total_dex": total, "by_strike": by_strike})


# ---------------------------------------------------------------- 166-169
def futures_basis(ctx, p):
    futures = to_float(_extras(ctx).get("futures_price"))
    spot = to_float(_extras(ctx).get("spot"))
    if futures is None or spot is None:
        return _env({}, note="data_unavailable")
    basis = futures - spot
    series: Series = [None] * max(1, len(getattr(ctx, "close", []) or [0]))
    if series:
        series[-1] = basis
    return _env({"basis": series}, meta={"basis": basis, "basis_pct": 100.0 * basis / spot if spot else None, "futures": futures, "spot": spot})


def funding_rate(ctx, p):
    value = to_float(_extras(ctx).get("funding_rate"))
    if value is None:
        return _env({}, note="data_unavailable")
    series: Series = [None] * max(1, len(getattr(ctx, "close", []) or [0]))
    if series:
        series[-1] = value
    return _env({"funding_rate": series}, meta={"funding_rate": value}, note="Requires perpetual-futures funding data (crypto venues only).")


def liquidation_levels(ctx, p):
    levels = _extras(ctx).get("liquidation_levels")
    if not levels:
        return _env({}, note="data_unavailable")
    parsed = [to_float(v) for v in levels if to_float(v) is not None]
    series: Series = [None] * max(1, len(getattr(ctx, "close", []) or [0]))
    return _env({}, meta={"levels": parsed}, note="Requires exchange liquidation data.")


def oi_weighted_price(ctx, p):
    rows = _rows(ctx)
    if not rows:
        return _env({}, note="data_unavailable")
    num = 0.0
    den = 0.0
    for r in rows:
        strike = r["call"]["strike"]
        for side in ("call", "put"):
            oi = r[side]["oi"]
            if strike is None or oi is None:
                continue
            num += strike * oi
            den += oi
    if den == 0:
        return _env({}, note="Chain data incomplete")
    value = num / den
    series: Series = [None] * max(1, len(getattr(ctx, "close", []) or [0]))
    if series:
        series[-1] = value
    return _env({"oi_weighted_price": series}, meta={"oi_weighted_price": value})
