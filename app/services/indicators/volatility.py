"""Volatility indicators (C: 51-70).

``ctx.extras`` may carry provider-supplied series that cannot be derived from
OHLCV (for example ``vix`` / ``india_vix``).  When the series is missing the
indicator returns a ``data_unavailable`` note instead of inventing a value.
"""

from __future__ import annotations

import math
from typing import Optional

from .series import (
    Series,
    atr,
    change,
    highest,
    lowest,
    pct_change,
    rma,
    sma,
    stdev,
    to_float,
    true_range,
    variance,
)

__all__ = [
    "bollinger", "atr_", "keltner", "donchian", "standard_deviation",
    "historical_volatility", "chaikin_volatility", "bollinger_bandwidth",
    "atr_percent", "ulcer_index", "choppiness", "mass_index", "vix",
    "india_vix", "volatility_stop", "acceleration_bands",
    "fractal_chaos_bands", "garch_volatility", "normalized_atr", "starc_bands",
]


def _env(series: dict, note: Optional[str] = None, levels: Optional[dict] = None) -> dict:
    return {"series": series, "levels": levels or {}, "note": note}


def _close(ctx) -> Series:
    return [to_float(v) for v in ctx.close]


def _high(ctx) -> Series:
    return [to_float(v) for v in ctx.high]


def _low(ctx) -> Series:
    return [to_float(v) for v in ctx.low]


def _unavailable(name: str) -> dict:
    return _env({name: [None] * 0}, note="data_unavailable")


def _series_or_none(ctx, key: str):
    extras = getattr(ctx, "extras", {}) or {}
    values = extras.get(key)
    if values is None:
        return None
    if isinstance(values, (int, float)) and not isinstance(values, bool):
        # a single observation (e.g. spot VIX) is placed on the last bar
        series = [None] * max(1, len(getattr(ctx, "close", []) or [0]))
        if series:
            series[-1] = float(values)
        return series
    if not values:
        return None
    return [to_float(v) for v in values]


# ---------------------------------------------------------------- 51 Bollinger
def bollinger(ctx, p):
    period = int(p.get("period", 20))
    mult = float(p.get("multiplier", 2.0))
    close = _close(ctx)
    mid = sma(close, period)
    sd = stdev(close, period)
    upper = [None if m is None or s is None else m + mult * s for m, s in zip(mid, sd)]
    lower = [None if m is None or s is None else m - mult * s for m, s in zip(mid, sd)]
    return _env({"middle": mid}, levels={"upper": upper, "lower": lower})


# ---------------------------------------------------------------- 52 ATR
def atr_(ctx, p):
    return _env({"atr": atr(_high(ctx), _low(ctx), _close(ctx), int(p.get("period", 14)))})


# ---------------------------------------------------------------- 53 Keltner
def keltner(ctx, p):
    period = int(p.get("period", 20))
    mult = float(p.get("multiplier", 2.0))
    close = _close(ctx)
    mid = ema_or_sma(ctx, period)
    atrs = atr(_high(ctx), _low(ctx), close, period)
    upper = [None if m is None or a is None else m + mult * a for m, a in zip(mid, atrs)]
    lower = [None if m is None or a is None else m - mult * a for m, a in zip(mid, atrs)]
    return _env({"middle": mid}, levels={"upper": upper, "lower": lower})


def ema_or_sma(ctx, period):
    from .series import ema

    return ema(_close(ctx), period)


# ---------------------------------------------------------------- 54 Donchian
def donchian(ctx, p):
    period = int(p.get("period", 20))
    high = _high(ctx)
    low = _low(ctx)
    upper = highest(high, period)
    lower = lowest(low, period)
    mid = [None if u is None or l is None else (u + l) / 2.0 for u, l in zip(upper, lower)]
    return _env({"middle": mid}, levels={"upper": upper, "lower": lower})


# ---------------------------------------------------------------- 55 Std Dev
def standard_deviation(ctx, p):
    return _env({"stddev": stdev(_close(ctx), int(p.get("period", 20)))})


# ---------------------------------------------------------------- 56 Historical Volatility
def historical_volatility(ctx, p):
    period = int(p.get("period", 20))
    annual = float(p.get("annualization", 252))
    close = _close(ctx)
    returns = pct_change(close, 1)
    sd = stdev(returns, period)
    scale = math.sqrt(annual)
    out = [None if s is None else s * scale for s in sd]
    return _env({"historical_volatility": out}, note=f"Annualised with sqrt({int(annual)}); input is daily/simple returns.")


