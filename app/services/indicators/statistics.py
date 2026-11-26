"""Advanced & statistical indicators (G: 131-150).

Indicators that need a second instrument (beta, correlation, pair spread,
cointegration) read it from ``ctx.extras["benchmark"]`` / ``["second"]`` and
report ``data_unavailable`` when the caller did not supply one.
"""

from __future__ import annotations

import math
from typing import Optional

from .series import (
    Series,
    change,
    ema,
    highest,
    linear_regression,
    pct_change,
    r_squared,
    sma,
    stdev,
    to_float,
    zscore,
    augmented_dickey_fuller,
    hurst_exponent,
)

__all__ = [
    "beta", "correlation_coefficient", "z_score", "mean_reversion",
    "linear_regression_channel", "standard_error_bands", "kalman_filter",
    "hurst", "entropy", "fractal_dimension_index", "r_squared_indicator",
    "variance_ratio", "pair_trading_spread", "cointegration",
    "adaptive_trend_finder", "cycle_indicator", "ehlers_roofing_filter",
    "ehlers_super_smoother", "hilbert_transform", "dominant_cycle_period",
]


def _env(series: dict, note: Optional[str] = None, meta: Optional[dict] = None, levels: Optional[dict] = None) -> dict:
    out = {"series": series, "levels": levels or {}, "note": note}
    if meta:
        out["meta"] = meta
    return out


def _close(ctx) -> Series:
    return [to_float(v) for v in ctx.close]


def _extras(ctx) -> dict:
    return getattr(ctx, "extras", {}) or {}


def _second(ctx) -> Optional[Series]:
    values = _extras(ctx).get("benchmark") or _extras(ctx).get("second")
    if not values:
        return None
    series = [to_float(v) for v in values]
    if len(series) != len(_close(ctx)):
        return None
    return series


def _covariance(a: Series, b: Series, period: int) -> Series:
    n = len(a)
    out: Series = [None] * n
    for i in range(period - 1, n):
        wa = a[i + 1 - period : i + 1]
        wb = b[i + 1 - period : i + 1]
        if any(v is None for v in wa + wb):
            continue
        ma = sum(wa) / period
        mb = sum(wb) / period
        out[i] = sum((x - ma) * (y - mb) for x, y in zip(wa, wb)) / period
    return out


# ---------------------------------------------------------------- 131 Beta
def beta(ctx, p):
    period = int(p.get("period", 60))
    second = _second(ctx)
    if second is None:
        return _env({}, note="data_unavailable")
    a = pct_change(_close(ctx), 1)
    b = pct_change(second, 1)
    cov = _covariance(a, b, period)
    var = [None if v is None else v * v for v in b]
    var_s = sma(var, period)
    out = [None if c is None or v in (None, 0) else c / v for c, v in zip(cov, var_s)]
    return _env({"beta": out}, note="Beta vs the benchmark series supplied in extras.benchmark.")


# ---------------------------------------------------------------- 132 Correlation
def correlation_coefficient(ctx, p):
    period = int(p.get("period", 30))
    second = _second(ctx)
    if second is None:
        return _env({}, note="data_unavailable")
    a, b = _close(ctx), second
    cov = _covariance(a, b, period)
    sa = sma(a, period)
    sb = sma(b, period)
    out: Series = []
    for i in range(len(a)):
        if i < period - 1 or cov[i] is None:
            out.append(None)
            continue
        wa = a[i + 1 - period : i + 1]
        wb = b[i + 1 - period : i + 1]
        if any(v is None for v in wa + wb):
            out.append(None)
            continue
        va = sum((x - sa[i]) ** 2 for x in wa)
        vb = sum((y - sb[i]) ** 2 for y in wb)
        out.append(None if va <= 0 or vb <= 0 else cov[i] / math.sqrt(va * vb))
    return _env({"correlation": out})


# ---------------------------------------------------------------- 133 Z-score
def z_score(ctx, p):
    period = int(p.get("period", 20))
    return _env({"z_score": zscore(_close(ctx), period)})


