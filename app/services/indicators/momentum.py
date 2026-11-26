"""Momentum indicators (B: 26-50)."""

from __future__ import annotations

import math
from typing import List, Optional

from .series import (
    Series,
    change,
    ema,
    highest,
    lowest,
    pct_change,
    rma,
    r_squared,
    sma,
    stdev,
    to_float,
    linear_regression,
)
from .trend import _cci

__all__ = [
    "rsi", "macd", "stochastic", "stochrsi", "williams_r", "cci", "roc",
    "momentum", "cmo", "trix", "ultimate_oscillator", "awesome_oscillator",
    "accelerator_oscillator", "ppo", "apo", "fisher_transform", "connors_rsi",
    "relative_vigor_index", "dpo", "elder_ray", "kst", "chande_forecast",
    "qstick", "relative_momentum_index", "smi",
]


def _env(series: dict, note: Optional[str] = None) -> dict:
    return {"series": series, "levels": {}, "note": note}


def _close(ctx) -> Series:
    return [to_float(v) for v in ctx.close]


def _pct_rank(series: Series, period: int) -> Series:
    """Percent rank of the current value inside the trailing window."""
    out: Series = [None] * len(series)
    for i in range(period - 1, len(series)):
        window = series[i + 1 - period : i + 1]
        if any(v is None for v in window) or series[i] is None:
            continue
        below = sum(1 for v in window if v < series[i])
        out[i] = 100.0 * below / (period - 1) if period > 1 else None
    return out


# ---------------------------------------------------------------- 26 RSI
def rsi(ctx, p):
    period = int(p.get("period", 14))
    close = _close(ctx)
    delta = change(close, 1)
    gains = [d if (d is not None and d > 0) else (0.0 if d is not None else None) for d in delta]
    losses = [(-d) if (d is not None and d < 0) else (0.0 if d is not None else None) for d in delta]
    avg_gain = rma(gains, period)
    avg_loss = rma(losses, period)
    out: Series = []
    for g, l in zip(avg_gain, avg_loss):
        if g is None or l is None:
            out.append(None)
        elif l == 0:
            out.append(100.0)
        else:
            rs = g / l
            out.append(100.0 - 100.0 / (1.0 + rs))
    return _env({"rsi": out})


# ---------------------------------------------------------------- 27 MACD
def macd(ctx, p):
    fast = int(p.get("fast", 12))
    slow = int(p.get("slow", 26))
    signal = int(p.get("signal", 9))
    close = _close(ctx)
    ef = ema(close, fast)
    es = ema(close, slow)
    line = [None if a is None or b is None else a - b for a, b in zip(ef, es)]
    sig = ema(line, signal)
    hist = [None if a is None or b is None else a - b for a, b in zip(line, sig)]
    return _env({"macd": line, "signal": sig, "histogram": hist})


# ---------------------------------------------------------------- 28/29 Stochastic
def stochastic(ctx, p):
    period = int(p.get("period", 14))
    smooth = int(p.get("smooth_k", 3))
    d_period = int(p.get("period_d", 3))
    high = [to_float(v) for v in ctx.high]
    low = [to_float(v) for v in ctx.low]
    close = _close(ctx)
    hh = highest(high, period)
    ll = lowest(low, period)
    raw_k: Series = [
        None if None in (c, h, l) or (h - l) == 0 else 100.0 * (c - l) / (h - l)
        for c, h, l in zip(close, hh, ll)
    ]
    k = sma(raw_k, smooth)
    d = sma(k, d_period)
    return _env({"k": k, "d": d})


def stochrsi(ctx, p):
    rsi_period = int(p.get("rsi_period", 14))
    period = int(p.get("period", 14))
    k_smooth = int(p.get("smooth_k", 3))
    d_smooth = int(p.get("period_d", 3))
    r = rsi(ctx, {"period": rsi_period})["series"]["rsi"]
    hh = highest(r, period)
    ll = lowest(r, period)
    raw: Series = [
        None if None in (v, h, l) or (h - l) == 0 else 100.0 * (v - l) / (h - l)
        for v, h, l in zip(r, hh, ll)
    ]
    k = sma(raw, k_smooth)
    d = sma(k, d_smooth)
    return _env({"stochrsi": k, "k": k, "d": d})


# ---------------------------------------------------------------- 30 Williams %R
def williams_r(ctx, p):
    period = int(p.get("period", 14))
    high = [to_float(v) for v in ctx.high]
    low = [to_float(v) for v in ctx.low]
    close = _close(ctx)
    hh = highest(high, period)
    ll = lowest(low, period)
    out: Series = [
        None if None in (c, h, l) or (h - l) == 0 else -100.0 * (h - c) / (h - l)
        for c, h, l in zip(close, hh, ll)
    ]
    return _env({"williams_r": out})


