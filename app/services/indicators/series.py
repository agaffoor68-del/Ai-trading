"""Pure-Python technical-analysis series math.

No numpy / pandas dependency: the engine must run on the production host
(Render, Python 3.11) and in low-resource environments alike.

Conventions
-----------
* Every public function takes a ``Sequence[Optional[float]]`` and returns a
  ``list`` of the SAME length, padded with ``None`` where the value is not
  defined yet (insufficient history).  This keeps every series aligned with
  the candle array, which is what the chart layer and the backtester expect.
* ``None`` inputs are propagated: a single missing candle makes the affected
  output ``None`` instead of raising or silently producing a wrong number.
* Functions never look ahead: ``out[i]`` depends only on ``values[: i + 1]``.
"""

from __future__ import annotations

import math
from typing import Callable, Iterable, List, Optional, Sequence

Number = Optional[float]
Series = List[Number]

__all__ = [
    "is_num",
    "to_float",
    "clean",
    "mean",
    "median",
    "sma",
    "ema",
    "rma",
    "wma",
    "dema",
    "tema",
    "hma",
    "kama",
    "alma",
    "zlema",
    "t3",
    "mcginley",
    "stdev",
    "variance",
    "rolling",
    "rolling_apply",
    "highest",
    "lowest",
    "sum_series",
    "change",
    "pct_change",
    "roc",
    "cumsum",
    "safe_div",
    "safe_mul",
    "clamp",
    "linear_regression",
    "slope",
    "r_squared",
    "zscore",
    "augmented_dickey_fuller",
    "hurst_exponent",
    "safe_log",
]


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------
def is_num(value: object) -> bool:
    """True for a finite real number (``bool`` is rejected on purpose)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def to_float(value: object) -> Number:
    """Best-effort numeric conversion, ``None`` when not finite."""
    if is_num(value):
        return float(value)  # type: ignore[arg-type]
    return None


def clean(values: Iterable[object]) -> List[Number]:
    return [to_float(v) for v in values]


def safe_div(a: Number, b: Number, default: Number = None) -> Number:
    if a is None or b is None or b == 0:
        return default
    return a / b


def safe_mul(a: Number, b: Number, default: Number = None) -> Number:
    if a is None or b is None:
        return default
    return a * b


def clamp(value: Number, low: Number, high: Number) -> Number:
    if value is None:
        return None
    if low is not None and value < low:
        return low
    if high is not None and value > high:
        return high
    return value


def safe_log(value: Number) -> Number:
    if value is None or value <= 0:
        return None
    return math.log(value)


def mean(values: Sequence[Number]) -> Number:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def median(values: Sequence[Number]) -> Number:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    mid = len(vals) // 2
    if len(vals) % 2:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2.0


def rolling(values: Sequence[Number], period: int, fn: Callable[[List[float]], float]) -> Series:
    """Apply ``fn`` to every full window of ``period`` items."""
    period = max(1, int(period))
    out: Series = [None] * len(values)
    if period > len(values):
        return out
    window: List[float] = []
    for i, raw in enumerate(values):
        value = to_float(raw)
        if value is None:
            window = []
            continue
        window.append(value)
        if len(window) > period:
            window.pop(0)
        if len(window) == period:
            out[i] = fn(window)
    return out


def rolling_apply(values: Sequence[Number], period: int, fn: Callable[[List[float]], float]) -> Series:
    """Alias kept for readability at call sites."""
    return rolling(values, period, fn)


def sma(values: Sequence[Number], period: int) -> Series:
    return rolling(values, period, lambda w: sum(w) / len(w))


def ema(values: Sequence[Number], period: int) -> Series:
    """Exponential MA seeded with the SMA of the first ``period`` values."""
    period = max(1, int(period))
    out: Series = [None] * len(values)
    alpha = 2.0 / (period + 1.0)
    seed = sma(values, period)
    prev: Number = None
    for i, raw in enumerate(values):
        value = to_float(raw)
        if value is None:
            prev = None
            continue
        if prev is None:
            if seed[i] is not None:
                prev = seed[i]
                out[i] = prev
            continue
        prev = value * alpha + prev * (1.0 - alpha)
        out[i] = prev
    return out


def rma(values: Sequence[Number], period: int) -> Series:
    """Wilder's smoothing (used by RSI / ATR / ADX)."""
    period = max(1, int(period))
    out: Series = [None] * len(values)
    seed = sma(values, period)
    prev: Number = None
    for i, raw in enumerate(values):
        value = to_float(raw)
        if value is None:
            prev = None
            continue
        if prev is None:
            if seed[i] is not None:
                prev = seed[i]
                out[i] = prev
            continue
        prev = (prev * (period - 1) + value) / period
        out[i] = prev
    return out


