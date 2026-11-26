"""Trend indicators (A: 1-25).

Every function has the signature ``fn(ctx, p) -> dict`` where ``ctx`` exposes
``ts/open/high/low/close/volume`` arrays and ``p`` is the parameter dict with
defaults already applied.  Results use the standard envelope::

    {"series": {name: [float|None, ...]}, "levels": {...}, "note": str|None}

Series are always the same length as ``ctx.close`` and never use future bars.
"""

from __future__ import annotations

import math
from typing import List, Optional

from .series import (
    Series,
    alma,
    atr,
    change,
    dema,
    ema,
    highest,
    hma,
    kama,
    lowest,
    mcginley,
    rma,
    sma,
    stdev,
    tema,
    to_float,
    true_range,
    wma,
    zlema,
    linear_regression,
)

__all__ = [
    "sma_", "ema_", "wma_", "vwma", "dema_", "tema_", "hma_", "kama_",
    "alma_", "zlema_", "t3_", "mcginley_", "supertrend", "parabolic_sar",
    "ichimoku", "adx", "dmi", "aroon", "aroon_oscillator", "vortex",
    "linear_regression_", "linear_regression_slope", "ma_ribbon",
    "guppy_gmma", "trend_magic",
]


def _env(series: dict, note: Optional[str] = None, levels: Optional[dict] = None) -> dict:
    return {"series": series, "levels": levels or {}, "note": note}


def _close(ctx) -> Series:
    return [to_float(v) for v in ctx.close]


# ---------------------------------------------------------------- A1-A12 MAs
def sma_(ctx, p):
    period = int(p.get("period", 20))
    return _env({"sma": sma(_close(ctx), period)})


def ema_(ctx, p):
    period = int(p.get("period", 20))
    return _env({"ema": ema(_close(ctx), period)})


def wma_(ctx, p):
    period = int(p.get("period", 20))
    return _env({"wma": wma(_close(ctx), period)})


def vwma(ctx, p):
    period = int(p.get("period", 20))
    close = _close(ctx)
    volume = [to_float(v) for v in ctx.volume]
    pv = [None if c is None or v is None else c * v for c, v in zip(close, volume)]
    num = sma(pv, period)
    den = sma(volume, period)
    out: Series = [
        None if n is None or d in (None, 0) else n / d for n, d in zip(num, den)
    ]
    return _env({"vwma": out})


def dema_(ctx, p):
    return _env({"dema": dema(_close(ctx), int(p.get("period", 20)))})


def tema_(ctx, p):
    return _env({"tema": tema(_close(ctx), int(p.get("period", 20)))})


def hma_(ctx, p):
    return _env({"hma": hma(_close(ctx), int(p.get("period", 20)))})


def kama_(ctx, p):
    return _env(
        {"kama": kama(_close(ctx), int(p.get("period", 10)), int(p.get("fast", 2)), int(p.get("slow", 30)))}
    )


def alma_(ctx, p):
    return _env(
        {"alma": alma(_close(ctx), int(p.get("period", 21)), float(p.get("offset", 0.85)), float(p.get("sigma", 6.0)))}
    )


def zlema_(ctx, p):
    return _env({"zlema": zlema(_close(ctx), int(p.get("period", 20)))})


def t3_(ctx, p):
    from .series import t3

    return _env({"t3": t3(_close(ctx), int(p.get("period", 5)), float(p.get("v_factor", 0.7)))})


def mcginley_(ctx, p):
    return _env({"mcginley": mcginley(_close(ctx), int(p.get("period", 14)))})


