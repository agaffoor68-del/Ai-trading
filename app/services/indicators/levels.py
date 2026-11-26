"""Support & resistance indicators (E: 96-110).

These produce *levels* (price lines) rather than oscillators.  Each result has
``levels`` with one entry per line so the chart layer can draw them, and a
``series`` entry only where a value per bar is meaningful.
"""

from __future__ import annotations

from typing import Optional

from .series import Series, highest, lowest, sma, to_float

__all__ = [
    "fibonacci_retracement", "fibonacci_extension", "fibonacci_projection",
    "pivot_points", "fibonacci_pivot_points", "camarilla_pivots",
    "woodie_pivots", "demark_pivots", "support_resistance_zones",
    "auto_support_resistance", "prev_day_high_low", "prev_week_high_low",
    "prev_month_high_low", "central_pivot_range", "floor_trader_pivots",
]

FIB = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
EXT = [0.0, 0.618, 1.0, 1.618, 2.618, 4.236]


def _env(series: dict, levels: Optional[dict] = None, note: Optional[str] = None, meta: Optional[dict] = None) -> dict:
    out = {"series": series, "levels": levels or {}, "note": note}
    if meta:
        out["meta"] = meta
    return out


def _close(ctx) -> Series:
    return [to_float(v) for v in ctx.close]


def _high(ctx) -> Series:
    return [to_float(v) for v in ctx.high]


def _low(ctx) -> Series:
    return [to_float(v) for v in ctx.low]


def _last_valid(series: Series):
    for value in reversed(series):
        if value is not None:
            return value
    return None


def _group_bars(ctx, key: str) -> list:
    """Group index per bar by calendar bucket (day/week/month) from ctx.ts."""
    ts = list(getattr(ctx, "ts", []) or [])
    import datetime as _dt

    out = []
    current = None
    bucket = -1
    for t in ts:
        if not isinstance(t, (int, float)):
            out.append(bucket if bucket >= 0 else 0)
            continue
        d = _dt.datetime.fromtimestamp(t, _dt.timezone.utc)
        if key == "day":
            label = d.date()
        elif key == "week":
            label = (d.isocalendar()[0], d.isocalendar()[1])
        else:
            label = (d.year, d.month)
        if label != current:
            current = label
            bucket += 1
        out.append(bucket)
    if not out:
        out = [0] * len(_close(ctx))
    return out


def _levels_from_groups(ctx, key: str, include_current: bool):
    high, low = _high(ctx), _low(ctx)
    groups = _group_bars(ctx, key)
    last_group = groups[-1] if groups else 0
    hi = lo = None
    prev_hi = prev_lo = None
    for i, g in enumerate(groups):
        if include_current or g != last_group:
            if high[i] is not None:
                hi = high[i] if hi is None else max(hi, high[i])
            if low[i] is not None:
                lo = low[i] if lo is None else min(lo, low[i])
        if g != last_group and (include_current or True):
            prev_hi, prev_lo = hi, lo
            hi = lo = None
    if prev_hi is None:
        prev_hi, prev_lo = hi, lo
    return prev_hi, prev_lo


# ---------------------------------------------------------------- 96-98 Fibonacci
def fibonacci_retracement(ctx, p):
    lookback = int(p.get("lookback", 50))
    high, low = _high(ctx), _low(ctx)
    n = len(high)
    window_h = high[max(0, n - lookback) :]
    window_l = low[max(0, n - lookback) :]
    hi = max([v for v in window_h if v is not None], default=None)
    lo = min([v for v in window_l if v is not None], default=None)
    if hi is None or lo is None:
        return _env({}, note="Insufficient data")
    diff = hi - lo
    levels = {f"fib_{int(r * 1000) / 10:g}": hi - diff * r for r in FIB}
    return _env({}, levels=levels, meta={"high": hi, "low": lo}, note="Retracement levels from the highest high / lowest low of the lookback window.")


def fibonacci_extension(ctx, p):
    lookback = int(p.get("lookback", 50))
    high, low = _high(ctx), _low(ctx)
    n = len(high)
    window_h = [v for v in high[max(0, n - lookback) :] if v is not None]
    window_l = [v for v in low[max(0, n - lookback) :] if v is not None]
    if not window_h or not window_l:
        return _env({}, note="Insufficient data")
    hi, lo = max(window_h), min(window_l)
    diff = hi - lo
    levels = {f"ext_{r:g}": lo + diff * r for r in EXT}
    return _env({}, levels=levels, meta={"high": hi, "low": lo})


