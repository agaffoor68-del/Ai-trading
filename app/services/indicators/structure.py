"""Market structure & price action (F: 111-130).

Structure indicators are event based: they return ``series`` (per-bar values or
signals) plus ``meta`` with the detected events/zones so the UI can list them.
All pivots are confirmed with a right-side window, so nothing repaints.
"""

from __future__ import annotations

from typing import Optional

from .series import (
    Series,
    atr,
    highest,
    lowest,
    pivot_highs,
    pivot_lows,
    sma,
    to_float,
)

__all__ = [
    "zig_zag", "fractals", "swing_high_low", "market_structure_break",
    "break_of_structure", "change_of_character", "smart_money_concepts",
    "order_blocks", "fair_value_gaps", "liquidity_zones", "equal_highs_lows",
    "supply_demand_zones", "accumulation_distribution_zones",
    "donchian_breakout", "darvas_box", "heikin_ashi", "renko", "kagi",
    "point_and_figure", "inside_bar",
]


def _env(series: dict, note: Optional[str] = None, meta: Optional[dict] = None, levels: Optional[dict] = None) -> dict:
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


# ---------------------------------------------------------------- 111 Zig Zag
def zig_zag(ctx, p):
    threshold = float(p.get("threshold_pct", 5.0))
    high, low = _high(ctx), _low(ctx)
    n = len(high)
    line: Series = [None] * n
    points: list = []
    if n == 0:
        return _env({"zig_zag": line})
    direction = 0
    last = high[0] if high[0] is not None else low[0]
    last_idx = 0
    for i in range(1, n):
        if high[i] is None or low[i] is None or last in (None, 0):
            continue
        if direction >= 0 and (high[i] - last) / last * 100.0 >= threshold:
            direction, last, last_idx = 1, high[i], i
            line[i] = last
            points.append({"index": i, "price": last, "type": "high"})
        elif direction <= 0 and (last - low[i]) / last * 100.0 >= threshold:
            direction, last, last_idx = -1, low[i], i
            line[i] = last
            points.append({"index": i, "price": last, "type": "low"})
        elif direction == 1 and high[i] > last:
            last, last_idx = high[i], i
            line[i] = last
        elif direction == -1 and low[i] < last:
            last, last_idx = low[i], i
            line[i] = last
    return _env({"zig_zag": line}, meta={"points": points}, note=f"Reversal threshold {threshold}%.")


# ---------------------------------------------------------------- 112 Fractals
def fractals(ctx, p):
    window = int(p.get("window", 2))
    high, low = _high(ctx), _low(ctx)
    n = len(high)
    up: Series = [None] * n
    down: Series = [None] * n
    for i in range(window, n - window):
        hw = high[i - window : i + window + 1]
        lw = low[i - window : i + window + 1]
        if any(v is None for v in hw + lw):
            continue
        if high[i] == max(hw) and hw.count(high[i]) == 1:
            up[i] = high[i]
        if low[i] == min(lw) and lw.count(low[i]) == 1:
            down[i] = low[i]
    return _env(
        {"fractal_up": up, "fractal_down": down},
        note=f"Confirmed {window} bars after the pivot (non-repainting).",
    )


# ---------------------------------------------------------------- 113 Swing high/low
def swing_high_low(ctx, p):
    left = int(p.get("left", 3))
    right = int(p.get("right", 3))
    high, low = _high(ctx), _low(ctx)
    n = len(high)
    sh: Series = [None] * n
    sl: Series = [None] * n
    highs = pivot_highs(high, left, right)
    lows = pivot_lows(low, left, right)
    for i, value in highs:
        sh[i] = value
    for i, value in lows:
        sl[i] = value
    return _env({"swing_high": sh, "swing_low": sl}, meta={"highs": highs, "lows": lows})