def wma(values: Sequence[Number], period: int) -> Series:
    period = max(1, int(period))
    denom = period * (period + 1) / 2.0
    return rolling(values, period, lambda w: sum(v * (i + 1) for i, v in enumerate(w)) / denom)


def dema(values: Sequence[Number], period: int) -> Series:
    e1 = ema(values, period)
    e2 = ema(e1, period)
    return [None if a is None or b is None else 2 * a - b for a, b in zip(e1, e2)]


def tema(values: Sequence[Number], period: int) -> Series:
    e1 = ema(values, period)
    e2 = ema(e1, period)
    e3 = ema(e2, period)
    return [
        None if a is None or b is None or c is None else 3 * a - 3 * b + c
        for a, b, c in zip(e1, e2, e3)
    ]


def hma(values: Sequence[Number], period: int) -> Series:
    period = max(1, int(period))
    half = max(1, period // 2)
    sqrt_p = max(1, int(math.sqrt(period)))
    w_half = wma(values, half)
    w_full = wma(values, period)
    raw = [
        None if a is None or b is None else 2 * a - b
        for a, b in zip(w_half, w_full)
    ]
    return wma(raw, sqrt_p)


def kama(values: Sequence[Number], period: int = 10, fast: int = 2, slow: int = 30) -> Series:
    """Kaufman Adaptive Moving Average."""
    period = max(2, int(period))
    fast_sc = 2.0 / (fast + 1.0)
    slow_sc = 2.0 / (slow + 1.0)
    out: Series = [None] * len(values)
    prev: Number = None
    for i in range(len(values)):
        value = to_float(values[i])
        if value is None:
            prev = None
            continue
        if i < period or prev is None:
            window = [to_float(v) for v in values[i - period + 1 : i + 1]] if i + 1 >= period else []
            if len(window) < period or any(v is None for v in window):
                continue
            prev = sum(window) / period
            out[i] = prev
            continue
        change = abs(value - to_float(values[i - period]))
        volatility = sum(
            abs(to_float(values[j]) - to_float(values[j - 1]))
            for j in range(i - period + 1, i + 1)
            if to_float(values[j]) is not None and to_float(values[j - 1]) is not None
        )
        er = safe_div(change, volatility, 0.0) or 0.0
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
        prev = prev + sc * (value - prev)
        out[i] = prev
    return out


def alma(values: Sequence[Number], period: int = 21, offset: float = 0.85, sigma: float = 6.0) -> Series:
    """Arnaud Legoux MA: Gaussian-weighted window."""
    period = max(1, int(period))
    m = offset * (period - 1)
    s = period / sigma
    weights = [math.exp(-((i - m) ** 2) / (2 * s * s)) for i in range(period)]
    total = sum(weights) or 1.0
    return rolling(values, period, lambda w: sum(v * wt for v, wt in zip(w, weights)) / total)


def zlema(values: Sequence[Number], period: int = 20) -> Series:
    """Zero-Lag EMA (de-lagged input, then EMA)."""
    period = max(1, int(period))
    lag = (period - 1) // 2
    adjusted: Series = []
    for i, raw in enumerate(values):
        value = to_float(raw)
        past = to_float(values[i - lag]) if i - lag >= 0 else None
        adjusted.append(None if value is None or past is None else value + (value - past))
    return ema(adjusted, period)


def t3(values: Sequence[Number], period: int = 5, v_factor: float = 0.7) -> Series:
    """Tillson T3 (triple smoothed generalized DEMA)."""
    e1 = ema(values, period)
    e2 = ema(e1, period)
    e3 = ema(e2, period)
    e4 = ema(e3, period)
    e5 = ema(e4, period)
    e6 = ema(e5, period)
    c1 = -(v_factor ** 3)
    c2 = 3 * v_factor ** 2 + 3 * v_factor ** 3
    c3 = -6 * v_factor ** 2 - 3 * v_factor - 3 * v_factor ** 3
    c4 = 1 + 3 * v_factor + v_factor ** 3 + 3 * v_factor ** 2
    out: Series = []
    for a, b, c, d, e, f in zip(e1, e2, e3, e4, e5, e6):
        if None in (a, b, c, d, e, f):
            out.append(None)
        else:
            out.append(c1 * a + c2 * b + c3 * c + c4 * d)
    return out


def mcginley(values: Sequence[Number], period: int = 14) -> Series:
    """McGinley Dynamic: self-adjusting EMA."""
    period = max(1, int(period))
    out: Series = [None] * len(values)
    prev: Number = None
    for i, raw in enumerate(values):
        value = to_float(raw)
        if value is None:
            prev = None
            continue
        if prev is None:
            if i + 1 < period:
                continue
            window = [to_float(v) for v in values[i + 1 - period : i + 1]]
            if any(v is None for v in window):
                continue
            prev = sum(window) / period
            out[i] = prev
            continue
        denom = period * (value / prev) ** 4
        if denom == 0:
            out[i] = prev
            continue
        prev = prev + (value - prev) / denom
        out[i] = prev
    return out


def variance(values: Sequence[Number], period: int, ddof: int = 0) -> Series:
    period = max(1, int(period))

    def _var(window: List[float]) -> float:
        avg = sum(window) / len(window)
        return sum((v - avg) ** 2 for v in window) / (len(window) - ddof if len(window) > ddof else 1)

    return rolling(values, period, _var)


def stdev(values: Sequence[Number], period: int, ddof: int = 0) -> Series:
    return [None if v is None else math.sqrt(max(v, 0.0)) for v in variance(values, period, ddof)]


def highest(values: Sequence[Number], period: int) -> Series:
    return rolling(values, period, max)


def lowest(values: Sequence[Number], period: int) -> Series:
    return rolling(values, period, min)


def sum_series(values: Sequence[Number], period: int) -> Series:
    return rolling(values, period, lambda w: sum(w))


def change(values: Sequence[Number], period: int = 1) -> Series:
    period = max(1, int(period))
    out: Series = [None] * len(values)
    for i in range(period, len(values)):
        a, b = to_float(values[i]), to_float(values[i - period])
        if a is not None and b is not None:
            out[i] = a - b
    return out


def pct_change(values: Sequence[Number], period: int = 1) -> Series:
    period = max(1, int(period))
    out: Series = [None] * len(values)
    for i in range(period, len(values)):
        a, b = to_float(values[i]), to_float(values[i - period])
        if a is not None and b not in (None, 0):
            out[i] = (a - b) / b * 100.0
    return out


def roc(values: Sequence[Number], period: int = 9) -> Series:
    return pct_change(values, period)


def cumsum(values: Sequence[Number]) -> Series:
    total = 0.0
    out: Series = []
    for raw in values:
        value = to_float(raw)
        if value is None:
            out.append(None)
            continue
        total += value
        out.append(total)
    return out


def linear_regression(values: Sequence[Number], period: int) -> tuple[Series, Series, Series]:
    """Rolling OLS. Returns ``(value, slope, r2)`` series.

    ``value`` is the fitted value at the last bar of each window (the
    "linear regression" indicator), ``slope`` is per-bar change and ``r2``
    the goodness of fit.
    """
    period = max(2, int(period))
    n = len(values)
    out_v: Series = [None] * n
    out_s: Series = [None] * n
    out_r: Series = [None] * n
    x_mean = (period - 1) / 2.0
    denom = sum((i - x_mean) ** 2 for i in range(period)) or 1.0
    for i in range(period - 1, n):
        window = [to_float(v) for v in values[i + 1 - period : i + 1]]
        if any(v is None for v in window):
            continue
        y_mean = sum(window) / period
        cov = sum((x - x_mean) * (y - y_mean) for x, y in zip(range(period), window))
        slope = cov / denom
        intercept = y_mean - slope * x_mean
        fitted = intercept + slope * (period - 1)
        ss_tot = sum((y - y_mean) ** 2 for y in window)
        ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(range(period), window))
        out_v[i] = fitted
        out_s[i] = slope
        out_r[i] = 1.0 if ss_tot == 0 else max(0.0, min(1.0, 1 - ss_res / ss_tot))
    return out_v, out_s, out_r