def fibonacci_projection(ctx, p):
    """Projection from a three-point swing (A-B-C) over the lookback window."""
    lookback = int(p.get("lookback", 100))
    high, low, close = _high(ctx), _low(ctx), _close(ctx)
    n = len(close)
    start = max(0, n - lookback)
    highs = [(i, high[i]) for i in range(start, n) if high[i] is not None]
    lows = [(i, low[i]) for i in range(start, n) if low[i] is not None]
    if len(highs) < 2 or len(lows) < 2:
        return _env({}, note="Insufficient data")
    a = highs[0][1]
    b = lows[0][1]
    c = close[-1] if close[-1] is not None else b
    diff = c - b
    levels = {f"proj_{r:g}": c + diff * r for r in (0.618, 1.0, 1.618, 2.618)}
    return _env({}, levels=levels, meta={"A": a, "B": b, "C": c}, note="Uses the first swing high/low of the window as A/B and the latest close as C.")


# ---------------------------------------------------------------- 99-103 Pivots
def _pivot_levels(h, l, c):
    rng = h - l
    return {
        "p": (h + l + c) / 3.0,
        "r1": 2 * ((h + l + c) / 3.0) - l,
        "s1": 2 * ((h + l + c) / 3.0) - h,
        "r2": (h + l + c) / 3.0 + rng,
        "s2": (h + l + c) / 3.0 - rng,
        "r3": h + 2 * (rng),
        "s3": l - 2 * (rng),
    }


def pivot_points(ctx, p):
    mode = str(p.get("mode", "daily"))
    hi, lo = _levels_from_groups(ctx, "day" if mode == "daily" else mode, include_current=False)
    if hi is None or lo is None:
        return _env({}, note="Insufficient data")
    prev_close = None
    close = _close(ctx)
    groups = _group_bars(ctx, "day")
    for i in range(len(close) - 1, -1, -1):
        if groups[i] != groups[-1] and close[i] is not None:
            prev_close = close[i]
            break
    if prev_close is None:
        prev_close = close[-1] or 0
    return _env({}, levels=_pivot_levels(hi, lo, prev_close), meta={"high": hi, "low": lo, "prev_close": prev_close})


def fibonacci_pivot_points(ctx, p):
    hi, lo = _levels_from_groups(ctx, "day", include_current=False)
    if hi is None or lo is None:
        return _env({}, note="Insufficient data")
    close = _close(ctx)
    prev_close = next((close[i] for i in range(len(close) - 1, -1, -1) if close[i] is not None), 0) or 0
    piv = (hi + lo + prev_close) / 3.0
    rng = hi - lo
    levels = {"p": piv}
    for r in (0.382, 0.618, 1.0):
        levels[f"r{r:g}"] = piv + rng * r
        levels[f"s{r:g}"] = piv - rng * r
    return _env({}, levels=levels, meta={"high": hi, "low": lo})


def camarilla_pivots(ctx, p):
    hi, lo = _levels_from_groups(ctx, "day", include_current=False)
    if hi is None or lo is None:
        return _env({}, note="Insufficient data")
    close = _close(ctx)
    prev_close = next((close[i] for i in range(len(close) - 1, -1, -1) if close[i] is not None), 0) or 0
    rng = hi - lo
    levels = {"p": prev_close}
    for mult, name in ((1.1, "h1"), (1.2, "h2"), (1.3, "h3"), (1.4, "h4")):
        levels[name] = prev_close + rng * mult / 12.0
        levels[name.replace("h", "l")] = prev_close - rng * mult / 12.0
    return _env({}, levels=levels, meta={"high": hi, "low": lo})


def woodie_pivots(ctx, p):
    hi, lo = _levels_from_groups(ctx, "day", include_current=False)
    if hi is None or lo is None:
        return _env({}, note="Insufficient data")
    close = _close(ctx)
    prev_close = next((close[i] for i in range(len(close) - 1, -1, -1) if close[i] is not None), 0) or 0
    piv = (hi + lo + 2 * prev_close) / 4.0
    return _env(
        {},
        levels={
            "p": piv,
            "r1": 2 * piv - lo,
            "s1": 2 * piv - hi,
            "r2": piv + (hi - lo),
            "s2": piv - (hi - lo),
            "r3": hi + 2 * (piv - lo),
            "s3": lo - 2 * (hi - piv),
        },
        meta={"high": hi, "low": lo},
    )


def demark_pivots(ctx, p):
    hi, lo = _levels_from_groups(ctx, "day", include_current=False)
    if hi is None or lo is None:
        return _env({}, note="Insufficient data")
    close = _close(ctx)
    prev_close = next((close[i] for i in range(len(close) - 1, -1, -1) if close[i] is not None), 0) or 0
    if prev_close < hi:
        x = hi + 2 * lo + prev_close
    elif prev_close > lo:
        x = 2 * hi + lo + prev_close
    else:
        x = hi + lo + 2 * prev_close
    rng = hi - lo
    return _env(
        {},
        levels={"p": x / 4.0, "r1": x / 2.0 - lo, "s1": x / 2.0 - hi},
        meta={"high": hi, "low": lo, "x": x},
        note=f"X = {x:g} (DeMark pivot); only one resistance and one support are defined.",
    )


