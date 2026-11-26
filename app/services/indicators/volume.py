"""Volume indicators (D: 71-95).

Volume-delta style indicators need bid/ask or trade-direction data.  They read
``ctx.extras["volume_delta"]`` / ``["buy_volume"]`` / ``["sell_volume"]`` when
the provider supplies it and otherwise report ``data_unavailable`` rather than
guessing a split.
"""

from __future__ import annotations

import math
from typing import Optional

from .series import Series, cumsum, ema, pct_change, sma, to_float

__all__ = [
    "volume", "vwap", "anchored_vwap", "obv", "mfi", "cmf", "ad_line",
    "volume_profile", "fixed_range_volume_profile", "visible_range_volume_profile",
    "pvt", "volume_oscillator", "force_index", "ease_of_movement",
    "negative_volume_index", "positive_volume_index", "chaikin_oscillator",
    "klinger_volume_oscillator", "volume_roc", "volume_delta",
    "cumulative_volume_delta", "buy_sell_volume_ratio", "relative_volume",
    "money_flow", "volume_weighted_macd",
]


def _env(series: dict, note: Optional[str] = None, levels: Optional[dict] = None, meta: Optional[dict] = None) -> dict:
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


def _volume(ctx) -> Series:
    return [to_float(v) for v in ctx.volume]


def _typical(ctx) -> Series:
    h, l, c = _high(ctx), _low(ctx), _close(ctx)
    return [None if None in (a, b, d) else (a + b + d) / 3.0 for a, b, d in zip(h, l, c)]