# ---------------------------------------------------------------- 57 Chaikin Volatility
def chaikin_volatility(ctx, p):
    period = int(p.get("period", 10))
    smooth = int(p.get("smooth", 10))
    close = _close(ctx)
    diff = [
        None if a is None or b is None or b == 0 else (a - b) / b * 100.0
        for a, b in zip(close, [None] + close[:-1])
    ]
    ema_diff = _ema(diff, smooth)
    out: Series = [
        None if a is None or b is None or b == 0 else (a - b) / b * 100.0
        for a, b in zip(ema_diff, [None] + ema_diff[:-1])
    ]
    return _env({"chaikin_volatility": out})


def _ema(values: Series, period: int) -> Series:
    from .series import ema

    return ema(values, period)


# ---------------------------------------------------------------- 58 BB Width
def bollinger_bandwidth(ctx, p):
    period = int(p.get("period", 20))
    mult = float(p.get("multiplier", 2.0))
    close = _close(ctx)
    mid = sma(close, period)
    sd = stdev(close, period)
    out: Series = []
    for m, s in zip(mid, sd):
        if m in (None, 0) or s is None:
            out.append(None)
        else:
            out.append(100.0 * (2 * mult * s) / m)
    return _env({"bandwidth": out})


# ---------------------------------------------------------------- 59 ATR Percent
def atr_percent(ctx, p):
    period = int(p.get("period", 14))
    close = _close(ctx)
    atrs = atr(_high(ctx), _low(ctx), close, period)
    out = [None if a is None or c in (None, 0) else 100.0 * a / c for a, c in zip(atrs, close)]
    return _env({"atr_percent": out})


# ---------------------------------------------------------------- 60 Ulcer Index
def ulcer_index(ctx, p):
    period = int(p.get("period", 14))
    close = _close(ctx)
    out: Series = [None] * len(close)
    for i in range(period - 1, len(close)):
        window = close[i + 1 - period : i + 1]
        if any(v is None for v in window):
            continue
        peak = max(window)
        if peak <= 0:
            continue
        sq = sum(((peak - v) / peak * 100.0) ** 2 for v in window) / period
        out[i] = math.sqrt(sq)
    return _env({"ulcer_index": out})


# ---------------------------------------------------------------- 61 Choppiness
def choppiness(ctx, p):
    period = int(p.get("period", 14))
    high = _high(ctx)
    low = _low(ctx)
    close = _close(ctx)
    tr_sum = sma(true_range(high, low, close), period)
    hh = highest(high, period)
    ll = lowest(low, period)
    out: Series = []
    for t, h, l in zip(tr_sum, hh, ll):
        if None in (t, h, l) or (h - l) == 0 or t == 0:
            out.append(None)
        else:
            out.append(100.0 * math.log10(t / (h - l)) / math.log10(period))
    return _env({"choppiness": out})


# ---------------------------------------------------------------- 62 Mass Index
def mass_index(ctx, p):
    period = int(p.get("period", 9))
    smooth = int(p.get("smooth", 9))
    high = _high(ctx)
    low = _low(ctx)
    ratio: Series = [
        None if h is None or l is None or l == 0 else h / l for h, l in zip(high, low)
    ]
    ema1 = _ema(ratio, period)
    ema2 = _ema(ema1, period)
    div: Series = [None if a is None or b in (None, 0) else a / b for a, b in zip(ema1, ema2)]
    out = sma(div, smooth)
    return _env({"mass_index": out})


# ---------------------------------------------------------------- 63/64 VIX
def vix(ctx, p):
    values = _series_or_none(ctx, "vix")
    if values is None:
        return _env({}, note="data_unavailable")
    return _env({"vix": values}, note="Requires a volatility-index feed (not derivable from NSE OHLCV).")


def india_vix(ctx, p):
    values = _series_or_none(ctx, "india_vix")
    if values is None:
        return _env({}, note="data_unavailable")
    return _env({"india_vix": values}, note="Requires the India VIX feed (NSE).")


# ---------------------------------------------------------------- 65 Volatility Stop
def volatility_stop(ctx, p):
    period = int(p.get("period", 20))
    mult = float(p.get("multiplier", 2.0))
    close = _close(ctx)
    high = _high(ctx)
    low = _low(ctx)
    atrs = atr(high, low, close, period)
    out: Series = [None] * len(close)
    mode = 0
    prev = None
    for i in range(len(close)):
        a = atrs[i]
        if a is None or close[i] is None:
            continue
        if prev is None or i == 0:
            mode, prev = 1, close[i] - mult * a
        elif mode == 1:
            prev = max(prev, close[i] - mult * a)
            if close[i] < prev:
                mode, prev = -1, close[i] + mult * a
        else:
            prev = min(prev, close[i] + mult * a)
            if close[i] > prev:
                mode, prev = 1, close[i] - mult * a
        out[i] = prev
    return _env({"volatility_stop": out})