# ---------------------------------------------------------------- 31 CCI
def cci(ctx, p):
    return _env({"cci": _cci(ctx, int(p.get("period", 20)))})


# ---------------------------------------------------------------- 32/33 ROC + Momentum
def roc(ctx, p):
    return _env({"roc": pct_change(_close(ctx), int(p.get("period", 9)))})


def momentum(ctx, p):
    period = int(p.get("period", 10))
    close = _close(ctx)
    out: Series = [None] * len(close)
    for i in range(period, len(close)):
        if close[i] is not None and close[i - period] is not None:
            out[i] = close[i] - close[i - period]
    return _env({"momentum": out})


# ---------------------------------------------------------------- 34 CMO
def cmo(ctx, p):
    period = int(p.get("period", 14))
    close = _close(ctx)
    delta = change(close, 1)
    out: Series = [None] * len(close)
    for i in range(period, len(close)):
        window = delta[i + 1 - period : i + 1]
        if any(v is None for v in window):
            continue
        up = sum(v for v in window if v > 0)
        down = sum(-v for v in window if v < 0)
        total = up + down
        out[i] = 0.0 if total == 0 else 100.0 * (up - down) / total
    return _env({"cmo": out})


# ---------------------------------------------------------------- 35 TRIX
def trix(ctx, p):
    period = int(p.get("period", 15))
    signal = int(p.get("signal", 9))
    close = _close(ctx)
    e = ema(ema(ema(close, period), period), period)
    line = pct_change(e, 1)
    sig = ema(line, signal)
    return _env({"trix": line, "signal": sig})


# ---------------------------------------------------------------- 36 Ultimate Oscillator
def ultimate_oscillator(ctx, p):
    p1 = int(p.get("period_1", 7))
    p2 = int(p.get("period_2", 14))
    p3 = int(p.get("period_3", 28))
    high = [to_float(v) for v in ctx.high]
    low = [to_float(v) for v in ctx.low]
    close = _close(ctx)
    n = len(close)
    bp: Series = [None] * n
    tr: Series = [None] * n
    for i in range(n):
        if None in (high[i], low[i], close[i]):
            continue
        prev = close[i - 1] if i > 0 else close[i]
        if prev is None:
            prev = close[i]
        bp[i] = close[i] - min(low[i], prev)
        tr[i] = max(high[i], prev) - min(low[i], prev)
    av1 = sma(bp, p1)
    at1 = sma(tr, p1)
    av2 = sma(bp, p2)
    at2 = sma(tr, p2)
    av3 = sma(bp, p3)
    at3 = sma(tr, p3)
    out: Series = []
    for a1, t1, a2, t2, a3, t3 in zip(av1, at1, av2, at2, av3, at3):
        if None in (a1, t1, a2, t2, a3, t3):
            out.append(None)
            continue
        denom = 7 * t1 + 14 * t2 + 28 * t3
        out.append(0.0 if denom == 0 else 100.0 * (7 * a1 + 14 * a2 + 28 * a3) / denom)
    return _env({"ultimate_oscillator": out})


# ---------------------------------------------------------------- 37/38 Awesome + Accelerator
def awesome_oscillator(ctx, p):
    short = int(p.get("short", 5))
    long = int(p.get("long", 34))
    high = [to_float(v) for v in ctx.high]
    low = [to_float(v) for v in ctx.low]
    median = [
        None if h is None or l is None else (h + l) / 2.0 for h, l in zip(high, low)
    ]
    a = sma(median, short)
    b = sma(median, long)
    return _env({"awesome": [None if x is None or y is None else x - y for x, y in zip(a, b)]})


def accelerator_oscillator(ctx, p):
    short = int(p.get("short", 5))
    long = int(p.get("long", 34))
    high = [to_float(v) for v in ctx.high]
    low = [to_float(v) for v in ctx.low]
    median = [None if h is None or l is None else (h + l) / 2.0 for h, l in zip(high, low)]
    ao = [None if x is None or y is None else x - y for x, y in zip(sma(median, short), sma(median, long))]
    smooth = sma(ao, 5)
    return _env(
        {"accelerator": [None if a is None or b is None else a - b for a, b in zip(ao, smooth)]}
    )