# ---------------------------------------------------------------- 114-116 BOS / CHoCH / MSB
def _structure(ctx, left: int, right: int):
    high, low, close = _high(ctx), _low(ctx), _close(ctx)
    n = len(close)
    highs = pivot_highs(high, left, right)
    lows = pivot_lows(low, left, right)
    last_high = None
    last_low = None
    hi_i = lo_i = -1
    trend = 0
    events = []
    bos: Series = [None] * n
    choch: Series = [None] * n
    msb: Series = [None] * n
    for i in range(n):
        while hi_i + 1 < len(highs) and highs[hi_i + 1][0] <= i - right:
            hi_i += 1
            last_high = highs[hi_i][1]
        while lo_i + 1 < len(lows) and lows[lo_i + 1][0] <= i - right:
            lo_i += 1
            last_low = lows[lo_i][1]
        c = close[i]
        if c is None:
            continue
        if last_high is not None and c > last_high:
            if trend == 1:
                bos[i] = 1
                events.append({"index": i, "type": "BOS", "direction": "bullish", "level": last_high})
            else:
                choch[i] = 1
                events.append({"index": i, "type": "CHoCH", "direction": "bullish", "level": last_high})
            trend = 1
            last_high = None
            hi_i = len(highs)
        elif last_low is not None and c < last_low:
            if trend == -1:
                bos[i] = -1
                events.append({"index": i, "type": "BOS", "direction": "bearish", "level": last_low})
            else:
                choch[i] = -1
                events.append({"index": i, "type": "CHoCH", "direction": "bearish", "level": last_low})
            trend = -1
            last_low = None
            lo_i = len(lows)
        msb[i] = trend
    return bos, choch, msb, trend, events


def market_structure_break(ctx, p):
    bos, _choch, msb, _t, events = _structure(ctx, int(p.get("left", 3)), int(p.get("right", 3)))
    return _env({"msb": msb, "msb_event": bos}, meta={"events": events}, note="MSB = break of the previous swing in the prevailing trend direction.")


def break_of_structure(ctx, p):
    bos, _choch, msb, _t, events = _structure(ctx, int(p.get("left", 3)), int(p.get("right", 3)))
    return _env({"bos": bos, "trend": msb}, meta={"events": [e for e in events if e["type"] == "BOS"]})


def change_of_character(ctx, p):
    _bos, choch, msb, _t, events = _structure(ctx, int(p.get("left", 3)), int(p.get("right", 3)))
    return _env({"choch": choch, "trend": msb}, meta={"events": [e for e in events if e["type"] == "CHoCH"]})


# ---------------------------------------------------------------- 117 SMC composite
def smart_money_concepts(ctx, p):
    bos, choch, trend, _t, events = _structure(ctx, int(p.get("left", 3)), int(p.get("right", 3)))
    fvg = fair_value_gaps(ctx, p)
    ob = order_blocks(ctx, p)
    return _env(
        {"trend": trend, "bos": bos, "choch": choch},
        meta={"events": events, "fvg": fvg.get("meta", {}).get("gaps", []), "order_blocks": ob.get("meta", {}).get("blocks", [])},
        note="Composite of structure, fair value gaps and order blocks.",
    )


# ---------------------------------------------------------------- 118 Order blocks
def order_blocks(ctx, p):
    window = int(p.get("window", 3))
    displacement = float(p.get("displacement_atr", 1.0))
    high, low, close = _high(ctx), _low(ctx), _close(ctx)
    atrs = atr(high, low, close, 14)
    n = len(close)
    blocks = []
    for i in range(window, n):
        a = atrs[i] if atrs[i] is not None else 0
        body = abs(close[i] - (open_of(ctx, i) or close[i]))
        if a <= 0 or body < displacement * a:
            continue
        if close[i] > (open_of(ctx, i) or close[i]):
            for j in range(i - window, i):
                if close[j] is not None and close[j] < (open_of(ctx, j) or close[j]):
                    blocks.append({"index": j, "type": "bullish", "low": low[j], "high": high[j]})
                    break
        else:
            for j in range(i - window, i):
                if close[j] is not None and close[j] > (open_of(ctx, j) or close[j]):
                    blocks.append({"index": j, "type": "bearish", "low": low[j], "high": high[j]})
                    break
    return _env({}, meta={"blocks": blocks[-20:]}, note="Last opposite-colour candle before a displacement move.")