# ---------------------------------------------------------------- 134 Mean reversion
def mean_reversion(ctx, p):
    period = int(p.get("period", 20))
    z = zscore(_close(ctx), period)
    avg = sma(_close(ctx), period)
    out: Series = [None if v is None else -v for v in z]
    signal: Series = [None if v is None else (1 if v < -1 else (-1 if v > 1 else 0)) for v in z]
    return _env({"mean_reversion": out, "signal": signal, "mean": avg}, note="Signal +1 = stretched below the mean (revert up), -1 = stretched above.")


# ---------------------------------------------------------------- 135 Linear regression channel
def linear_regression_channel(ctx, p):
    period = int(p.get("period", 50))
    mult = float(p.get("multiplier", 2.0))
    close = _close(ctx)
    fitted, slope_s, r2 = linear_regression(close, period)
    n = len(close)
    resid: Series = [None] * n
    for i in range(period - 1, n):
        window = close[i + 1 - period : i + 1]
        f = fitted[i]
        if f is None or any(v is None for v in window):
            continue
        # residual of the fitted line at each bar in the window
        b = slope_s[i]
        intercept = f - b * (period - 1)
        residuals = [y - (intercept + b * x) for x, y in zip(range(period), window)]
        mean_r = sum(residuals) / period
        resid[i] = math.sqrt(sum((r - mean_r) ** 2 for r in residuals) / period)
    upper = [None if f is None or s is None else f + mult * s for f, s in zip(fitted, resid)]
    lower = [None if f is None or s is None else f - mult * s for f, s in zip(fitted, resid)]
    return _env({"middle": fitted}, levels={"upper": upper, "lower": lower}, note=f"±{mult}σ channel; R²={r2[-1] if r2 else None}.")


# ---------------------------------------------------------------- 136 Standard error bands
def standard_error_bands(ctx, p):
    period = int(p.get("period", 20))
    mult = float(p.get("multiplier", 2.0))
    close = _close(ctx)
    fitted, slope_s, _r = linear_regression(close, period)
    n = len(close)
    se: Series = [None] * n
    for i in range(period - 1, n):
        window = close[i + 1 - period : i + 1]
        f = fitted[i]
        b = slope_s[i]
        if f is None or b is None or any(v is None for v in window):
            continue
        intercept = f - b * (period - 1)
        residuals = [y - (intercept + b * x) for x, y in zip(range(period), window)]
        dof = max(1, period - 2)
        s = math.sqrt(sum(r * r for r in residuals) / dof)
        x_mean = (period - 1) / 2.0
        sxx = sum((x - x_mean) ** 2 for x in range(period)) or 1.0
        se[i] = s * math.sqrt(1.0 / period + ((period - 1 - x_mean) ** 2) / sxx)
    upper = [None if f is None or e is None else f + mult * e for f, e in zip(fitted, se)]
    lower = [None if f is None or e is None else f - mult * e for f, e in zip(fitted, se)]
    return _env({"middle": fitted}, levels={"upper": upper, "lower": lower})


# ---------------------------------------------------------------- 137 Kalman filter
def kalman_filter(ctx, p):
    """Local-level (random-walk) Kalman filter with a fixed measurement noise."""
    q = float(p.get("process_noise", 0.01))
    r = float(p.get("measurement_noise", 0.1))
    close = _close(ctx)
    out: Series = [None] * len(close)
    level = None
    error = 1.0
    for i, value in enumerate(close):
        if value is None:
            continue
        if level is None:
            level, error = value, r
        else:
            error = error + q
            gain = error / (error + r)
            level = level + gain * (value - level)
            error = (1 - gain) * error
        out[i] = level
    return _env({"kalman": out}, note=f"Local-level model, q={q}, r={r}.")


# ---------------------------------------------------------------- 138 Hurst
def hurst(ctx, p):
    max_lag = int(p.get("max_lag", 20))
    value = hurst_exponent(_close(ctx), max_lag)
    series: Series = [None] * len(_close(ctx))
    if value is not None and series:
        series[-1] = value
    return _env(
        {"hurst": series},
        meta={"hurst": value},
        note="H<0.5 mean reverting, ~0.5 random walk, >0.5 trending." if value is not None else "Insufficient history",
    )