# ---------------------------------------------------------------- 39/40 PPO + APO
def ppo(ctx, p):
    fast = int(p.get("fast", 12))
    slow = int(p.get("slow", 26))
    signal = int(p.get("signal", 9))
    close = _close(ctx)
    ef = ema(close, fast)
    es = ema(close, slow)
    line = [
        None if a is None or b in (None, 0) else 100.0 * (a - b) / b for a, b in zip(ef, es)
    ]
    sig = ema(line, signal)
    hist = [None if a is None or b is None else a - b for a, b in zip(line, sig)]
    return _env({"ppo": line, "signal": sig, "histogram": hist})


def apo(ctx, p):
    fast = int(p.get("fast", 12))
    slow = int(p.get("slow", 26))
    close = _close(ctx)
    ef = ema(close, fast)
    es = ema(close, slow)
    return _env({"apo": [None if a is None or b is None else a - b for a, b in zip(ef, es)]})


# ---------------------------------------------------------------- 41 Fisher Transform
def fisher_transform(ctx, p):
    period = int(p.get("period", 9))
    high = [to_float(v) for v in ctx.high]
    low = [to_float(v) for v in ctx.low]
    n = len(high)
    hl2 = [None if h is None or l is None else (h + l) / 2.0 for h, l in zip(high, low)]
    hh = highest(hl2, period)
    ll = lowest(hl2, period)
    fisher: Series = [None] * n
    trigger: Series = [None] * n
    prev = 0.0
    prev_f = 0.0
    for i in range(n):
        if None in (hl2[i], hh[i], ll[i]) or (hh[i] - ll[i]) == 0:
            continue
        value = 2.0 * ((hl2[i] - ll[i]) / (hh[i] - ll[i]) - 0.5)
        value = max(-0.999, min(0.999, value))
        f = 0.5 * math.log((1 + value) / (1 - value)) + 0.5 * prev
        fisher[i] = f
        trigger[i] = prev_f
        prev, prev_f = f, f
    return _env({"fisher": fisher, "trigger": trigger})


# ---------------------------------------------------------------- 42 Connors RSI
def connors_rsi(ctx, p):
    rsi_period = int(p.get("rsi_period", 3))
    stoch_period = int(p.get("stoch_period", 3))
    roc_period = int(p.get("roc_period", 100))
    close = _close(ctx)
    r = rsi(ctx, {"period": rsi_period})["series"]["rsi"]
    hh = highest(r, stoch_period)
    ll = lowest(r, stoch_period)
    stoch: Series = [
        None if None in (v, h, l) or (h - l) == 0 else 100.0 * (v - l) / (h - l)
        for v, h, l in zip(r, hh, ll)
    ]
    pr = _pct_rank(change(close, 1), roc_period)
    out: Series = []
    for a, b, c in zip(r, stoch, pr):
        if None in (a, b, c):
            out.append(None)
        else:
            out.append((a + b + c) / 3.0)
    return _env({"connors_rsi": out})


# ---------------------------------------------------------------- 43 Relative Vigor Index
def relative_vigor_index(ctx, p):
    period = int(p.get("period", 10))
    high = [to_float(v) for v in ctx.high]
    low = [to_float(v) for v in ctx.low]
    close = _close(ctx)
    open_ = [to_float(v) for v in ctx.open]
    n = len(close)
    num: Series = [None] * n
    den: Series = [None] * n
    for i in range(n):
        if None in (close[i], open_[i], high[i], low[i]):
            continue
        num[i] = (close[i] - open_[i]) + 2 * (close[i - 1] - open_[i - 1]) if i > 0 and None not in (close[i - 1], open_[i - 1]) else close[i] - open_[i]
        den[i] = (high[i] - low[i]) + 2 * (high[i - 1] - low[i - 1]) if i > 0 and None not in (high[i - 1], low[i - 1]) else high[i] - low[i]
    weights = [1, 2, 2, 1]
    total = sum(weights)
    rvi: Series = [None] * n
    for i in range(3, n):
        nw = [num[i - k] for k in range(4)]
        dw = [den[i - k] for k in range(4)]
        if any(v is None for v in nw + dw):
            continue
        d = sum(w * v for w, v in zip(weights, dw))
        rvi[i] = 0.0 if d == 0 else sum(w * v for w, v in zip(weights, nw)) / d
    signal: Series = [None] * n
    for i in range(3, n):
        window = rvi[i - 3 : i + 1]
        if any(v is None for v in window):
            continue
        d = sum(w * v for w, v in zip(weights, window))
        signal[i] = d / total if total else None
    return _env({"rvi": rvi, "signal": signal})