# ---------------------------------------------------------------- A13 Supertrend
def supertrend(ctx, p):
    period = int(p.get("period", 10))
    mult = float(p.get("multiplier", 3.0))
    high = [to_float(v) for v in ctx.high]
    low = [to_float(v) for v in ctx.low]
    close = _close(ctx)
    atrs = atr(high, low, close, period)

    st: Series = [None] * len(close)
    direction: Series = [None] * len(close)
    upper: Series = [None] * len(close)
    lower: Series = [None] * len(close)
    prev_dir = 1
    for i in range(len(close)):
        a = atrs[i]
        if a is None or close[i] is None or high[i] is None or low[i] is None:
            continue
        hl2 = (high[i] + low[i]) / 2.0
        bu = hl2 + mult * a
        bl = hl2 - mult * a
        if i == 0 or st[i - 1] is None:
            upper[i], lower[i] = bu, bl
            st[i] = bl
            direction[i] = 1
            prev_dir = 1
            continue
        upper[i] = bu if (bu < upper[i - 1] or close[i - 1] > upper[i - 1]) else upper[i - 1]
        lower[i] = bl if (bl > lower[i - 1] or close[i - 1] < lower[i - 1]) else lower[i - 1]
        if st[i - 1] == upper[i - 1] and close[i] <= upper[i]:
            prev_dir = -1
        elif st[i - 1] == lower[i - 1] and close[i] >= lower[i]:
            prev_dir = 1
        elif close[i] > upper[i]:
            prev_dir = 1
        elif close[i] < lower[i]:
            prev_dir = -1
        st[i] = lower[i] if prev_dir == 1 else upper[i]
        direction[i] = prev_dir
    return _env({"supertrend": st, "direction": direction}, levels={"upper": upper, "lower": lower})


# ---------------------------------------------------------------- A14 Parabolic SAR
def parabolic_sar(ctx, p):
    step = float(p.get("step", 0.02))
    max_step = float(p.get("max_step", 0.2))
    high = [to_float(v) for v in ctx.high]
    low = [to_float(v) for v in ctx.low]
    n = len(high)
    out: Series = [None] * n
    if n < 2:
        return _env({"sar": out})
    rising = (high[1] if high[1] is not None else 0) >= (high[0] or 0)
    af = step
    ep = high[1] if rising else low[1]
    sar = low[0] if rising else high[0]
    if sar is None:
        sar = low[1] if low[1] is not None else high[1]
    out[0] = sar
    for i in range(1, n):
        if high[i] is None or low[i] is None:
            out[i] = None
            continue
        sar = sar + af * (ep - sar)
        if rising:
            sar = min(sar, low[i - 1] if low[i - 1] is not None else low[i], low[i])
            if low[i] < sar:
                rising, ep, af = False, low[i], step
                sar = ep if ep is not None else sar
            elif high[i] > ep:
                ep = high[i]
                af = min(af + step, max_step)
        else:
            sar = max(sar, high[i - 1] if high[i - 1] is not None else high[i], high[i])
            if high[i] > sar:
                rising, ep, af = True, high[i], step
                sar = ep if ep is not None else sar
            elif low[i] < ep:
                ep = low[i]
                af = min(af + step, max_step)
        out[i] = sar
    return _env({"sar": out})


# ---------------------------------------------------------------- A15 Ichimoku
def ichimoku(ctx, p):
    tenkan = int(p.get("tenkan", 9))
    kijun = int(p.get("kijun", 26))
    senkou = int(p.get("senkou_b", 52))
    high = [to_float(v) for v in ctx.high]
    low = [to_float(v) for v in ctx.low]
    close = _close(ctx)
    n = len(close)
    tenkan_i = sma(high, tenkan)
    tenkan_l = sma(low, tenkan)
    kijun_i = sma(high, kijun)
    kijun_l = sma(low, kijun)
    tenkan = [None if a is None or b is None else (a + b) / 2 for a, b in zip(tenkan_i, tenkan_l)]
    kijun_s = [None if a is None or b is None else (a + b) / 2 for a, b in zip(kijun_i, kijun_l)]
    span_a: Series = [None] * n
    span_b: Series = [None] * n
    for i in range(n):
        if tenkan[i] is not None and kijun_s[i] is not None:
            span_a[i] = (tenkan[i] + kijun_s[i]) / 2
        hi = highest(high, senkou)[i]
        lo = lowest(low, senkou)[i]
        if hi is not None and lo is not None:
            span_b[i] = (hi + lo) / 2
    # Chikou is the close plotted `kijun` bars back (a displaced, not future, value).
    chikou: Series = [None] * n
    for i in range(n - kijun):
        chikou[i] = close[i + kijun]
    return _env(
        {"tenkan": tenkan, "kijun": kijun_s, "span_a": span_a, "span_b": span_b, "chikou": chikou},
        note="Senkou spans are displaced forward by kijun bars for display; chikou is displaced back. Displacement is a plotting convention, not look-ahead.",
    )