# ---------------------------------------------------------------- 139 Entropy
def entropy(ctx, p):
    period = int(p.get("period", 50))
    bins = int(p.get("bins", 16))
    close = _close(ctx)
    returns = pct_change(close, 1)
    n = len(returns)
    out: Series = [None] * n
    for i in range(period, n):
        window = [r for r in returns[i + 1 - period : i + 1] if r is not None]
        if len(window) < period // 2:
            continue
        lo, hi = min(window), max(window)
        if hi <= lo:
            out[i] = 0.0
            continue
        counts = [0] * bins
        width = (hi - lo) / bins
        for r in window:
            idx = min(bins - 1, int((r - lo) / width))
            counts[idx] += 1
        total = sum(counts)
        h = 0.0
        for c in counts:
            if c:
                pr = c / total
                h -= pr * math.log(pr)
        out[i] = h / math.log(bins)
    return _env({"entropy": out}, note="Normalised Shannon entropy of returns (0 = ordered, 1 = random).")


# ---------------------------------------------------------------- 140 Fractal dimension index
def fractal_dimension_index(ctx, p):
    period = int(p.get("period", 30))
    close = _close(ctx)
    n = len(close)
    out: Series = [None] * n
    for i in range(period, n):
        window = close[i + 1 - period : i + 1]
        if any(v is None for v in window):
            continue
        path = sum(abs(window[j] - window[j - 1]) for j in range(1, period))
        span = max(window) - min(window)
        if path <= 0 or span <= 0:
            out[i] = 2.0
            continue
        d = max(window) - min(window)
        # Katz fractal dimension
        out[i] = max(1.0, min(2.0, math.log10(period) / (math.log10(period) + math.log10(d / (path / (period - 1))))))
    return _env({"fractal_dimension": out}, note="Katz fractal dimension; 1 = straight line, 2 = space filling.")


# ---------------------------------------------------------------- 141 R-squared
def r_squared_indicator(ctx, p):
    return _env({"r_squared": r_squared(_close(ctx), int(p.get("period", 20)))})


# ---------------------------------------------------------------- 142 Variance ratio
def variance_ratio(ctx, p):
    q = int(p.get("q", 5))
    close = _close(ctx)
    d1 = change(close, 1)
    dq = change(close, q)
    var1 = sma([None if v is None else v * v for v in d1], q)
    varq = sma([None if v is None else v * v for v in dq], q)
    out = [None if a in (None, 0) or b is None else b / (q * a) for a, b in zip(var1, varq)]
    return _env({"variance_ratio": out}, note=f"Lo-MacKinlay VR({q}); >1 trending, <1 mean reverting.")


# ---------------------------------------------------------------- 143 Pair spread
def pair_trading_spread(ctx, p):
    period = int(p.get("period", 60))
    second = _second(ctx)
    if second is None:
        return _env({}, note="data_unavailable")
    a, b = _close(ctx), second
    log_a = [None if v in (None, 0) else math.log(v) for v in a]
    log_b = [None if v in (None, 0) else math.log(v) for v in b]
    n = len(a)
    hedge: Series = [None] * n
    spread: Series = [None] * n
    z: Series = [None] * n
    for i in range(period - 1, n):
        wa = log_a[i + 1 - period : i + 1]
        wb = log_b[i + 1 - period : i + 1]
        if any(v is None for v in wa + wb):
            continue
        mb = sum(wb) / period
        ma = sum(wa) / period
        var_b = sum((x - mb) ** 2 for x in wb)
        if var_b <= 0:
            continue
        h = sum((x - ma) * (y - mb) for x, y in zip(wa, wb)) / var_b
        residuals = [x - h * y for x, y in zip(wa, wb)]
        sd = math.sqrt(sum(r * r for r in residuals) / period) or None
        hedge[i] = h
        spread[i] = residuals[-1]
        z[i] = None if sd in (None, 0) else residuals[-1] / sd
    return _env({"spread": spread, "hedge_ratio": hedge, "z": z}, note="Spread = log(A) - β·log(B) over the rolling window.")