def open_of(ctx, i) -> Optional[float]:
    values = getattr(ctx, "open", [])
    return to_float(values[i]) if i < len(values) else None


# ---------------------------------------------------------------- 119 FVG
def fair_value_gaps(ctx, p):
    high, low = _high(ctx), _low(ctx)
    n = len(high)
    gaps = []
    for i in range(2, n):
        if None in (high[i], low[i], high[i - 2], low[i - 2]):
            continue
        if low[i] > high[i - 2]:
            gaps.append({"index": i, "type": "bullish", "low": high[i - 2], "high": low[i]})
        elif high[i] < low[i - 2]:
            gaps.append({"index": i, "type": "bearish", "low": high[i], "high": low[i - 2]})
    return _env({}, meta={"gaps": gaps[-30:]}, note="Three-candle imbalance (gap between bar i-2 and bar i).")


# ---------------------------------------------------------------- 120 Liquidity zones
def liquidity_zones(ctx, p):
    left = int(p.get("left", 3))
    right = int(p.get("right", 3))
    tolerance = float(p.get("tolerance_pct", 0.2))
    highs = pivot_highs(_high(ctx), left, right)
    lows = pivot_lows(_low(ctx), left, right)
    buy = []
    sell = []
    for cluster, source, target in (([], highs, buy), ([], lows, sell)):
        for _i, price in source:
            for zone in cluster:
                if abs(price - zone["price"]) / zone["price"] * 100.0 <= tolerance:
                    zone["touches"] += 1
                    zone["price"] = (zone["price"] * (zone["touches"] - 1) + price) / zone["touches"]
                    break
            else:
                cluster.append({"price": price, "touches": 1})
    return _env(
        {},
        meta={"buy_side_liquidity": sorted(buy, key=lambda z: -z["touches"])[:5], "sell_side_liquidity": sorted(sell, key=lambda z: -z["touches"])[:5]},
        note="Clusters of equal highs (buy-side liquidity) and equal lows (sell-side liquidity).",
    )


# ---------------------------------------------------------------- 121 Equal highs/lows
def equal_highs_lows(ctx, p):
    tolerance = float(p.get("tolerance_pct", 0.1))
    left = int(p.get("left", 3))
    right = int(p.get("right", 3))
    highs = pivot_highs(_high(ctx), left, right)
    lows = pivot_lows(_low(ctx), left, right)
    equal_highs = []
    for i in range(len(highs)):
        for j in range(i + 1, len(highs)):
            a, b = highs[i][1], highs[j][1]
            if a and abs(a - b) / a * 100.0 <= tolerance:
                equal_highs.append({"first": highs[i][0], "second": highs[j][0], "price": (a + b) / 2})
    equal_lows = []
    for i in range(len(lows)):
        for j in range(i + 1, len(lows)):
            a, b = lows[i][1], lows[j][1]
            if a and abs(a - b) / a * 100.0 <= tolerance:
                equal_lows.append({"first": lows[i][0], "second": lows[j][0], "price": (a + b) / 2})
    return _env({}, meta={"equal_highs": equal_highs[-10:], "equal_lows": equal_lows[-10:]})


# ---------------------------------------------------------------- 122/123 Supply & demand zones
def _zones(ctx, mode: str, p):
    high, low, close = _high(ctx), _low(ctx), _close(ctx)
    open_ = [to_float(v) for v in getattr(ctx, "open", [])]
    vol = [to_float(v) for v in getattr(ctx, "volume", [])]
    atrs = atr(high, low, close, 14)
    n = len(close)
    zones = []
    for i in range(1, n):
        a = atrs[i] if atrs[i] is not None else None
        o = open_[i] if i < len(open_) else close[i]
        v = vol[i] if i < len(vol) else None
        if None in (close[i], o) or a in (None, 0):
            continue
        body = abs(close[i] - o)
        if mode == "supply_demand" and body >= 1.5 * a:
            zones.append({"index": i, "type": "supply" if close[i] < o else "demand", "low": low[i], "high": high[i]})
        elif mode == "accumulation" and v is not None and body < 0.5 * a:
            zones.append({"index": i, "type": "consolidation", "low": low[i], "high": high[i], "volume": v})
    return _env({}, meta={"zones": zones[-20:]}, note="Supply/demand = impulse candles; accumulation = high-volume inside bars." if mode == "supply_demand" else "High-volume consolidation (base) zones.")