# ---------------------------------------------------------------- 66 Acceleration Bands
def acceleration_bands(ctx, p):
    period = int(p.get("period", 20))
    mult = float(p.get("multiplier", 4.0))
    high = _high(ctx)
    low = _low(ctx)
    close = _close(ctx)
    mid = sma(close, period)
    factor = [
        None if h is None or l is None or c in (None, 0) else mult * (h - l) / c
        for h, l, c in zip(high, low, close)
    ]
    upper = [None if m is None or f is None or h is None else m + f * (h - m) for m, f, h in zip(mid, factor, high)]
    lower = [None if m is None or f is None or l is None else m - f * (m - l) for m, f, l in zip(mid, factor, low)]
    return _env({"middle": mid}, levels={"upper": upper, "lower": lower})


# ---------------------------------------------------------------- 67 Fractal Chaos Bands
def fractal_chaos_bands(ctx, p):
    period = int(p.get("period", 6))
    high = _high(ctx)
    low = _low(ctx)
    upper = highest(high, period)
    lower = lowest(low, period)
    mid = [None if u is None or l is None else (u + l) / 2.0 for u, l in zip(upper, lower)]
    return _env({"middle": mid}, levels={"upper": upper, "lower": lower})


# ---------------------------------------------------------------- 68 GARCH(1,1) volatility
def garch_volatility(ctx, p):
    """GARCH(1,1) conditional volatility estimated by quasi-ML.

    sigma2_t = omega + alpha*eps^2_{t-1} + beta*sigma2_{t-1}, with
    omega = variance * (1 - alpha - beta) so the long-run variance matches
    the sample variance.  Parameters are estimated by grid search because a
    full optimiser would add a heavy dependency.
    """
    period = int(p.get("period", 100))
    close = _close(ctx)
    returns = [None] + [
        None if a is None or b in (None, 0) else math.log(a / b)
        for a, b in zip(close[1:], close[:-1])
    ]
    clean = [r for r in returns if r is not None][-period:]
    if len(clean) < 30:
        return _env({"garch_volatility": [None] * len(close)}, note="Insufficient history for GARCH estimation")
    mean = sum(clean) / len(clean)
    var = sum((r - mean) ** 2 for r in clean) / len(clean)
    if var <= 0:
        return _env({"garch_volatility": [None] * len(close)}, note="Zero return variance")
    best = None
    for alpha in (0.05, 0.10, 0.15, 0.20):
        for beta in (0.80, 0.85, 0.90, 0.95):
            if alpha + beta >= 0.999:
                continue
            omega = var * (1 - alpha - beta)
            s2 = var
            ll = 0.0
            for r in clean:
                s2 = omega + alpha * (r - mean) ** 2 + beta * s2
                if s2 <= 0:
                    ll = -1e18
                    break
                ll += -0.5 * (math.log(2 * math.pi) + math.log(s2) + (r - mean) ** 2 / s2)
            if best is None or ll > best[0]:
                best = (ll, alpha, beta, omega)
    _, alpha, beta, omega = best
    out: Series = [None] * len(close)
    s2 = var
    for i in range(len(close)):
        r = returns[i]
        if r is None:
            continue
        s2 = omega + alpha * (r - mean) ** 2 + beta * s2
        out[i] = math.sqrt(max(s2, 0.0)) * math.sqrt(252.0)
    return _env(
        {"garch_volatility": out},
        note=f"GARCH(1,1) grid-ML alpha={alpha} beta={beta}; annualised with sqrt(252).",
    )


# ---------------------------------------------------------------- 69 Normalized ATR
def normalized_atr(ctx, p):
    period = int(p.get("period", 14))
    pct = atr_percent(ctx, {"period": period})["series"]["atr_percent"]
    return _env({"normalized_atr": [None if v is None else v / 100.0 for v in pct]})


# ---------------------------------------------------------------- 70 STARC bands
def starc_bands(ctx, p):
    period = int(p.get("period", 15))
    mult = float(p.get("multiplier", 2.0))
    close = _close(ctx)
    mid = sma(close, period)
    atrs = atr(_high(ctx), _low(ctx), close, period)
    upper = [None if m is None or a is None else m + mult * a for m, a in zip(mid, atrs)]
    lower = [None if m is None or a is None else m - mult * a for m, a in zip(mid, atrs)]
    return _env({"middle": mid}, levels={"upper": upper, "lower": lower})