# ---------------------------------------------------------------- 144 Cointegration
def cointegration(ctx, p):
    period = int(p.get("period", 120))
    second = _second(ctx)
    if second is None:
        return _env({}, note="data_unavailable")
    a, b = _close(ctx), second
    n = min(len(a), len(b))
    log_a = [None if v in (None, 0) else math.log(v) for v in a[:n]]
    log_b = [None if v in (None, 0) else math.log(v) for v in b[:n]]
    window_a = log_a[-period:]
    window_b = log_b[-period:]
    if len(window_a) < 20 or any(v is None for v in window_a + window_b):
        return _env({}, note="Insufficient data")
    mb = sum(window_b) / len(window_b)
    ma = sum(window_a) / len(window_a)
    var_b = sum((x - mb) ** 2 for x in window_b) or 1e-12
    hedge = sum((x - ma) * (y - mb) for x, y in zip(window_a, window_b)) / var_b
    spread = [x - hedge * y for x, y in zip(window_a, window_b)]
    stat = augmented_dickey_fuller(spread, 1)
    series: Series = [None] * n
    if stat is not None:
        series[-1] = stat
    return _env(
        {"cointegration": series},
        meta={"adf_statistic": stat, "hedge_ratio": hedge, "critical_1pct": -3.43},
        note="ADF on the spread; cointegrated when the statistic is below -3.43 (1% level). p-values need statsmodels.",
    )


# ---------------------------------------------------------------- 145 Adaptive trend finder
def adaptive_trend_finder(ctx, p):
    fast = int(p.get("fast", 10))
    slow = int(p.get("slow", 30))
    close = _close(ctx)
    fast_ma = ema(close, fast)
    slow_ma = ema(close, slow)
    change_fast = change(fast_ma, 1)
    change_slow = change(slow_ma, 1)
    efficiency = [
        None if a is None or b is None or b == 0 else min(1.0, abs(a / b)) if b != 0 else None
        for a, b in zip(change(close, fast), change_fast)
    ]
    out: Series = [
        None if e is None else (f if e > 0.5 else s)
        for e, f, s in zip(efficiency, fast_ma, slow_ma)
    ]
    return _env(
        {"adaptive_ma": out, "efficiency": efficiency},
        note="Uses the fast MA when the efficiency ratio > 0.5 (trending) and the slow MA otherwise.",
    )


# ---------------------------------------------------------------- 146-150 Ehlers family
def ehlers_super_smoother(ctx, p):
    period = float(p.get("period", 10))
    a1 = math.exp(-1.414 * math.pi / period)
    b1 = 2 * a1 * math.cos(1.414 * math.pi / period)
    c2, c3 = b1, -(a1 * a1)
    c1 = 1 - c2 - c3
    close = _close(ctx)
    out: Series = [None] * len(close)
    prev_in = prev_out = prev_out2 = None
    for i, value in enumerate(close):
        if value is None:
            continue
        if prev_in is None:
            prev_in = prev_out = prev_out2 = value
            out[i] = value
            continue
        current = c1 * (value + prev_in) / 2.0 + c2 * prev_out + c3 * prev_out2
        out[i] = current
        prev_in, prev_out2, prev_out = value, prev_out, current
    return _env({"super_smoother": out}, note="Ehlers 2-pole Butterworth super smoother.")


def ehlers_roofing_filter(ctx, p):
    hp_period = float(p.get("hp_period", 48))
    ss_period = float(p.get("smooth_period", 10))
    a1 = math.exp(-1.414 * math.pi / hp_period)
    b1 = 2 * a1 * math.cos(1.414 * math.pi / hp_period)
    c2, c3 = b1, -(a1 * a1)
    c1 = 1 - c2 - c3
    close = _close(ctx)
    hp: Series = [None] * len(close)
    prev_in = prev_out = prev_out2 = None
    for i, value in enumerate(close):
        if value is None:
            continue
        if prev_in is None:
            prev_in = prev_out = prev_out2 = value
            hp[i] = 0.0
            continue
        current = c1 * (value + prev_in) / 2.0 + c2 * prev_out + c3 * prev_out2
        hp[i] = value - current
        prev_in, prev_out2, prev_out = value, prev_out, current
    return _env({"roofing": ehlers_super_smoother(ctx, {"period": ss_period})["series"]["super_smoother"], "high_pass": hp}, note="2-pole high-pass (48) then super smoother (10).")