def supply_demand_zones(ctx, p):
    return _zones(ctx, "supply_demand", p)


def accumulation_distribution_zones(ctx, p):
    return _zones(ctx, "accumulation", p)


# ---------------------------------------------------------------- 124 Donchian breakout
def donchian_breakout(ctx, p):
    period = int(p.get("period", 20))
    high, low, close = _high(ctx), _low(ctx), _close(ctx)
    hh = highest(high, period)
    ll = lowest(low, period)
    n = len(close)
    signal: Series = [None] * n
    for i in range(1, n):
        if None in (close[i], hh[i - 1], ll[i - 1]):
            continue
        if close[i] > hh[i - 1]:
            signal[i] = 1
        elif close[i] < ll[i - 1]:
            signal[i] = -1
    return _env({"breakout": signal}, levels={"upper": hh, "lower": ll})


# ---------------------------------------------------------------- 125 Darvas box
def darvas_box(ctx, p):
    period = int(p.get("period", 5))
    high, low, close = _high(ctx), _low(ctx), _close(ctx)
    vol = [to_float(v) for v in getattr(ctx, "volume", [])]
    n = len(close)
    box_high: Series = [None] * n
    box_low: Series = [None] * n
    top = bottom = None
    for i in range(n):
        if high[i] is None or low[i] is None:
            continue
        if top is None:
            top, bottom = high[i], low[i]
        elif high[i] > top and (i >= period and all(close[j] is None or close[j] < high[i] for j in range(max(0, i - period), i))):
            top, bottom = high[i], low[i]
        elif low[i] < bottom:
            bottom = low[i]
        box_high[i], box_low[i] = top, bottom
    return _env(
        {"box_high": box_high, "box_low": box_low},
        meta={"volume_confirm": [bool(v) for v in vol[-1:]]},
        note="Darvas boxes form on new highs with the prior bars contained; volume confirmation is shown separately.",
    )


# ---------------------------------------------------------------- 126 Heikin Ashi
def heikin_ashi(ctx, p):
    open_ = [to_float(v) for v in getattr(ctx, "open", [])]
    high, low, close = _high(ctx), _low(ctx), _close(ctx)
    n = len(close)
    ha_open: Series = [None] * n
    ha_high: Series = [None] * n
    ha_low: Series = [None] * n
    ha_close: Series = [None] * n
    prev_open = prev_close = None
    for i in range(n):
        if None in (open_[i], high[i], low[i], close[i]):
            continue
        ha_close[i] = (open_[i] + high[i] + low[i] + close[i]) / 4.0
        ha_open[i] = (prev_open + prev_close) / 2.0 if prev_open is not None else open_[i]
        ha_high[i] = max(high[i], ha_open[i], ha_close[i])
        ha_low[i] = min(low[i], ha_open[i], ha_close[i])
        prev_open, prev_close = ha_open[i], ha_close[i]
    return _env({"ha_open": ha_open, "ha_high": ha_high, "ha_low": ha_low, "ha_close": ha_close})