# ---------------------------------------------------------------- 44 Detrended Price Oscillator
def dpo(ctx, p):
    period = int(p.get("period", 20))
    shift = period // 2 + 1
    close = _close(ctx)
    avg = sma(close, period)
    out: Series = [None] * len(close)
    for i in range(len(close)):
        src = i - shift
        if src < 0 or avg[i] is None or close[src] is None:
            continue
        out[i] = close[src] - avg[i]
    return _env({"dpo": out}, note="Displaced left by period/2+1 bars for display; the value at bar i uses the price from `shift` bars earlier.")


# ---------------------------------------------------------------- 45 Elder Ray
def elder_ray(ctx, p):
    period = int(p.get("period", 13))
    high = [to_float(v) for v in ctx.high]
    low = [to_float(v) for v in ctx.low]
    close = _close(ctx)
    avg = ema(close, period)
    bull = [None if h is None or a is None else h - a for h, a in zip(high, avg)]
    bear = [None if l is None or a is None else l - a for l, a in zip(low, avg)]
    return _env({"bull_power": bull, "bear_power": bear, "ema": avg})


# ---------------------------------------------------------------- 46 KST
def kst(ctx, p):
    r1 = int(p.get("r1", 10))
    r2 = int(p.get("r2", 15))
    r3 = int(p.get("r3", 20))
    r4 = int(p.get("r4", 30))
    sma1 = int(p.get("sma1", 10))
    sma2 = int(p.get("sma2", 10))
    sma3 = int(p.get("sma3", 10))
    sma4 = int(p.get("sma4", 15))
    signal = int(p.get("signal", 9))
    close = _close(ctx)
    m1 = sma(roc(ctx, {"period": r1})["series"]["roc"], sma1)
    m2 = sma(roc(ctx, {"period": r2})["series"]["roc"], sma2)
    m3 = sma(roc(ctx, {"period": r3})["series"]["roc"], sma3)
    m4 = sma(roc(ctx, {"period": r4})["series"]["roc"], sma4)
    line: Series = []
    for a, b, c, d in zip(m1, m2, m3, m4):
        if None in (a, b, c, d):
            line.append(None)
        else:
            line.append(a + 2 * b + 3 * c + 4 * d)
    sig = sma(line, signal)
    return _env({"kst": line, "signal": sig})


# ---------------------------------------------------------------- 47 Chande Forecast Oscillator
def chande_forecast(ctx, p):
    period = int(p.get("period", 14))
    close = _close(ctx)
    fitted, _s, _r = linear_regression(close, period)
    out: Series = [
        None if c in (None, 0) or f is None else 100.0 * (c - f) / c for c, f in zip(close, fitted)
    ]
    return _env({"chande_forecast": out})


# ---------------------------------------------------------------- 48 Qstick
def qstick(ctx, p):
    period = int(p.get("period", 14))
    close = _close(ctx)
    open_ = [to_float(v) for v in ctx.open]
    body = [None if c is None or o is None else c - o for c, o in zip(close, open_)]
    return _env({"qstick": sma(body, period)})


# ---------------------------------------------------------------- 49 Relative Momentum Index
def relative_momentum_index(ctx, p):
    period = int(p.get("period", 14))
    momentum_period = int(p.get("momentum_period", 4))
    close = _close(ctx)
    mom = change(close, momentum_period)
    gains = [m if (m is not None and m > 0) else (0.0 if m is not None else None) for m in mom]
    losses = [(-m) if (m is not None and m < 0) else (0.0 if m is not None else None) for m in mom]
    ag = rma(gains, period)
    al = rma(losses, period)
    out: Series = []
    for g, l in zip(ag, al):
        if g is None or l is None:
            out.append(None)
        elif l == 0:
            out.append(100.0)
        else:
            out.append(100.0 * g / (g + l))
    return _env({"rmi": out})


# ---------------------------------------------------------------- 50 SMI
def smi(ctx, p):
    period = int(p.get("period", 14))
    k_smooth = int(p.get("smooth_k", 3))
    d_smooth = int(p.get("smooth_d", 3))
    high = [to_float(v) for v in ctx.high]
    low = [to_float(v) for v in ctx.low]
    close = _close(ctx)
    hh = highest(high, period)
    ll = lowest(low, period)
    raw: Series = [
        None if None in (c, h, l) or (h - l) == 0 else 100.0 * (c - (h + l) / 2.0) / (h / 2.0 - l / 2.0)
        for c, h, l in zip(close, hh, ll)
    ]
    k = ema(ema(raw, k_smooth), k_smooth)
    d = ema(k, d_smooth)
    return _env({"smi": k, "signal": d})