# ---------------------------------------------------------------- A16/A17 ADX + DMI
def _di_components(ctx, period):
    high = [to_float(v) for v in ctx.high]
    low = [to_float(v) for v in ctx.low]
    close = _close(ctx)
    n = len(close)
    tr = true_range(high, low, close)
    plus_dm: Series = [None] * n
    minus_dm: Series = [None] * n
    for i in range(1, n):
        if None in (high[i], low[i], high[i - 1], low[i - 1]):
            continue
        up = high[i] - high[i - 1]
        down = low[i - 1] - low[i]
        plus_dm[i] = up if (up > down and up > 0) else 0.0
        minus_dm[i] = down if (down > up and down > 0) else 0.0
    tr_s = rma(tr, period)
    pdm_s = rma(plus_dm, period)
    mdm_s = rma(minus_dm, period)
    plus_di = [None if a is None or b in (None, 0) else 100 * a / b for a, b in zip(pdm_s, tr_s)]
    minus_di = [None if a is None or b in (None, 0) else 100 * a / b for a, b in zip(mdm_s, tr_s)]
    dx = [
        None
        if p is None or m is None or (p + m) == 0
        else 100 * abs(p - m) / (p + m)
        for p, m in zip(plus_di, minus_di)
    ]
    adx = rma(dx, period)
    return plus_di, minus_di, adx


def adx(ctx, p):
    period = int(p.get("period", 14))
    plus_di, minus_di, adx_s = _di_components(ctx, period)
    return _env({"adx": adx_s, "plus_di": plus_di, "minus_di": minus_di})


def dmi(ctx, p):
    period = int(p.get("period", 14))
    plus_di, minus_di, adx_s = _di_components(ctx, period)
    return _env({"plus_di": plus_di, "minus_di": minus_di, "adx": adx_s})


# ---------------------------------------------------------------- A18-A20 Aroon / Vortex
def aroon(ctx, p):
    period = int(p.get("period", 25))
    high = [to_float(v) for v in ctx.high]
    low = [to_float(v) for v in ctx.low]
    n = len(high)
    up: Series = [None] * n
    down: Series = [None] * n
    for i in range(period, n):
        window_h = high[i - period : i + 1]
        window_l = low[i - period : i + 1]
        if any(v is None for v in window_h) or any(v is None for v in window_l):
            continue
        since_high = period - (max(range(len(window_h)), key=lambda j: window_h[j]))
        since_low = period - (max(range(len(window_l)), key=lambda j: window_l[j]))
        up[i] = 100.0 * (period - since_high) / period
        down[i] = 100.0 * (period - since_low) / period
    return _env({"aroon_up": up, "aroon_down": down})


def aroon_oscillator(ctx, p):
    period = int(p.get("period", 25))
    high = [to_float(v) for v in ctx.high]
    low = [to_float(v) for v in ctx.low]
    n = len(high)
    out: Series = [None] * n
    for i in range(period, n):
        wh = high[i - period : i + 1]
        wl = low[i - period : i + 1]
        if any(v is None for v in wh) or any(v is None for v in wl):
            continue
        up = 100.0 * (period - (period - max(range(len(wh)), key=lambda j: wh[j]))) / period
        dn = 100.0 * (period - (period - max(range(len(wl)), key=lambda j: wl[j]))) / period
        out[i] = up - dn
    return _env({"aroon_oscillator": out})