# ---------------------------------------------------------------- 127 Renko
def renko(ctx, p):
    brick = p.get("brick_size")
    high, low, close = _high(ctx), _low(ctx), _close(ctx)
    atrs = atr(high, low, close, 14)
    if brick is None:
        valid = [a for a in atrs if a is not None]
        brick = (sum(valid) / len(valid)) if valid else 0.0
    brick = float(brick)
    n = len(close)
    out: Series = [None] * n
    bricks = []
    if brick <= 0 or n == 0:
        return _env({"renko": out}, meta={"bricks": []}, note="Brick size unavailable (needs ATR or an explicit brick_size).")
    last = close[0]
    if last is None:
        return _env({"renko": out}, meta={"bricks": []})
    out[0] = last
    for i in range(1, n):
        if close[i] is None:
            continue
        diff = close[i] - last
        while abs(diff) >= brick:
            step = brick if diff > 0 else -brick
            last += step
            out[i] = last
            bricks.append({"index": i, "price": last, "direction": 1 if step > 0 else -1})
            diff = close[i] - last
        if out[i] is None:
            out[i] = last
    return _env({"renko": out}, meta={"bricks": bricks[-200:], "brick_size": brick})


# ---------------------------------------------------------------- 128 Kagi
def kagi(ctx, p):
    reversal = p.get("reversal")
    close = _close(ctx)
    if reversal is None:
        valid = [c for c in close if c]
        reversal = 0.01 * (sum(valid) / len(valid)) if valid else 0.0
    reversal = float(reversal)
    n = len(close)
    out: Series = [None] * n
    lines = []
    if reversal <= 0 or n == 0 or close[0] is None:
        return _env({"kagi": out}, meta={"lines": []}, note="Reversal amount unavailable.")
    direction = 0
    anchor = close[0]
    out[0] = anchor
    for i in range(1, n):
        if close[i] is None:
            continue
        diff = close[i] - anchor
        if direction >= 0 and diff >= reversal:
            direction, anchor = 1, close[i]
            out[i] = anchor
            lines.append({"index": i, "price": anchor, "direction": 1})
        elif direction <= 0 and -diff >= reversal:
            direction, anchor = -1, close[i]
            out[i] = anchor
            lines.append({"index": i, "price": anchor, "direction": -1})
        else:
            out[i] = anchor
    return _env({"kagi": out}, meta={"lines": lines[-200:], "reversal": reversal})


# ---------------------------------------------------------------- 129 Point & figure
def point_and_figure(ctx, p):
    box = p.get("box_size")
    reversal = int(p.get("reversal", 3))
    close = _close(ctx)
    if box is None:
        valid = [c for c in close if c]
        box = 0.01 * (sum(valid) / len(valid)) if valid else 0.0
    box = float(box)
    n = len(close)
    out: Series = [None] * n
    columns = []
    if box <= 0 or n == 0 or close[0] is None:
        return _env({"pnf": out}, meta={"columns": []}, note="Box size unavailable.")
    direction = 0
    anchor = close[0]
    out[0] = anchor
    for i in range(1, n):
        if close[i] is None:
            continue
        if direction >= 0 and close[i] - anchor >= box:
            direction, anchor = 1, anchor + box * int((close[i] - anchor) // box)
            out[i] = anchor
            columns.append({"index": i, "price": anchor, "type": "X"})
        elif direction <= 0 and anchor - close[i] >= box:
            direction, anchor = -1, anchor - box * int((anchor - close[i]) // box)
            out[i] = anchor
            columns.append({"index": i, "price": anchor, "type": "O"})
        elif direction == 1 and anchor - close[i] >= reversal * box:
            direction, anchor = -1, close[i]
            out[i] = anchor
            columns.append({"index": i, "price": anchor, "type": "O"})
        elif direction == -1 and close[i] - anchor >= reversal * box:
            direction, anchor = 1, close[i]
            out[i] = anchor
            columns.append({"index": i, "price": anchor, "type": "X"})
        else:
            out[i] = anchor
    return _env({"pnf": out}, meta={"columns": columns[-200:], "box_size": box})


# ---------------------------------------------------------------- 130 Inside bar
def inside_bar(ctx, p):
    high, low = _high(ctx), _low(ctx)
    n = len(high)
    signal: Series = [None] * n
    count = 0
    for i in range(1, n):
        if None in (high[i], low[i], high[i - 1], low[i - 1]):
            continue
        if high[i] < high[i - 1] and low[i] > low[i - 1]:
            signal[i] = 1
            count += 1
    return _env({"inside_bar": signal}, meta={"count": count})