def hilbert_transform(ctx, p):
    """Ehlers Hilbert transform: in-phase / quadrature components."""
    close = _close(ctx)
    n = len(close)
    detrender: Series = [None] * n
    i1: Series = [None] * n
    q1: Series = [None] * n
    ji: Series = [None] * n
    jq: Series = [None] * n
    i2: Series = [None] * n
    q2: Series = [None] * n
    re: Series = [None] * n
    im: Series = [None] * n
    period: Series = [None] * n
    smooth_period: Series = [None] * n
    for i in range(n):
        if i < 7 or close[i] is None:
            continue
        window = close[i - 6 : i + 1]
        if any(v is None for v in window):
            continue
        detrender[i] = 0.0962 * window[6] + 0.5769 * window[5] - 0.5769 * window[3] - 0.0962 * window[1]
        q1[i] = detrender[i]
        i1[i] = close[i - 7] if close[i - 7] is not None else None
        if i1[i] is None or i < 12 or i1[i - 2] is None:
            continue
        ji[i] = 0.0962 * detrender[i] + 0.5769 * (i1[i - 1] or 0) - 0.5769 * (i1[i - 3] or 0) - 0.0962 * (i1[i - 5] or 0)
        jq[i] = 0.0962 * q1[i] + 0.5769 * (q1[i - 1] or 0) - 0.5769 * (q1[i - 3] or 0) - 0.0962 * (q1[i - 5] or 0)
        i2[i] = 0.2 * (i1[i] + 0.75 * (i1[i] - i1[i - 2])) + 0.8 * (i2[i - 1] or 0)
        q2[i] = 0.2 * (q1[i] + 0.75 * (q1[i] - q1[i - 2])) + 0.8 * (q2[i - 1] or 0)
        re[i] = 0.2 * (i2[i] + 0.75 * (i2[i] - (i2[i - 2] or 0))) + 0.8 * (re[i - 1] or 0)
        im[i] = 0.2 * (q2[i] + 0.75 * (q2[i] - (q2[i - 2] or 0))) + 0.8 * (im[i - 1] or 0)
        if re[i] is not None and im[i] is not None and (re[i] != 0 or im[i] != 0):
            phase = math.degrees(math.atan2(im[i], re[i]))
            prev = period[i - 1]
            if prev is not None and 0 < phase < 180:
                period[i] = 360.0 / phase if phase > 0 else prev
            elif prev is not None:
                period[i] = prev * 0.9 + (360.0 / phase if phase > 0 else prev) * 0.1
            if period[i] is not None:
                smooth_period[i] = 0.2 * period[i] + 0.8 * (smooth_period[i - 1] or period[i])
    return _env({"i1": i1, "q1": q1, "re": re, "im": im, "period": period}, note="Ehlers Hilbert transform (in-phase/quadrature).")


def dominant_cycle_period(ctx, p):
    ht = hilbert_transform(ctx, p)["series"]["period"]
    smooth = [None if v is None else v for v in ht]
    last = next((v for v in reversed(smooth) if v is not None), None)
    series: Series = [None] * len(smooth)
    if last is not None and series:
        series[-1] = last
    return _env({"dominant_cycle": series}, meta={"dominant_cycle": last}, note="Dominant cycle in bars from the Hilbert transform.")


def cycle_indicator(ctx, p):
    period = int(p.get("period", 20))
    close = _close(ctx)
    dom = next((v for v in reversed(hilbert_transform(ctx, {})["series"]["period"] or []) if v is not None), None)
    length = int(dom) if dom else period
    if length < 2 or length > len(close):
        length = period
    n = len(close)
    out: Series = [None] * n
    for i in range(length, n):
        window = close[i + 1 - length : i + 1]
        if any(v is None for v in window):
            continue
        avg = sum(window) / length
        slope = (window[-1] - window[0]) / max(1, length - 1)
        out[i] = avg + slope * (length - 1) / 2.0
    return _env({"cycle": out}, meta={"cycle_length": length}, note="Cycle-length moving average projection (detrended cycle proxy).")