def floor_trader_pivots(ctx, p):
    hi, lo = _levels_from_groups(ctx, "day", include_current=False)
    if hi is None or lo is None:
        return _env({}, note="Insufficient data")
    close = _close(ctx)
    prev_close = next((close[i] for i in range(len(close) - 1, -1, -1) if close[i] is not None), 0) or 0
    piv = (hi + lo + prev_close) / 3.0
    rng = hi - lo
    return _env(
        {},
        levels={
            "p": piv,
            "r1": (2 * piv) - lo,
            "s1": (2 * piv) - hi,
            "r2": piv + rng,
            "s2": piv - rng,
            "r3": piv + 2 * rng,
            "s3": piv - 2 * rng,
        },
        meta={"high": hi, "low": lo},
    )


# ---------------------------------------------------------------- 104-105 S/R zones
def support_resistance_zones(ctx, p):
    """Cluster swing pivots into price zones; the strongest touches win."""
    from .series import pivot_highs, pivot_lows

    lookback = int(p.get("lookback", 300))
    tolerance = float(p.get("tolerance_pct", 0.5))
    n = len(_close(ctx))
    start = max(0, n - lookback)
    highs = [(i, v) for i, v in pivot_highs(_high(ctx), 3, 3) if i >= start]
    lows = [(i, v) for i, v in pivot_lows(_low(ctx), 3, 3) if i >= start]
    levels = {}
    for name, points in (("resistance", highs), ("support", lows)):
        clusters: list = []
        for _i, price in points:
            for cluster in clusters:
                if abs(price - cluster[0]) / cluster[0] * 100.0 <= tolerance:
                    cluster[1] += 1
                    cluster[0] = (cluster[0] * (cluster[1] - 1) + price) / cluster[1]
                    break
            else:
                clusters.append([price, 1])
        for idx, (price, touches) in enumerate(sorted(clusters, key=lambda c: -c[1])[:5]):
            levels[f"{name}_{idx + 1}"] = price
    return _env({}, levels=levels, meta={"touches": {k: v for k, v in levels.items()}}, note=f"Zones cluster pivots within {tolerance}%.")


def auto_support_resistance(ctx, p):
    period = int(p.get("period", 20))
    lookback = int(p.get("lookback", 300))
    high, low = _high(ctx), _low(ctx)
    n = len(high)
    start = max(0, n - lookback)
    highs = highest(high, period)
    lows = lowest(low, period)
    res = {}
    sup = {}
    for i in range(start + period, n):
        if highs[i] is not None:
            res.setdefault(round(highs[i], 2), 0)
            res[round(highs[i], 2)] += 1
        if lows[i] is not None:
            sup.setdefault(round(lows[i], 2), 0)
            sup[round(lows[i], 2)] += 1
    levels = {}
    for idx, (price, _c) in enumerate(sorted(res.items(), key=lambda kv: -kv[1])[:3]):
        levels[f"resistance_{idx + 1}"] = price
    for idx, (price, _c) in enumerate(sorted(sup.items(), key=lambda kv: -kv[1])[:3]):
        levels[f"support_{idx + 1}"] = price
    return _env({}, levels=levels, note=f"Levels are the most frequently touched {period}-bar extremes in the lookback.")


# ---------------------------------------------------------------- 106-108 Previous period H/L
def prev_day_high_low(ctx, p):
    hi, lo = _levels_from_groups(ctx, "day", include_current=False)
    if hi is None or lo is None:
        return _env({}, note="Insufficient data")
    return _env({}, levels={"prev_day_high": hi, "prev_day_low": lo})


def prev_week_high_low(ctx, p):
    hi, lo = _levels_from_groups(ctx, "week", include_current=False)
    if hi is None or lo is None:
        return _env({}, note="Insufficient data")
    return _env({}, levels={"prev_week_high": hi, "prev_week_low": lo})


def prev_month_high_low(ctx, p):
    hi, lo = _levels_from_groups(ctx, "month", include_current=False)
    if hi is None or lo is None:
        return _env({}, note="Insufficient data")
    return _env({}, levels={"prev_month_high": hi, "prev_month_low": lo})


# ---------------------------------------------------------------- 109 CPR
def central_pivot_range(ctx, p):
    hi, lo = _levels_from_groups(ctx, "day", include_current=False)
    if hi is None or lo is None:
        return _env({}, note="Insufficient data")
    close = _close(ctx)
    prev_close = next((close[i] for i in range(len(close) - 1, -1, -1) if close[i] is not None), 0) or 0
    piv = (hi + lo + prev_close) / 3.0
    bc = (hi + lo) / 2.0
    tc = 2 * piv - bc
    return _env({}, levels={"pivot": piv, "bc": bc, "tc": tc, "cpr_width": abs(tc - bc)}, meta={"high": hi, "low": lo})