def slope(values: Sequence[Number], period: int) -> Series:
    return linear_regression(values, period)[1]


def r_squared(values: Sequence[Number], period: int) -> Series:
    return linear_regression(values, period)[2]


def zscore(values: Sequence[Number], period: int) -> Series:
    avg = sma(values, period)
    sd = stdev(values, period)
    return [safe_div(a - b, c) if None not in (a, b, c) else None for a, b, c in zip(values, avg, sd)]


def true_range(high: Sequence[Number], low: Sequence[Number], close: Sequence[Number]) -> Series:
    """Wilder's True Range (uses the previous close, never the next one)."""
    out: Series = []
    prev_close: Number = None
    for h, l, c in zip(high, low, close):
        h, l = to_float(h), to_float(l)
        if h is None or l is None:
            out.append(None)
            prev_close = to_float(c)
            continue
        if prev_close is None:
            out.append(h - l)
        else:
            out.append(max(h - l, abs(h - prev_close), abs(l - prev_close)))
        prev_close = to_float(c)
    return out


def atr(high: Sequence[Number], low: Sequence[Number], close: Sequence[Number], period: int = 14) -> Series:
    """Average True Range (Wilder / RMA smoothing)."""
    return rma(true_range(high, low, close), period)


def pivot_highs(high: Sequence[Number], left: int = 3, right: int = 3) -> List[tuple[int, float]]:
    """Indices of confirmed swing highs.

    A bar ``i`` is a pivot high when its high is the strict maximum of the
    window ``[i-left, i+right]``.  Confirmation therefore lags ``right`` bars,
    which is what makes the result non-repainting.
    """
    values = [to_float(v) for v in high]
    out: List[tuple[int, float]] = []
    for i in range(left, len(values) - right):
        window = values[i - left : i + right + 1]
        if any(v is None for v in window):
            continue
        if values[i] == max(window) and window.count(values[i]) == 1:
            out.append((i, values[i]))
    return out