def vortex(ctx, p):
    period = int(p.get("period", 14))
    high = [to_float(v) for v in ctx.high]
    low = [to_float(v) for v in ctx.low]
    close = _close(ctx)
    n = len(close)
    tr = true_range(high, low, close)
    vm_plus: Series = [None] * n
    vm_minus: Series = [None] * n
    for i in range(1, n):
        if None in (high[i], low[i], high[i - 1], low[i - 1]):
            continue
        vm_plus[i] = abs(high[i] - low[i - 1])
        vm_minus[i] = abs(low[i] - high[i - 1])
    tr_sum = sma(tr, period)
    vp_sum = sma(vm_plus, period)
    vm_sum = sma(vm_minus, period)
    vi_plus = [None if a is None or b in (None, 0) else a / b for a, b in zip(vp_sum, tr_sum)]
    vi_minus = [None if a is None or b in (None, 0) else a / b for a, b in zip(vm_sum, tr_sum)]
    return _env({"vi_plus": vi_plus, "vi_minus": vi_minus})


# ---------------------------------------------------------------- A21-A25
def linear_regression_(ctx, p):
    period = int(p.get("period", 20))
    value, _s, _r = linear_regression(_close(ctx), period)
    return _env({"linear_regression": value})


def linear_regression_slope(ctx, p):
    period = int(p.get("period", 20))
    _v, slope_s, _r = linear_regression(_close(ctx), period)
    return _env({"slope": slope_s})


def ma_ribbon(ctx, p):
    base = int(p.get("base", 8))
    count = int(p.get("count", 8))
    close = _close(ctx)
    series = {}
    for i in range(count):
        period = base * (2 ** i)
        series[f"sma_{period}"] = sma(close, period)
    return _env(series)


def guppy_gmma(ctx, p):
    close = _close(ctx)
    groups = {
        "short": [3, 5, 8, 10, 12, 15],
        "medium": [21, 24, 27, 30, 35, 40],
        "long": [50, 60, 70, 80, 90, 105],
    }
    series = {}
    for name, periods in groups.items():
        for period in periods:
            series[f"{name}_{period}"] = ema(close, period)
    return _env(series, note="GMMA groups: 3-15 (short), 21-40 (medium), 50-105 (long).")


def _cci(ctx, period):
    high = [to_float(v) for v in ctx.high]
    low = [to_float(v) for v in ctx.low]
    close = _close(ctx)
    tp = [
        None if None in (h, l, c) else (h + l + c) / 3.0
        for h, l, c in zip(high, low, close)
    ]
    avg = sma(tp, period)
    mean_dev = [
        None if a is None else a
        for a in avg
    ]
    # mean deviation over the window
    md: Series = [None] * len(tp)
    for i in range(period - 1, len(tp)):
        window = tp[i + 1 - period : i + 1]
        if any(v is None for v in window) or avg[i] is None:
            continue
        md[i] = sum(abs(v - avg[i]) for v in window) / period
    out: Series = []
    for t, a, m in zip(tp, avg, md):
        if None in (t, a, m) or m == 0:
            out.append(None)
        else:
            out.append((t - a) / (0.015 * m))
    return out


def trend_magic(ctx, p):
    period = int(p.get("period", 14))
    close = _close(ctx)
    cci = _cci(ctx, period)
    atrs = atr([to_float(v) for v in ctx.high], [to_float(v) for v in ctx.low], close, period)
    line: Series = []
    for c, k, a in zip(close, cci, atrs):
        if None in (c, k, a):
            line.append(None)
        else:
            line.append(c + (k / 100.0) * a)
    return _env(
        {"trend_magic": line},
        note="Trend Magic variant: close + (CCI/100)*ATR; direction is the sign of CCI.",
    )