def _day_index(ctx) -> list:
    """Day index per bar (0 for the first day) from ``ctx.ts`` (epoch seconds)."""
    ts = list(getattr(ctx, "ts", []) or [])
    out = []
    current = None
    day = -1
    for t in ts:
        d = int(t // 86400) if isinstance(t, (int, float)) else None
        if d is None:
            out.append(day if day >= 0 else 0)
            continue
        if d != current:
            current = d
            day += 1
        out.append(day)
    if not out:
        out = [0] * len(_close(ctx))
    return out


def _extras(ctx) -> dict:
    return getattr(ctx, "extras", {}) or {}


# ---------------------------------------------------------------- 71 Volume
def volume(ctx, p):
    return _env({"volume": _volume(ctx)})


# ---------------------------------------------------------------- 72 VWAP
def vwap(ctx, p):
    """Session VWAP: cumulative price*volume / cumulative volume, reset daily."""
    typical = _typical(ctx)
    vol = _volume(ctx)
    days = _day_index(ctx)
    out: Series = [None] * len(typical)
    num = den = 0.0
    current = None
    for i, (t, v) in enumerate(zip(typical, vol)):
        if t is None or v is None:
            out[i] = None
            continue
        if days[i] != current:
            current, num, den = days[i], 0.0, 0.0
        num += t * v
        den += v
        out[i] = None if den == 0 else num / den
    return _env({"vwap": out}, note="Session-anchored (resets at each new UTC day in ctx.ts).")


# ---------------------------------------------------------------- 73 Anchored VWAP
def anchored_vwap(ctx, p):
    start = int(p.get("start_index", 0))
    typical = _typical(ctx)
    vol = _volume(ctx)
    out: Series = [None] * len(typical)
    num = den = 0.0
    for i in range(len(typical)):
        t, v = typical[i], vol[i]
        if i < start or t is None or v is None:
            continue
        num += t * v
        den += v
        out[i] = None if den == 0 else num / den
    return _env({"anchored_vwap": out}, note=f"Anchored at bar {start}.")


# ---------------------------------------------------------------- 74 OBV
def obv(ctx, p):
    close = _close(ctx)
    vol = _volume(ctx)
    out: Series = [None] * len(close)
    total = 0.0
    started = False
    for i, (c, v) in enumerate(zip(close, vol)):
        if c is None or v is None:
            continue
        if not started:
            total, started = v, True
            out[i] = total
            continue
        prev = close[i - 1]
        if prev is None:
            out[i] = total
            continue
        if c > prev:
            total += v
        elif c < prev:
            total -= v
        out[i] = total
    return _env({"obv": out})


# ---------------------------------------------------------------- 75 MFI
def mfi(ctx, p):
    period = int(p.get("period", 14))
    typical = _typical(ctx)
    vol = _volume(ctx)
    raw_pos: Series = [None] * len(typical)
    raw_neg: Series = [None] * len(typical)
    for i in range(1, len(typical)):
        if None in (typical[i], typical[i - 1], vol[i]):
            continue
        if typical[i] > typical[i - 1]:
            raw_pos[i] = typical[i] * vol[i]
            raw_neg[i] = 0.0
        elif typical[i] < typical[i - 1]:
            raw_pos[i] = 0.0
            raw_neg[i] = typical[i] * vol[i]
        else:
            raw_pos[i] = raw_neg[i] = 0.0
    pos = sma(raw_pos, period)
    neg = sma(raw_neg, period)
    out: Series = []
    for a, b in zip(pos, neg):
        if a is None or b is None:
            out.append(None)
        elif b == 0:
            out.append(100.0)
        else:
            out.append(100.0 - 100.0 / (1.0 + a / b))
    return _env({"mfi": out})


# ---------------------------------------------------------------- 76 CMF
def cmf(ctx, p):
    period = int(p.get("period", 20))
    high, low, close = _high(ctx), _low(ctx), _close(ctx)
    vol = _volume(ctx)
    mfm: Series = []
    raw: Series = []
    for h, l, c in zip(high, low, close):
        if None in (h, l, c) or (h - l) == 0:
            mfm.append(None)
            raw.append(None)
            continue
        mfm.append(((c - l) - (h - c)) / (h - l))
        raw.append(None)
    weighted = [None if m is None or v is None else m * v for m, v in zip(mfm, vol)]
    num = sma(weighted, period)
    den = sma(vol, period)
    out = [None if a is None or b in (None, 0) else a / b for a, b in zip(num, den)]
    return _env({"cmf": out})


# ---------------------------------------------------------------- 77 A/D line
def ad_line(ctx, p):
    high, low, close = _high(ctx), _low(ctx), _close(ctx)
    vol = _volume(ctx)
    out: Series = [None] * len(close)
    total = 0.0
    started = False
    out = [None] * len(close)
    for i in range(len(close)):
        h, l, c, v = high[i], low[i], close[i], vol[i]
        if None in (h, l, c, v) or (h - l) == 0:
            if started:
                out[i] = total
            continue
        clv = ((c - l) - (h - c)) / (h - l)
        total += clv * v
        started = True
        out[i] = total
    return _env({"ad_line": out})


# ---------------------------------------------------------------- 78-80 Volume profiles
def _profile(ctx, start: int, end: int, bins: int) -> dict:
    high, low, close = _high(ctx), _low(ctx), _close(ctx)
    vol = _volume(ctx)
    rows = []
    for i in range(max(0, start), min(end, len(close))):
        if None in (high[i], low[i], close[i], vol[i]):
            continue
        rows.append((high[i], low[i], close[i], vol[i]))
    if not rows:
        return {"profile": [], "poc": None, "value_area": None}
    hi = max(r[0] for r in rows)
    lo = min(r[1] for r in rows)
    if hi <= lo:
        return {"profile": [{"price": hi, "volume": sum(r[3] for r in rows), "buy": 0.0, "sell": 0.0}], "poc": hi, "value_area": None}
    step = (hi - lo) / bins
    buckets = [0.0] * bins
    buy = [0.0] * bins
    sell = [0.0] * bins
    for h, l, c, v in rows:
        idx = min(bins - 1, int((h - lo) / step))
        buckets[idx] += v
        if c >= (h + l) / 2.0:
            buy[idx] += v
        else:
            sell[idx] += v
    total = sum(buckets) or 1.0
    poc_idx = max(range(bins), key=lambda i: buckets[i])
    # value area: expand around POC until 70% of volume is covered
    acc = buckets[poc_idx]
    low_i = high_i = poc_idx
    while acc < 0.7 * total and (low_i > 0 or high_i < bins - 1):
        down = buckets[low_i - 1] if low_i > 0 else -1
        up = buckets[high_i + 1] if high_i < bins - 1 else -1
        if up >= down:
            high_i += 1
            acc += max(up, 0)
        else:
            low_i -= 1
            acc += max(down, 0)
    profile = [
        {
            "price": lo + (i + 0.5) * step,
            "volume": buckets[i],
            "buy": buy[i],
            "sell": sell[i],
            "in_value_area": low_i <= i <= high_i,
        }
        for i in range(bins)
    ]
    return {
        "profile": profile,
        "poc": lo + (poc_idx + 0.5) * step,
        "value_area": [lo + low_i * step, lo + (high_i + 1) * step],
    }


def volume_profile(ctx, p):
    bins = int(p.get("bins", 24))
    lookback = int(p.get("lookback", 100))
    end = len(_close(ctx))
    res = _profile(ctx, max(0, end - lookback), end, bins)
    poc = res["poc"]
    poc_series: Series = [None] * end
    if poc is not None:
        poc_series[end - 1] = poc
    return _env({"poc": poc_series}, levels={"profile": res["profile"]}, meta={"poc": poc, "value_area": res["value_area"]})


def fixed_range_volume_profile(ctx, p):
    bins = int(p.get("bins", 24))
    start = int(p.get("start_pct", 0.0) / 100.0 * max(0, len(_close(ctx)) - 1))
    end = int(p.get("end_pct", 100.0) / 100.0 * max(0, len(_close(ctx)) - 1)) + 1
    res = _profile(ctx, start, end, bins)
    poc = res["poc"]
    poc_series: Series = [None] * len(_close(ctx))
    if poc is not None:
        poc_series[min(end, len(poc_series)) - 1] = poc
    return _env({"poc": poc_series}, levels={"profile": res["profile"]}, meta={"poc": poc, "value_area": res["value_area"], "range": [start, end]})


def visible_range_volume_profile(ctx, p):
    bins = int(p.get("bins", 24))
    res = _profile(ctx, 0, len(_close(ctx)), bins)
    poc = res["poc"]
    poc_series: Series = [None] * len(_close(ctx))
    if poc is not None and poc_series:
        poc_series[-1] = poc
    return _env({"poc": poc_series}, levels={"profile": res["profile"]}, meta={"poc": poc, "value_area": res["value_area"]})


# ---------------------------------------------------------------- 81 PVT
def pvt(ctx, p):
    close = _close(ctx)
    vol = _volume(ctx)
    out: Series = [None] * len(close)
    total = 0.0
    started = False
    for i, (c, v) in enumerate(zip(close, vol)):
        if c is None or v is None:
            continue
        prev = close[i - 1] if i > 0 else None
        if prev in (None, 0) or not started:
            started = True
            out[i] = total
            continue
        total += ((c - prev) / prev) * v
        out[i] = total
    return _env({"pvt": out})


# ---------------------------------------------------------------- 82 Volume oscillator
def volume_oscillator(ctx, p):
    fast = int(p.get("fast", 5))
    slow = int(p.get("slow", 20))
    vol = _volume(ctx)
    a = ema(vol, fast)
    b = ema(vol, slow)
    line = [None if x is None or y is None else x - y for x, y in zip(a, b)]
    return _env({"volume_oscillator": line})


# ---------------------------------------------------------------- 83 Force Index
def force_index(ctx, p):
    period = int(p.get("period", 13))
    close = _close(ctx)
    vol = _volume(ctx)
    raw: Series = [None] * len(close)
    for i in range(1, len(close)):
        if None in (close[i], close[i - 1], vol[i]):
            continue
        raw[i] = (close[i] - close[i - 1]) * vol[i]
    return _env({"force_index": ema(raw, period)})


# ---------------------------------------------------------------- 84 Ease of Movement
def ease_of_movement(ctx, p):
    period = int(p.get("period", 14))
    high, low = _high(ctx), _low(ctx)
    vol = _volume(ctx)
    n = len(high)
    raw: Series = [None] * n
    for i in range(1, n):
        if None in (high[i], low[i], high[i - 1], low[i - 1], vol[i]) or vol[i] == 0:
            continue
        midpoint_move = (high[i] + low[i]) / 2.0 - (high[i - 1] + low[i - 1]) / 2.0
        box_ratio = vol[i] / (high[i] - low[i]) if high[i] != low[i] else None
        if box_ratio in (None, 0):
            continue
        raw[i] = midpoint_move / box_ratio
    return _env({"ease_of_movement": sma(raw, period)})


# ---------------------------------------------------------------- 85/86 NVI / PVI
def negative_volume_index(ctx, p):
    close = _close(ctx)
    vol = _volume(ctx)
    out: Series = [None] * len(close)
    total = 1000.0
    started = False
    for i, (c, v) in enumerate(zip(close, vol)):
        if c is None or v is None:
            continue
        if not started:
            total, started, out[i] = 1000.0, True, 1000.0
            continue
        prev_v = vol[i - 1]
        if prev_v is not None and v < prev_v and close[i - 1] not in (None, 0):
            total *= c / close[i - 1]
        out[i] = total
    return _env({"nvi": out})


def positive_volume_index(ctx, p):
    close = _close(ctx)
    vol = _volume(ctx)
    out: Series = [None] * len(close)
    total = 1000.0
    started = False
    for i, (c, v) in enumerate(zip(close, vol)):
        if c is None or v is None:
            continue
        if not started:
            total, started, out[i] = 1000.0, True, 1000.0
            continue
        prev_v = vol[i - 1]
        if prev_v is not None and v > prev_v and close[i - 1] not in (None, 0):
            total *= c / close[i - 1]
        out[i] = total
    return _env({"pvi": out})


# ---------------------------------------------------------------- 87 Chaikin oscillator
def chaikin_oscillator(ctx, p):
    fast = int(p.get("fast", 3))
    slow = int(p.get("slow", 10))
    ad = ad_line(ctx, {})["series"]["ad_line"]
    a = ema(ad, fast)
    b = ema(ad, slow)
    return _env({"chaikin_oscillator": [None if x is None or y is None else x - y for x, y in zip(a, b)]})


# ---------------------------------------------------------------- 88 Klinger
def klinger_volume_oscillator(ctx, p):
    fast = int(p.get("fast", 34))
    slow = int(p.get("slow", 55))
    signal = int(p.get("signal", 13))
    high, low, close = _high(ctx), _low(ctx), _close(ctx)
    vol = _volume(ctx)
    n = len(close)
    trend: Series = [None] * n
    vf: Series = [None] * n
    for i in range(1, n):
        if None in (high[i], low[i], close[i], close[i - 1], vol[i]):
            continue
        dm = high[i] - low[i]
        trend[i] = 1 if (high[i] + low[i] + close[i]) > (high[i - 1] + low[i - 1] + close[i - 1]) else -1
        cm = (close[i] - close[i - 1]) if dm == 0 else (close[i] - close[i - 1]) / dm
        vf[i] = vol[i] * abs(2 * (dm / cm - 1)) * trend[i] * 100 if cm != 0 else 0.0
    kvo = [None if a is None or b is None else a - b for a, b in zip(ema(vf, fast), ema(vf, slow))]
    return _env({"kvo": kvo, "signal": ema(kvo, signal)})


# ---------------------------------------------------------------- 89 Volume ROC
def volume_roc(ctx, p):
    return _env({"volume_roc": pct_change(_volume(ctx), int(p.get("period", 9)))})


# ---------------------------------------------------------------- 90-92 Delta family
def volume_delta(ctx, p):
    values = _extras(ctx).get("volume_delta")
    if not values:
        return _env({}, note="data_unavailable")
    series = [to_float(v) for v in values]
    return _env({"volume_delta": series}, note="Requires tick/trade-direction data from the provider.")


def cumulative_volume_delta(ctx, p):
    values = _extras(ctx).get("volume_delta")
    if not values:
        return _env({}, note="data_unavailable")
    return _env({"cvd": cumsum([to_float(v) for v in values])}, note="Requires tick/trade-direction data from the provider.")


def buy_sell_volume_ratio(ctx, p):
    buy = _extras(ctx).get("buy_volume")
    sell = _extras(ctx).get("sell_volume")
    if not buy or not sell:
        return _env({}, note="data_unavailable")
    b = [to_float(v) for v in buy]
    s = [to_float(v) for v in sell]
    out: Series = [None if x is None or y in (None, 0) else x / y for x, y in zip(b, s)]
    return _env({"buy_sell_ratio": out}, note="Requires classified buy/sell volume from the provider.")


# ---------------------------------------------------------------- 93 RVOL
def relative_volume(ctx, p):
    period = int(p.get("period", 20))
    vol = _volume(ctx)
    avg = sma(vol, period)
    out = [None if v is None or a in (None, 0) else v / a for v, a in zip(vol, avg)]
    return _env({"rvol": out})


# ---------------------------------------------------------------- 94 Money flow
def money_flow(ctx, p):
    typical = _typical(ctx)
    vol = _volume(ctx)
    out: Series = [None] * len(typical)
    total = 0.0
    for i, (t, v) in enumerate(zip(typical, vol)):
        if t is None or v is None:
            continue
        total += t * v
        out[i] = total
    return _env({"money_flow": out})


# ---------------------------------------------------------------- 95 Volume-weighted MACD
def volume_weighted_macd(ctx, p):
    fast = int(p.get("fast", 12))
    slow = int(p.get("slow", 26))
    signal = int(p.get("signal", 9))
    v = vwap(ctx, {})["series"]["vwap"]
    a = ema(v, fast)
    b = ema(v, slow)
    line = [None if x is None or y is None else x - y for x, y in zip(a, b)]
    sig = ema(line, signal)
    hist = [None if x is None or y is None else x - y for x, y in zip(line, sig)]
    return _env({"vwmacd": line, "signal": sig, "histogram": hist}, note="MACD applied to session VWAP.")