def pivot_lows(low: Sequence[Number], left: int = 3, right: int = 3) -> List[tuple[int, float]]:
    values = [to_float(v) for v in low]
    out: List[tuple[int, float]] = []
    for i in range(left, len(values) - right):
        window = values[i - left : i + right + 1]
        if any(v is None for v in window):
            continue
        if values[i] == min(window) and window.count(values[i]) == 1:
            out.append((i, values[i]))
    return out


def augmented_dickey_fuller(values: Sequence[Number], lag: int = 1) -> Number:
    """ADF test statistic with a constant term (no trend).

    Regression: dy_t = c + gamma * y_{t-1} + sum(delta_i * dy_{t-i}) + e
    Returns the t-statistic of ``gamma``; ``None`` when undefined.
    """
    y = [v for v in (to_float(x) for x in values) if v is not None]
    lag = max(1, int(lag))
    if len(y) < lag + 5:
        return None
    dy = [y[i] - y[i - 1] for i in range(1, len(y))]
    rows = []
    for t in range(lag, len(dy)):
        row = [1.0, y[t]]  # constant, y_{t-1} (dy index t-1 == y[t])
        for k in range(1, lag + 1):
            row.append(dy[t - k])
        rows.append((row, dy[t]))
    if len(rows) < 4:
        return None
    p = len(rows[0][0])
    xtx = [[0.0] * p for _ in range(p)]
    xty = [0.0] * p
    for row, target in rows:
        for a in range(p):
            xty[a] += row[a] * target
            for b in range(p):
                xtx[a][b] += row[a] * row[b]
    # Gauss-Jordan inverse
    inv = _invert(xtx)
    if inv is None:
        return None
    beta = [sum(inv[a][b] * xty[b] for b in range(p)) for a in range(p)]
    resid = [target - sum(row[a] * beta[a] for a in range(p)) for row, target in rows]
    dof = len(rows) - p
    if dof <= 0:
        return None
    sigma2 = sum(r * r for r in resid) / dof
    var_gamma = inv[1][1] * sigma2
    if var_gamma <= 0:
        return None
    return beta[1] / math.sqrt(var_gamma)


def _invert(matrix: List[List[float]]) -> Optional[List[List[float]]]:
    n = len(matrix)
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            return None
        aug[col], aug[pivot] = aug[pivot], aug[col]
        pv = aug[col][col]
        aug[col] = [v / pv for v in aug[col]]
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            if factor:
                aug[r] = [a - factor * b for a, b in zip(aug[r], aug[col])]
    return [row[n:] for row in aug]


def hurst_exponent(values: Sequence[Number], max_lag: int = 20) -> Number:
    """Rescaled-range Hurst exponent (no external deps).

    H < 0.5 mean-reverting, H ~ 0.5 random walk, H > 0.5 trending.
    """
    series = [v for v in (to_float(x) for x in values) if v is not None]
    if len(series) < max_lag * 2:
        return None
    lags = [lag for lag in range(2, max_lag + 1) if len(series) // lag >= 2]
    if len(lags) < 3:
        return None
    log_lags: List[float] = []
    log_rs: List[float] = []
    for lag in lags:
        chunks = [series[i : i + lag] for i in range(0, len(series) - lag + 1, lag)]
        rs_values = []
        for chunk in chunks:
            if len(chunk) < 2:
                continue
            avg = sum(chunk) / len(chunk)
            dev = [c - avg for c in chunk]
            pos = neg = 0.0
            for d in dev:
                pos = max(pos, pos + d)
                neg = min(neg, neg + d)
            spread = pos - neg
            sd = math.sqrt(sum(d * d for d in dev) / len(dev))
            if sd > 0:
                rs_values.append(spread / sd)
        if rs_values:
            log_lags.append(math.log(lag))
            log_rs.append(math.log(sum(rs_values) / len(rs_values)))
    if len(log_lags) < 3:
        return None
    n = len(log_lags)
    mx = sum(log_lags) / n
    my = sum(log_rs) / n
    denom = sum((x - mx) ** 2 for x in log_lags)
    if denom == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(log_lags, log_rs)) / denom
