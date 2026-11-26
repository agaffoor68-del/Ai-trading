"""Registry of all 169 indicators: metadata + compute binding.

This module is the single source of truth used by the API, the Indicator
Library UI and the docs generator.  ``status`` is deliberately honest:

* ``implemented_tested``        – formula implemented and unit-tested
* ``implemented_awaiting_data`` – implemented, needs a provider feed (VIX,
  option chain, benchmark series, tick direction)
* ``unsupported_data``          – no configured provider can supply the input
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import levels as levels_mod
from . import momentum as momentum_mod
from . import options_analysis as options_mod
from . import statistics as statistics_mod
from . import structure as structure_mod
from . import trend as trend_mod
from . import volatility as volatility_mod
from . import volume as volume_mod

CATEGORIES: Dict[str, dict] = {
    "trend": {"label": "Trend", "order": 1},
    "momentum": {"label": "Momentum", "order": 2},
    "volatility": {"label": "Volatility", "order": 3},
    "volume": {"label": "Volume", "order": 4},
    "levels": {"label": "Support & Resistance", "order": 5},
    "structure": {"label": "Market Structure", "order": 6},
    "statistics": {"label": "Advanced & Statistical", "order": 7},
    "options": {"label": "Options & Derivatives", "order": 8},
}

TIMEFRAMES_ALL = ["1m", "3m", "5m", "10m", "15m", "30m", "1h", "2h", "4h", "1d", "1wk", "1mo"]
TIMEFRAMES_DAILY = ["1d", "1wk", "1mo"]

MARKET_PRICE = ["NSE", "BSE", "NIFTY", "BANKNIFTY", "FINNIFTY", "STOCK", "FUTURES", "GOLD", "SILVER", "FOREX", "CRYPTO"]
MARKET_DERIV = ["NIFTY", "BANKNIFTY", "FINNIFTY", "OPTIONS", "FUTURES"]
MARKET_CRYPTO = ["CRYPTO"]

DEFAULT_INTERP = {
    "trend": "Trend-following: price above the line is bullish, below is bearish. Confirm with price structure before acting.",
    "momentum": "Momentum: values above the midline show upside pressure, below show downside pressure. Divergences hint at exhaustion.",
    "volatility": "Volatility: expanding bands/ranges mean larger expected moves; contraction often precedes a breakout.",
    "volume": "Volume: confirms (or contradicts) price moves. Rising volume on a breakout is stronger than a quiet one.",
    "levels": "Levels: price often reacts at these lines. A break with volume is more meaningful than a touch.",
    "structure": "Structure: pivots and breaks map the trend. A break in the opposite direction is an early warning.",
    "statistics": "Statistics: describes the data-generating process (trending vs mean reverting) rather than giving a directional signal.",
    "options": "Derivatives: positioning and pricing data. Read together with price; never in isolation.",
}

DEFAULT_LIMITS = {
    "trend": "Lagging by construction; in choppy markets it whipsaws. Not a standalone entry trigger.",
    "momentum": "Can stay stretched for a long time in a strong trend; divergences may persist.",
    "volatility": "Does not predict direction, only the size of moves. Band-based signals need confirmation.",
    "volume": "Volume quality depends on the venue; indicative (non-exchange) feeds understate real activity.",
    "levels": "Levels are approximations; clustered zones are more reliable than single lines.",
    "structure": "Pivots confirm `right` bars later, so the most recent pivot is provisional by design.",
    "statistics": "Estimates are noisy on short samples; correlation is not causation and parameters are unstable.",
    "options": "Requires a live chain with IV and OI; stale or synthetic chains make these values misleading.",
}


def _p(name: str, default: Any, ptype: str = "int", pmin: Optional[float] = None,
       pmax: Optional[float] = None, label: Optional[str] = None, step: float = 1) -> dict:
    return {
        "name": name,
        "default": default,
        "type": ptype,
        "min": pmin,
        "max": pmax,
        "step": step,
        "label": label or name.replace("_", " ").title(),
    }


PERIOD = lambda default=14, pmin=1, pmax=500: _p("period", default, "int", pmin, pmax)  # noqa: E731


def _spec(
    ident: str,
    name: str,
    category: str,
    description: str,
    formula: str,
    params: List[dict],
    compute,
    required: str = "ohlcv",
    status: str = "implemented_tested",
    chart: str = "pane",
    repaint: bool = False,
    markets: Optional[List[str]] = None,
    timeframes: Optional[List[str]] = None,
    interpretation: Optional[str] = None,
    limitations: Optional[str] = None,
    note: Optional[str] = None,
) -> dict:
    return {
        "id": ident,
        "name": name,
        "category": category,
        "category_label": CATEGORIES[category]["label"],
        "description": description,
        "formula": formula,
        "params": params,
        "required_data": required,
        "status": status,
        "chart": chart,
        "repaint": repaint,
        "markets": markets or MARKET_PRICE,
        "timeframes": timeframes or TIMEFRAMES_ALL,
        "interpretation": interpretation or DEFAULT_INTERP[category],
        "limitations": limitations or DEFAULT_LIMITS[category],
        "note": note,
        "compute": compute,
    }


SPECS: List[dict] = []

# =====================================================================  A. TREND
SPECS += [
    _spec("sma", "SMA", "trend", "Arithmetic mean of the last N closes.", "SMA_t = (1/N) * Σ close_{t-i}, i=0..N-1", [PERIOD(20)], trend_mod.sma_, chart="overlay"),
    _spec("ema", "EMA", "trend", "Exponentially weighted mean; reacts faster than SMA.", "EMA_t = α·close_t + (1-α)·EMA_{t-1}, α = 2/(N+1)", [PERIOD(20)], trend_mod.ema_, chart="overlay"),
    _spec("wma", "WMA", "trend", "Linearly weighted mean (recent bars weigh more).", "WMA = Σ (i·close_i) / Σ i", [PERIOD(20)], trend_mod.wma_, chart="overlay"),
    _spec("vwma", "VWMA", "trend", "Moving average weighted by volume.", "VWMA = Σ(close·vol) / Σ vol", [PERIOD(20)], trend_mod.vwma, chart="overlay"),
    _spec("dema", "DEMA", "trend", "Double-smoothed EMA with reduced lag.", "DEMA = 2·EMA(N) - EMA(EMA(N))", [PERIOD(20)], trend_mod.dema_, chart="overlay"),
    _spec("tema", "TEMA", "trend", "Triple-smoothed EMA, even less lag.", "TEMA = 3·E1 - 3·E2 + E3", [PERIOD(20)], trend_mod.tema_, chart="overlay"),
    _spec("hma", "HMA", "trend", "Hull MA: weighted difference of two WMAs.", "HMA = WMA(2·WMA(n/2) - WMA(n), √n)", [PERIOD(20)], trend_mod.hma_, chart="overlay"),
    _spec("kama", "KAMA", "trend", "Kaufman adaptive MA; speeds up in trends, flattens in ranges.", "SC = (ER·(2/(f+1) - 2/(s+1)) + 2/(s+1))²; KAMA_t = KAMA_{t-1} + SC·(close-KAMA_{t-1})", [_p("period", 10, "int", 2, 200), _p("fast", 2, "int", 1, 50), _p("slow", 30, "int", 1, 200)], trend_mod.kama_, chart="overlay"),
    _spec("alma", "ALMA", "trend", "Arnaud Legoux MA with a Gaussian window.", "ALMA = Σ w_i·close_i / Σ w_i, w_i = exp(-(i-m)²/(2σ²)), m = offset·(N-1), σ = N/sigma", [PERIOD(21), _p("offset", 0.85, "float", 0.0, 1.0, step=0.01), _p("sigma", 6.0, "float", 1.0, 20.0, step=0.1)], trend_mod.alma_, chart="overlay"),
    _spec("zlema", "ZLEMA", "trend", "Zero-lag EMA on a de-lagged price.", "ZLEMA = EMA(close + (close - close_{lag}), N), lag = (N-1)/2", [PERIOD(20)], trend_mod.zlema_, chart="overlay"),
    _spec("t3", "T3", "trend", "Tillson T3: six EMAs combined with a volume factor.", "T3 = c1·E1 + c2·E2 + c3·E3 + c4·E4 (coefficients from v)", [PERIOD(5), _p("v_factor", 0.7, "float", 0.0, 1.0, step=0.01)], trend_mod.t3_, chart="overlay"),
    _spec("mcginley", "McGinley Dynamic", "trend", "Self-adjusting average that tracks price closely.", "MD_t = MD_{t-1} + (close - MD_{t-1}) / (N·(close/MD_{t-1})⁴)", [PERIOD(14)], trend_mod.mcginley_, chart="overlay"),
    _spec("supertrend", "Supertrend", "trend", "ATR band trend line with an up/down flip.", "basicUpper = (H+L)/2 + mult·ATR; basicLower = (H+L)/2 - mult·ATR", [PERIOD(10), _p("multiplier", 3.0, "float", 0.5, 20.0, step=0.1)], trend_mod.supertrend, chart="overlay"),
    _spec("parabolic_sar", "Parabolic SAR", "trend", "Accelerating stop-and-reverse level.", "SAR_t = SAR_{t-1} + AF·(EP - SAR_{t-1}); AF += step capped at max_step", [_p("step", 0.02, "float", 0.001, 0.5, step=0.001), _p("max_step", 0.2, "float", 0.01, 1.0, step=0.01)], trend_mod.parabolic_sar, chart="overlay"),
    _spec("ichimoku", "Ichimoku Cloud", "trend", "Five-line system: tenkan, kijun, two spans, chikou.", "Tenkan=(H9+L9)/2; Kijun=(H26+L26)/2; SpanA=(Tenkan+Kijun)/2; SpanB=(H52+L52)/2", [_p("tenkan", 9, "int", 1, 100), _p("kijun", 26, "int", 1, 200), _p("senkou_b", 52, "int", 1, 300)], trend_mod.ichimoku, chart="overlay"),
    _spec("adx", "ADX", "trend", "Trend strength (not direction) from smoothed directional movement.", "ADX = RMA(|+DI - -DI| / (+DI + -DI) · 100, N)", [PERIOD(14)], trend_mod.adx, chart="pane"),
    _spec("dmi", "DMI", "trend", "Directional movement lines (+DI, -DI) with ADX.", "+DI = 100·RMA(+DM,N)/ATR(N); -DI = 100·RMA(-DM,N)/ATR(N)", [PERIOD(14)], trend_mod.dmi, chart="pane"),
    _spec("aroon", "Aroon", "trend", "Time since the highest high / lowest low.", "AroonUp = 100·(N - barsSinceHigh)/N; AroonDown = 100·(N - barsSinceLow)/N", [PERIOD(25)], trend_mod.aroon, chart="pane"),
    _spec("aroon_oscillator", "Aroon Oscillator", "trend", "AroonUp minus AroonDown.", "AO = AroonUp - AroonDown", [PERIOD(25)], trend_mod.aroon_oscillator, chart="pane"),
    _spec("vortex", "Vortex", "trend", "Directional vortex lines from upward/downward motion.", "VI+ = Σ|High_t - Low_{t-1}| / Σ TR; VI- = Σ|Low_t - High_{t-1}| / Σ TR", [PERIOD(14)], trend_mod.vortex, chart="pane"),
    _spec("linear_regression", "Linear Regression", "trend", "Fitted value of the least-squares line.", "y = a + b·x fitted over N bars; value = a + b·(N-1)", [PERIOD(20)], trend_mod.linear_regression_, chart="overlay"),
    _spec("linear_regression_slope", "Linear Regression Slope", "trend", "Slope of the least-squares line per bar.", "b = Σ(x-x̄)(y-ȳ) / Σ(x-x̄)²", [PERIOD(20)], trend_mod.linear_regression_slope, chart="pane"),
    _spec("ma_ribbon", "Moving Average Ribbon", "trend", "Eight stacked SMAs from 8 to 1024 periods.", "SMA(base·2^i) for i = 0..count-1", [_p("base", 8, "int", 1, 50), _p("count", 8, "int", 3, 10)], trend_mod.ma_ribbon, chart="overlay"),
    _spec("guppy_gmma", "Guppy GMMA", "trend", "Three EMA groups (short, medium, long) showing crowd behaviour.", "EMA groups {3,5,8,10,12,15}, {21,24,27,30,35,40}, {50,60,70,80,90,105}", [], trend_mod.guppy_gmma, chart="overlay"),
    _spec("trend_magic", "Trend Magic", "trend", "CCI-scaled ATR trend line.", "TrendMagic = close + (CCI/100)·ATR", [PERIOD(14)], trend_mod.trend_magic, chart="overlay"),
]

# ===================================================================  B. MOMENTUM
SPECS += [
    _spec("rsi", "RSI", "momentum", "Relative strength index, 0-100.", "RSI = 100 - 100/(1+RS); RS = avgGain/avgLoss (Wilder)", [PERIOD(14)], momentum_mod.rsi),
    _spec("macd", "MACD", "momentum", "Difference of two EMAs with a signal line.", "MACD = EMA(fast) - EMA(slow); signal = EMA(MACD, signal)", [_p("fast", 12, "int", 1, 100), _p("slow", 26, "int", 1, 200), _p("signal", 9, "int", 1, 50)], momentum_mod.macd),
    _spec("stochastic", "Stochastic Oscillator", "momentum", "Position of the close inside the recent range.", "%K = 100·(close - LL)/(HH - LL); %D = SMA(%K, d)", [PERIOD(14), _p("smooth_k", 3, "int", 1, 20), _p("period_d", 3, "int", 1, 20)], momentum_mod.stochastic),
    _spec("stochrsi", "Stochastic RSI", "momentum", "Stochastic applied to RSI.", "StochRSI = 100·(RSI - min(RSI))/(max(RSI) - min(RSI))", [_p("rsi_period", 14, "int", 1, 100), PERIOD(14), _p("smooth_k", 3, "int", 1, 20), _p("period_d", 3, "int", 1, 20)], momentum_mod.stochrsi),
    _spec("williams_r", "Williams %R", "momentum", "Close position in range, -100 to 0.", "%R = -100·(HH - close)/(HH - LL)", [PERIOD(14)], momentum_mod.williams_r),
    _spec("cci", "CCI", "momentum", "Commodity channel index: deviation from the mean.", "CCI = (TP - SMA(TP)) / (0.015 · meanDeviation)", [PERIOD(20)], momentum_mod.cci),
    _spec("roc", "ROC", "momentum", "Percentage change over N bars.", "ROC = 100·(close - close_{t-N}) / close_{t-N}", [PERIOD(9)], momentum_mod.roc),
    _spec("momentum", "Momentum", "momentum", "Absolute price change over N bars.", "Momentum = close_t - close_{t-N}", [PERIOD(10)], momentum_mod.momentum),
    _spec("cmo", "CMO", "momentum", "Chande momentum oscillator, -100 to 100.", "CMO = 100·(sumUp - sumDown)/(sumUp + sumDown)", [PERIOD(14)], momentum_mod.cmo),
    _spec("trix", "TRIX", "momentum", "Rate of change of a triple-smoothed EMA.", "TRIX = 100·(E3_t - E3_{t-1}) / E3_{t-1}", [PERIOD(15), _p("signal", 9, "int", 1, 50)], momentum_mod.trix),
    _spec("ultimate_oscillator", "Ultimate Oscillator", "momentum", "Weighted momentum across three horizons.", "UO = 100·(7·BP1 + 14·BP2 + 28·BP3)/(7·TR1 + 14·TR2 + 28·TR3)", [_p("period_1", 7, "int", 1, 100), _p("period_2", 14, "int", 1, 200), _p("period_3", 28, "int", 1, 400)], momentum_mod.ultimate_oscillator),
    _spec("awesome_oscillator", "Awesome Oscillator", "momentum", "Median-price SMA difference (5 vs 34).", "AO = SMA(median,5) - SMA(median,34)", [_p("short", 5, "int", 1, 100), _p("long", 34, "int", 1, 300)], momentum_mod.awesome_oscillator),
    _spec("accelerator_oscillator", "Accelerator Oscillator", "momentum", "Acceleration of the awesome oscillator.", "AC = AO - SMA(AO, 5)", [_p("short", 5, "int", 1, 100), _p("long", 34, "int", 1, 300)], momentum_mod.accelerator_oscillator),
    _spec("ppo", "PPO", "momentum", "Percentage price oscillator.", "PPO = 100·(EMA(fast) - EMA(slow))/EMA(slow)", [_p("fast", 12, "int", 1, 100), _p("slow", 26, "int", 1, 200), _p("signal", 9, "int", 1, 50)], momentum_mod.ppo),
    _spec("apo", "APO", "momentum", "Absolute price oscillator.", "APO = EMA(fast) - EMA(slow)", [_p("fast", 12, "int", 1, 100), _p("slow", 26, "int", 1, 200)], momentum_mod.apo),
    _spec("fisher_transform", "Fisher Transform", "momentum", "Gaussianised price position; sharp turning points.", "v = 2·((price-LL)/(HH-LL) - 0.5); F = 0.5·ln((1+v)/(1-v)) + 0.5·F_{t-1}", [PERIOD(9)], momentum_mod.fisher_transform),
    _spec("connors_rsi", "Connors RSI", "momentum", "Composite of RSI, streak and percent rank.", "CRSI = (RSI(3) + StochRSI(3) + PR(ROC(1),100)) / 3", [_p("rsi_period", 3, "int", 1, 50), _p("stoch_period", 3, "int", 1, 50), _p("roc_period", 100, "int", 1, 500)], momentum_mod.connors_rsi),
    _spec("relative_vigor_index", "Relative Vigor Index", "momentum", "Close-open body versus the bar range.", "RVI = Σ w·(C-O) / Σ w·(H-L), w = [1,2,2,1]", [PERIOD(10)], momentum_mod.relative_vigor_index),
    _spec("dpo", "DPO", "momentum", "Price displaced against a moving average to expose cycles.", "DPO = close_{t-(N/2+1)} - SMA(close, N)", [PERIOD(20)], momentum_mod.dpo),
    _spec("elder_ray", "Elder Ray", "momentum", "Bull and bear power relative to an EMA.", "Bull = High - EMA(N); Bear = Low - EMA(N)", [PERIOD(13)], momentum_mod.elder_ray),
    _spec("kst", "KST", "momentum", "Know Sure Thing: weighted smoothed ROCs.", "KST = RCMA1 + 2·RCMA2 + 3·RCMA3 + 4·RCMA4", [_p("r1", 10, "int", 1, 100), _p("r2", 15, "int", 1, 200), _p("r3", 20, "int", 1, 300), _p("r4", 30, "int", 1, 400), _p("sma1", 10, "int", 1, 50), _p("sma2", 10, "int", 1, 50), _p("sma3", 10, "int", 1, 50), _p("sma4", 15, "int", 1, 50), _p("signal", 9, "int", 1, 50)], momentum_mod.kst),
    _spec("chande_forecast", "Chande Forecast Oscillator", "momentum", "Deviation of price from the regression line.", "CFO = 100·(close - trendline)/close", [PERIOD(14)], momentum_mod.chande_forecast),
    _spec("qstick", "Qstick", "momentum", "Moving average of the candle body.", "Qstick = SMA(close - open, N)", [PERIOD(14)], momentum_mod.qstick),
    _spec("relative_momentum_index", "Relative Momentum Index", "momentum", "RSI applied to momentum instead of price change.", "RMI = 100·avgGain/(avgGain + avgLoss) over momentum", [PERIOD(14), _p("momentum_period", 4, "int", 1, 50)], momentum_mod.relative_momentum_index),
    _spec("smi", "SMI", "momentum", "Double-smoothed stochastic momentum index.", "SMI = EMA(EMA((close - (HH+LL)/2)/((HH-LL)/2)·100, k), k)", [PERIOD(14), _p("smooth_k", 3, "int", 1, 20), _p("smooth_d", 3, "int", 1, 20)], momentum_mod.smi),
]

# =================================================================  C. VOLATILITY
SPECS += [
    _spec("bollinger", "Bollinger Bands", "volatility", "SMA with ±k standard-deviation bands.", "mid = SMA(N); upper/lower = mid ± k·σ(N)", [PERIOD(20), _p("multiplier", 2.0, "float", 0.1, 10.0, step=0.1)], volatility_mod.bollinger, chart="overlay"),
    _spec("atr", "ATR", "volatility", "Average true range (Wilder).", "TR = max(H-L, |H-Cprev|, |L-Cprev|); ATR = RMA(TR, N)", [PERIOD(14)], volatility_mod.atr_),
    _spec("keltner", "Keltner Channels", "volatility", "EMA with ATR-scaled bands.", "mid = EMA(N); bands = mid ± mult·ATR(N)", [PERIOD(20), _p("multiplier", 2.0, "float", 0.1, 10.0, step=0.1)], volatility_mod.keltner, chart="overlay"),
    _spec("donchian", "Donchian Channels", "volatility", "Highest high / lowest low channel.", "upper = HH(N); lower = LL(N); mid = (upper+lower)/2", [PERIOD(20)], volatility_mod.donchian, chart="overlay"),
    _spec("standard_deviation", "Standard Deviation", "volatility", "Rolling dispersion of price.", "σ = sqrt(Σ(x-x̄)²/N)", [PERIOD(20)], volatility_mod.standard_deviation),
    _spec("historical_volatility", "Historical Volatility", "volatility", "Annualised standard deviation of returns.", "HV = σ(returns, N)·sqrt(252)", [PERIOD(20), _p("annualization", 252, "int", 1, 365)], volatility_mod.historical_volatility),
    _spec("chaikin_volatility", "Chaikin Volatility", "volatility", "Change in EMA of the high-low spread.", "CV = 100·(EMA(diff) - EMA(diff)_{t-1}) / EMA(diff)_{t-1}", [PERIOD(10), _p("smooth", 10, "int", 1, 100)], volatility_mod.chaikin_volatility),
    _spec("bollinger_bandwidth", "Bollinger Band Width", "volatility", "Band width as a percentage of the mean.", "BW = 100·(2·k·σ)/mid", [PERIOD(20), _p("multiplier", 2.0, "float", 0.1, 10.0, step=0.1)], volatility_mod.bollinger_bandwidth),
    _spec("atr_percent", "ATR Percent", "volatility", "ATR as a percentage of price.", "ATR% = 100·ATR/close", [PERIOD(14)], volatility_mod.atr_percent),
    _spec("ulcer_index", "Ulcer Index", "volatility", "Depth and duration of drawdowns.", "UI = sqrt(Σ(100·(peak-close)/peak)²/N)", [PERIOD(14)], volatility_mod.ulcer_index),
    _spec("choppiness", "Choppiness Index", "volatility", "0-100: high values mean a ranging market.", "CHOP = 100·log10(ΣTR/(HH-LL))/log10(N)", [PERIOD(14)], volatility_mod.choppiness),
    _spec("mass_index", "Mass Index", "volatility", "EMA ratio of the high-low range, spotting range shifts.", "MI = SMA(EMA(H/L,N)/EMA(EMA(H/L,N),N), N)", [PERIOD(9), _p("smooth", 9, "int", 1, 50)], volatility_mod.mass_index),
    _spec("vix", "VIX", "volatility", "CBOE volatility index level (needs a VIX feed).", "Provider series (not derivable from NSE OHLCV)", [], volatility_mod.vix, required="index_feed", status="implemented_awaiting_data", markets=MARKET_PRICE, note="No VIX feed is configured; endpoint returns data_unavailable."),
    _spec("india_vix", "India VIX", "volatility", "NSE India VIX level (needs the NSE feed).", "Provider series (NSE India VIX)", [], volatility_mod.india_vix, required="index_feed", status="implemented_awaiting_data", markets=["NSE", "NIFTY", "BANKNIFTY"], note="No India VIX feed is configured yet."),
    _spec("volatility_stop", "Volatility Stop", "volatility", "ATR trailing stop that flips with price.", "longStop = max(prev, close - mult·ATR); shortStop = min(prev, close + mult·ATR)", [PERIOD(20), _p("multiplier", 2.0, "float", 0.1, 10.0, step=0.1)], volatility_mod.volatility_stop, chart="overlay"),
    _spec("acceleration_bands", "Acceleration Bands", "volatility", "Bands scaled by the high-low range relative to price.", "upper = mid + mult·(H-L)/C·(H-mid)", [PERIOD(20), _p("multiplier", 4.0, "float", 0.1, 20.0, step=0.1)], volatility_mod.acceleration_bands, chart="overlay"),
    _spec("fractal_chaos_bands", "Fractal Chaos Bands", "volatility", "High/low envelope of the recent window.", "upper = HH(N); lower = LL(N)", [PERIOD(6)], volatility_mod.fractal_chaos_bands, chart="overlay"),
    _spec("garch_volatility", "GARCH Volatility", "volatility", "GARCH(1,1) conditional volatility (grid-ML).", "σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}", [PERIOD(100)], volatility_mod.garch_volatility, note="Parameters estimated by grid search; annualised."),
    _spec("normalized_atr", "Normalized ATR", "volatility", "ATR divided by price (0-1 scale).", "NATR = ATR/close", [PERIOD(14)], volatility_mod.normalized_atr),
    _spec("starc_bands", "STARC Bands", "volatility", "SMA with ATR-scaled bands (STARC).", "mid = SMA(N); bands = mid ± mult·ATR(N)", [PERIOD(15), _p("multiplier", 2.0, "float", 0.1, 10.0, step=0.1)], volatility_mod.starc_bands, chart="overlay"),
]

# =====================================================================  D. VOLUME
SPECS += [
    _spec("volume", "Volume", "volume", "Raw traded volume per bar.", "volume_t", [], volume_mod.volume, chart="overlay"),
    _spec("vwap", "VWAP", "volume", "Session volume-weighted average price.", "VWAP = Σ(TP·vol)/Σvol, reset each session", [], volume_mod.vwap, chart="overlay", note="Session anchor uses the UTC day of ctx.ts."),
    _spec("anchored_vwap", "Anchored VWAP", "volume", "VWAP anchored at a chosen bar.", "VWAP = Σ(TP·vol)/Σvol from the anchor bar", [_p("start_index", 0, "int", 0, 100000, "Anchor bar index")], volume_mod.anchored_vwap, chart="overlay"),
    _spec("obv", "OBV", "volume", "Cumulative volume signed by price direction.", "OBV += vol if close>close_prev; -= vol if close<close_prev", [], volume_mod.obv),
    _spec("mfi", "MFI", "volume", "Money flow index: volume-weighted RSI.", "MFI = 100 - 100/(1 + ΣPosFlow/ΣNegFlow)", [PERIOD(14)], volume_mod.mfi),
    _spec("cmf", "CMF", "volume", "Chaikin money flow over N bars.", "CMF = Σ(MFM·vol)/Σvol; MFM = ((C-L)-(H-C))/(H-L)", [PERIOD(20)], volume_mod.cmf),
    _spec("ad_line", "Accumulation/Distribution Line", "volume", "Cumulative signed volume flow.", "AD += ((C-L)-(H-C))/(H-L) · vol", [], volume_mod.ad_line),
    _spec("volume_profile", "Volume Profile", "volume", "Volume traded at each price in the lookback.", "bucket(price) = Σ volume; POC = modal bucket", [_p("bins", 24, "int", 5, 100), _p("lookback", 100, "int", 10, 2000)], volume_mod.volume_profile, chart="overlay", note="Returns the profile in levels.profile plus the POC."),
    _spec("fixed_range_volume_profile", "Fixed Range Volume Profile", "volume", "Volume profile over a fixed % range of the data.", "bucket(price) over [start_pct, end_pct]", [_p("bins", 24, "int", 5, 100), _p("start_pct", 0.0, "float", 0.0, 100.0, step=0.1), _p("end_pct", 100.0, "float", 0.0, 100.0, step=0.1)], volume_mod.fixed_range_volume_profile, chart="overlay"),
    _spec("visible_range_volume_profile", "Visible Range Volume Profile", "volume", "Volume profile over all loaded bars.", "bucket(price) over the visible range", [_p("bins", 24, "int", 5, 100)], volume_mod.visible_range_volume_profile, chart="overlay"),
    _spec("pvt", "PVT", "volume", "Price volume trend: cumulative return-weighted volume.", "PVT += ((close-close_prev)/close_prev)·vol", [], volume_mod.pvt),
    _spec("volume_oscillator", "Volume Oscillator", "volume", "Fast minus slow EMA of volume.", "VO = EMA(vol, fast) - EMA(vol, slow)", [_p("fast", 5, "int", 1, 100), _p("slow", 20, "int", 1, 300)], volume_mod.volume_oscillator),
    _spec("force_index", "Force Index", "volume", "Price change multiplied by volume, smoothed.", "FI = EMA((close-close_prev)·vol, N)", [PERIOD(13)], volume_mod.force_index),
    _spec("ease_of_movement", "Ease of Movement", "volume", "Range movement per unit of volume.", "EMV = ((H+L)/2 - (Hprev+Lprev)/2) / (vol/(H-L))", [PERIOD(14)], volume_mod.ease_of_movement),
    _spec("negative_volume_index", "Negative Volume Index", "volume", "Cumulative return on down-volume days.", "NVI_t = NVI_{t-1}·close/close_prev when vol<vol_prev", [], volume_mod.negative_volume_index),
    _spec("positive_volume_index", "Positive Volume Index", "volume", "Cumulative return on up-volume days.", "PVI_t = PVI_{t-1}·close/close_prev when vol>vol_prev", [], volume_mod.positive_volume_index),
    _spec("chaikin_oscillator", "Chaikin Oscillator", "volume", "EMA spread of the A/D line.", "CO = EMA(AD, fast) - EMA(AD, slow)", [_p("fast", 3, "int", 1, 100), _p("slow", 10, "int", 1, 300)], volume_mod.chaikin_oscillator),
    _spec("klinger_volume_oscillator", "Klinger Volume Oscillator", "volume", "Volume force with trend and confirmation.", "KVO = EMA(VF,34) - EMA(VF,55); signal = EMA(KVO,13)", [_p("fast", 34, "int", 1, 200), _p("slow", 55, "int", 1, 300), _p("signal", 13, "int", 1, 100)], volume_mod.klinger_volume_oscillator),
    _spec("volume_roc", "Volume Rate of Change", "volume", "Percentage change in volume.", "VROC = 100·(vol - vol_{t-N})/vol_{t-N}", [PERIOD(9)], volume_mod.volume_roc),
    _spec("volume_delta", "Volume Delta", "volume", "Difference between buying and selling volume.", "ΔV = buyVolume - sellVolume", [], volume_mod.volume_delta, required="tick_direction", status="implemented_awaiting_data", note="The Fyers quote feed does not classify aggressor side."),
    _spec("cumulative_volume_delta", "Cumulative Volume Delta", "volume", "Running total of volume delta.", "CVD = Σ ΔV", [], volume_mod.cumulative_volume_delta, required="tick_direction", status="implemented_awaiting_data"),
    _spec("buy_sell_volume_ratio", "Buy/Sell Volume Ratio", "volume", "Ratio of classified buy to sell volume.", "ratio = ΣbuyVolume / ΣsellVolume", [], volume_mod.buy_sell_volume_ratio, required="tick_direction", status="implemented_awaiting_data"),
    _spec("relative_volume", "Relative Volume (RVOL)", "volume", "Current volume versus its average.", "RVOL = vol / SMA(vol, N)", [PERIOD(20)], volume_mod.relative_volume),
    _spec("money_flow", "Money Flow", "volume", "Cumulative typical price times volume.", "MF = Σ(TP·vol)", [], volume_mod.money_flow),
    _spec("volume_weighted_macd", "Volume Weighted MACD", "volume", "MACD computed on VWAP instead of close.", "MACD(VWAP) with EMA(fast/slow) and signal", [_p("fast", 12, "int", 1, 100), _p("slow", 26, "int", 1, 200), _p("signal", 9, "int", 1, 50)], volume_mod.volume_weighted_macd),
]

# =====================================================  E. SUPPORT & RESISTANCE
SPECS += [
    _spec("fibonacci_retracement", "Fibonacci Retracement", "levels", "Retracement grid from the lookback high/low.", "level = high - (high-low)·ratio for ratio in {0, .236, .382, .5, .618, .786, 1}", [_p("lookback", 50, "int", 5, 1000)], levels_mod.fibonacci_retracement, chart="overlay"),
    _spec("fibonacci_extension", "Fibonacci Extension", "levels", "Extension grid beyond the range.", "level = low + (high-low)·ratio for ratio in {0, .618, 1, 1.618, 2.618, 4.236}", [_p("lookback", 50, "int", 5, 1000)], levels_mod.fibonacci_extension, chart="overlay"),
    _spec("fibonacci_projection", "Fibonacci Projection", "levels", "Three-point A-B-C projection levels.", "level = C + (C-B)·ratio", [_p("lookback", 100, "int", 5, 2000)], levels_mod.fibonacci_projection, chart="overlay"),
    _spec("pivot_points", "Pivot Points", "levels", "Classic floor-trader pivots from the previous period.", "P=(H+L+C)/3; R1=2P-L; S1=2P-H; R2=P+(H-L); S2=P-(H-L)", [], levels_mod.pivot_points, chart="overlay"),
    _spec("fibonacci_pivot_points", "Fibonacci Pivot Points", "levels", "Pivots with Fibonacci-scaled levels.", "P=(H+L+C)/3; levels = P ± (H-L)·ratio", [], levels_mod.fibonacci_pivot_points, chart="overlay"),
    _spec("camarilla_pivots", "Camarilla Pivot Points", "levels", "Tight mean-reversion levels from the range.", "H_i = C + range·m_i/12; L_i = C - range·m_i/12, m ∈ {1.1,1.2,1.3,1.4}", [], levels_mod.camarilla_pivots, chart="overlay"),
    _spec("woodie_pivots", "Woodie Pivot Points", "levels", "Pivots weighting the previous close twice.", "P=(H+L+2C)/4; R1=2P-L; S1=2P-H", [], levels_mod.woodie_pivots, chart="overlay"),
    _spec("demark_pivots", "DeMark Pivot Points", "levels", "Conditional pivot using the close vs prior range.", "X = H+2L+C (C<H) or 2H+L+C (C>L) or H+L+2C", [], levels_mod.demark_pivots, chart="overlay"),
    _spec("support_resistance_zones", "Support & Resistance Zones", "levels", "Clusters of swing pivots as price zones.", "cluster pivots within tolerance_pct; rank by touches", [_p("lookback", 300, "int", 20, 5000), _p("tolerance_pct", 0.5, "float", 0.05, 5.0, step=0.05)], levels_mod.support_resistance_zones, chart="overlay"),
    _spec("auto_support_resistance", "Auto Support/Resistance", "levels", "Most frequently touched N-bar extremes.", "count touches of HH(N)/LL(N) in the lookback", [PERIOD(20), _p("lookback", 300, "int", 20, 5000)], levels_mod.auto_support_resistance, chart="overlay"),
    _spec("prev_day_high_low", "Previous Day High/Low", "levels", "Prior session high and low.", "max/min of the previous day group", [], levels_mod.prev_day_high_low, chart="overlay"),
    _spec("prev_week_high_low", "Previous Week High/Low", "levels", "Prior week high and low.", "max/min of the previous week group", [], levels_mod.prev_week_high_low, chart="overlay"),
    _spec("prev_month_high_low", "Previous Month High/Low", "levels", "Prior month high and low.", "max/min of the previous month group", [], levels_mod.prev_month_high_low, chart="overlay"),
    _spec("central_pivot_range", "CPR", "levels", "Central pivot range derived from the pivot.", "P=(H+L+C)/3; BC=(H+L)/2; TC=2P-BC", [], levels_mod.central_pivot_range, chart="overlay"),
    _spec("floor_trader_pivots", "Floor Trader Pivots", "levels", "Classic pit pivots with three supports/resistances.", "P=(H+L+C)/3; R_i/S_i from the range", [], levels_mod.floor_trader_pivots, chart="overlay"),
]

# ======================================================  F. MARKET STRUCTURE
SPECS += [
    _spec("zig_zag", "Zig Zag", "structure", "Filtered swing line ignoring small moves.", "reversal when price moves >= threshold% from the last pivot", [_p("threshold_pct", 5.0, "float", 0.1, 50.0, step=0.1)], structure_mod.zig_zag, chart="overlay", repaint=True, limitations="The last leg repaints until the next reversal threshold is hit."),
    _spec("fractals", "Fractals", "structure", "Williams fractals: 5-bar confirmed pivots.", "pivot high/low over a (2·window+1) bar window", [_p("window", 2, "int", 1, 10)], structure_mod.fractals, chart="overlay"),
    _spec("swing_high_low", "Swing High/Low", "structure", "Confirmed swing points with left/right symmetry.", "pivot where high is max of [i-left, i+right]", [_p("left", 3, "int", 1, 20), _p("right", 3, "int", 1, 20)], structure_mod.swing_high_low, chart="overlay"),
    _spec("market_structure_break", "Market Structure Break (MSB)", "structure", "Break of the previous swing in the trend direction.", "close beyond the last confirmed swing high/low", [_p("left", 3, "int", 1, 20), _p("right", 3, "int", 1, 20)], structure_mod.market_structure_break, chart="overlay"),
    _spec("break_of_structure", "Break of Structure (BOS)", "structure", "Continuation break after an existing trend.", "close > last swing high (bullish) or < last swing low", [_p("left", 3, "int", 1, 20), _p("right", 3, "int", 1, 20)], structure_mod.break_of_structure, chart="overlay"),
    _spec("change_of_character", "Change of Character (CHoCH)", "structure", "Trend reversal break against the prevailing direction.", "opposite-direction break of the last swing", [_p("left", 3, "int", 1, 20), _p("right", 3, "int", 1, 20)], structure_mod.change_of_character, chart="overlay"),
    _spec("smart_money_concepts", "Smart Money Concepts", "structure", "Composite SMC: structure, FVG and order blocks.", "union of BOS/CHoCH, fair value gaps and order blocks", [_p("left", 3, "int", 1, 20), _p("right", 3, "int", 1, 20), _p("window", 3, "int", 1, 20), _p("displacement_atr", 1.0, "float", 0.1, 10.0, step=0.1)], structure_mod.smart_money_concepts, chart="overlay"),
    _spec("order_blocks", "Order Blocks", "structure", "Last opposite candle before a displacement move.", "block = opposite-colour candle before body >= k·ATR", [_p("window", 3, "int", 1, 20), _p("displacement_atr", 1.0, "float", 0.1, 10.0, step=0.1)], structure_mod.order_blocks, chart="overlay"),
    _spec("fair_value_gaps", "Fair Value Gaps (FVG)", "structure", "Three-candle price imbalance.", "bullish: low_t > high_{t-2}; bearish: high_t < low_{t-2}", [], structure_mod.fair_value_gaps, chart="overlay"),
    _spec("liquidity_zones", "Liquidity Zones", "structure", "Clusters of equal highs/lows where stops sit.", "cluster pivots within tolerance_pct", [_p("left", 3, "int", 1, 20), _p("right", 3, "int", 1, 20), _p("tolerance_pct", 0.2, "float", 0.01, 5.0, step=0.01)], structure_mod.liquidity_zones, chart="overlay"),
    _spec("equal_highs_lows", "Equal Highs/Lows", "structure", "Matching swing highs or lows (stop clusters).", "two pivots within tolerance_pct", [_p("tolerance_pct", 0.1, "float", 0.01, 2.0, step=0.01), _p("left", 3, "int", 1, 20), _p("right", 3, "int", 1, 20)], structure_mod.equal_highs_lows, chart="overlay"),
    _spec("supply_demand_zones", "Supply & Demand Zones", "structure", "Impulse candles that created imbalance.", "body >= 1.5·ATR marks a supply/demand zone", [], structure_mod.supply_demand_zones, chart="overlay"),
    _spec("accumulation_distribution_zones", "Accumulation/Distribution Zones", "structure", "High-volume consolidation (base) zones.", "small body with high volume marks a base", [], structure_mod.accumulation_distribution_zones, chart="overlay"),
    _spec("donchian_breakout", "Donchian Breakout", "structure", "Close outside the prior N-bar range.", "close > HH(N)_{t-1} (+1) or < LL(N)_{t-1} (-1)", [PERIOD(20)], structure_mod.donchian_breakout, chart="overlay"),
    _spec("darvas_box", "Darvas Box", "structure", "New-high boxes with contained prior bars.", "box top extends when the prior N bars stay below", [PERIOD(5)], structure_mod.darvas_box, chart="overlay"),
    _spec("heikin_ashi", "Heikin Ashi", "structure", "Smoothed candles that filter market noise.", "HA_close=(O+H+L+C)/4; HA_open=(prevHA_open+prevHA_close)/2", [], structure_mod.heikin_ashi, chart="overlay"),
    _spec("renko", "Renko", "structure", "Price bricks of a fixed size, noise filtered.", "brick when |close-last| >= brick_size (ATR if unset)", [_p("brick_size", 0.0, "float", 0.0, 1000000.0, step=0.1)], structure_mod.renko, chart="overlay", note="brick_size 0 = auto (average ATR)."),
    _spec("kagi", "Kagi", "structure", "Line chart that changes direction on a reversal amount.", "reversal when price reverses by the reversal amount", [_p("reversal", 0.0, "float", 0.0, 1000000.0, step=0.1)], structure_mod.kagi, chart="overlay", note="reversal 0 = auto (1% of mean price)."),
    _spec("point_and_figure", "Point & Figure", "structure", "X/O columns with box sizing and reversal.", "X when +box, O when -box, reversal at `reversal` boxes", [_p("box_size", 0.0, "float", 0.0, 1000000.0, step=0.1), _p("reversal", 3, "int", 1, 10)], structure_mod.point_and_figure, chart="overlay"),
    _spec("inside_bar", "Inside Bar Detector", "structure", "Bar contained inside the previous bar.", "high_t < high_{t-1} and low_t > low_{t-1}", [], structure_mod.inside_bar, chart="overlay"),
]

# ==============================================  G. ADVANCED & STATISTICAL
SPECS += [
    _spec("beta", "Beta", "statistics", "Sensitivity to a benchmark.", "β = cov(asset, bench)/var(bench) over returns", [PERIOD(60)], statistics_mod.beta, required="benchmark", status="implemented_awaiting_data", note="Pass extras.benchmark (aligned closes) to enable."),
    _spec("correlation_coefficient", "Correlation Coefficient", "statistics", "Pearson correlation with a benchmark.", "ρ = cov(a,b)/(σ_a·σ_b)", [PERIOD(30)], statistics_mod.correlation_coefficient, required="benchmark", status="implemented_awaiting_data"),
    _spec("z_score", "Z-Score", "statistics", "Distance from the mean in standard deviations.", "z = (x - SMA(N))/σ(N)", [PERIOD(20)], statistics_mod.z_score),
    _spec("mean_reversion", "Mean Reversion", "statistics", "Negative z-score with a stretch signal.", "signal = +1 when z<-1, -1 when z>+1", [PERIOD(20)], statistics_mod.mean_reversion),
    _spec("linear_regression_channel", "Linear Regression Channel", "statistics", "Regression line with ±kσ residual channel.", "fitted ± mult·σ(residuals)", [PERIOD(50), _p("multiplier", 2.0, "float", 0.1, 10.0, step=0.1)], statistics_mod.linear_regression_channel, chart="overlay"),
    _spec("standard_error_bands", "Standard Error Bands", "statistics", "Bands from the standard error of the regression.", "se = s·sqrt(1/N + (x-x̄)²/Sxx); bands = fitted ± mult·se", [PERIOD(20), _p("multiplier", 2.0, "float", 0.1, 10.0, step=0.1)], statistics_mod.standard_error_bands, chart="overlay"),
    _spec("kalman_filter", "Kalman Filter", "statistics", "Adaptive local-level estimate of price.", "level += K·(price-level); K = P/(P+R)", [_p("process_noise", 0.01, "float", 0.0001, 10.0, step=0.0001), _p("measurement_noise", 0.1, "float", 0.0001, 10.0, step=0.0001)], statistics_mod.kalman_filter, chart="overlay"),
    _spec("hurst", "Hurst Exponent", "statistics", "Rescaled-range exponent: trending vs mean reverting.", "H = slope of log(R/S) vs log(lag)", [_p("max_lag", 20, "int", 2, 100)], statistics_mod.hurst),
    _spec("entropy", "Entropy Indicator", "statistics", "Shannon entropy of returns (randomness).", "H = -Σ p_i·ln(p_i)/ln(bins)", [PERIOD(50), _p("bins", 16, "int", 4, 100)], statistics_mod.entropy),
    _spec("fractal_dimension_index", "Fractal Dimension Index", "statistics", "Katz fractal dimension of the price path.", "D = log10(N)/(log10(N)+log10(d/meanStep))", [PERIOD(30)], statistics_mod.fractal_dimension_index),
    _spec("r_squared_indicator", "R-Squared", "statistics", "Goodness of fit of the regression line.", "R² = 1 - SS_res/SS_tot", [PERIOD(20)], statistics_mod.r_squared_indicator),
    _spec("variance_ratio", "Variance Ratio", "statistics", "Lo-MacKinlay variance ratio.", "VR(q) = Var(q-period change)/(q·Var(1-period change))", [_p("q", 5, "int", 2, 100)], statistics_mod.variance_ratio),
    _spec("pair_trading_spread", "Pair Trading Spread", "statistics", "Log spread with a rolling hedge ratio.", "spread = log(A) - β·log(B), β from the rolling window", [PERIOD(60)], statistics_mod.pair_trading_spread, required="benchmark", status="implemented_awaiting_data"),
    _spec("cointegration", "Cointegration", "statistics", "ADF test on the pair spread.", "ADF t-statistic of the spread; cointegrated if < -3.43", [PERIOD(120)], statistics_mod.cointegration, required="benchmark", status="implemented_awaiting_data"),
    _spec("adaptive_trend_finder", "Adaptive Trend Finder", "statistics", "Switches between fast and slow MA on efficiency.", "use fast MA when efficiency ratio > 0.5", [_p("fast", 10, "int", 1, 100), _p("slow", 30, "int", 1, 300)], statistics_mod.adaptive_trend_finder, chart="overlay"),
    _spec("cycle_indicator", "Cycle Indicator", "statistics", "Cycle-length moving average projection.", "average over the dominant cycle length, de-trended", [PERIOD(20)], statistics_mod.cycle_indicator),
    _spec("ehlers_roofing_filter", "Ehlers Roofing Filter", "statistics", "High-pass plus super smoother to remove trend noise.", "HP = price - 2-pole HP(48); then super smoother(10)", [_p("hp_period", 48, "int", 5, 200), _p("smooth_period", 10, "int", 2, 100)], statistics_mod.ehlers_roofing_filter),
    _spec("ehlers_super_smoother", "Ehlers Super Smoother", "statistics", "Two-pole Butterworth smoother.", "out = c1·(in+in_prev)/2 + c2·out_prev + c3·out_prev2", [PERIOD(10)], statistics_mod.ehlers_super_smoother, chart="overlay"),
    _spec("hilbert_transform", "Hilbert Transform", "statistics", "In-phase/quadrature decomposition (Ehlers).", "detrender = 0.0962·p + 0.5769·p2 - 0.5769·p4 - 0.0962·p6", [], statistics_mod.hilbert_transform),
    _spec("dominant_cycle_period", "Dominant Cycle Period", "statistics", "Cycle length in bars from the Hilbert transform.", "period = 360/phase, smoothed", [], statistics_mod.dominant_cycle_period),
]

# ==================================================  H. OPTIONS & DERIVATIVES
_OPT_PARAMS = [
    _p("time_to_expiry_years", 0.082, "float", 0.0001, 5.0, "Time to expiry (years)", step=0.0001),
    _p("risk_free", 0.065, "float", 0.0, 0.5, "Risk-free rate", step=0.001),
]
SPECS += [
    _spec("put_call_ratio", "Put Call Ratio (PCR)", "options", "Put open interest (or volume) divided by call OI.", "PCR = Σ put OI / Σ call OI", [_p("field", "oi", "str", None, None, "OI or volume")], options_mod.put_call_ratio, required="option_chain", status="implemented_awaiting_data", markets=MARKET_DERIV, timeframes=TIMEFRAMES_DAILY, note=">1 bearish positioning, <0.7 bullish (index context dependent)."),
    _spec("open_interest", "Open Interest (OI)", "options", "Total open interest across the chain.", "OI = Σ(call OI + put OI)", [], options_mod.open_interest, required="option_chain", status="implemented_awaiting_data", markets=MARKET_DERIV, timeframes=TIMEFRAMES_DAILY),
    _spec("change_in_open_interest", "Change in Open Interest", "options", "Change in OI versus the previous snapshot.", "ΔOI = Σ(call ΔOI + put ΔOI)", [], options_mod.change_in_open_interest, required="option_chain", status="implemented_awaiting_data", markets=MARKET_DERIV, timeframes=TIMEFRAMES_DAILY),
    _spec("option_chain_analysis", "Option Chain Analysis", "options", "Aggregate chain summary with key OI strikes.", "max call OI strike, max put OI strike, totals", [], options_mod.option_chain_analysis, required="option_chain", status="implemented_awaiting_data", markets=MARKET_DERIV, timeframes=TIMEFRAMES_DAILY),
    _spec("max_pain", "Max Pain", "options", "Strike where option holders lose the most.", "argmin Σ [OI_call·max(0,S-K) + OI_put·max(0,K-S)]", [], options_mod.max_pain, required="option_chain", status="implemented_awaiting_data", markets=MARKET_DERIV, timeframes=TIMEFRAMES_DAILY),
    _spec("implied_volatility", "Implied Volatility (IV)", "options", "ATM IV solved from the option price.", "Black-Scholes implied σ (Newton + bisection)", _OPT_PARAMS, options_mod.implied_volatility_indicator, required="option_chain", status="implemented_awaiting_data", markets=MARKET_DERIV, timeframes=TIMEFRAMES_DAILY, note="Model: Black-Scholes, European, no dividends."),
    _spec("iv_rank", "IV Rank", "options", "Current IV position in its range.", "IVR = 100·(IV - min)/(max - min)", _OPT_PARAMS, options_mod.iv_rank, required="iv_history", status="implemented_awaiting_data", markets=MARKET_DERIV, timeframes=TIMEFRAMES_DAILY),
    _spec("iv_percentile", "IV Percentile", "options", "Share of history below the current IV.", "percentile = 100·count(IV_hist <= IV)/N", _OPT_PARAMS, options_mod.iv_percentile, required="iv_history", status="implemented_awaiting_data", markets=MARKET_DERIV, timeframes=TIMEFRAMES_DAILY),
    _spec("delta", "Delta", "options", "Sensitivity of the option price to spot.", "Δ_call = N(d1); Δ_put = N(d1) - 1", _OPT_PARAMS, options_mod.delta, required="option_chain", status="implemented_awaiting_data", markets=MARKET_DERIV, timeframes=TIMEFRAMES_DAILY),
    _spec("gamma", "Gamma", "options", "Sensitivity of delta to spot.", "Γ = φ(d1)/(S·σ·√T)", _OPT_PARAMS, options_mod.gamma, required="option_chain", status="implemented_awaiting_data", markets=MARKET_DERIV, timeframes=TIMEFRAMES_DAILY),
    _spec("theta", "Theta", "options", "Time decay per calendar day.", "Θ = -(S·φ(d1)·σ)/(2√T) - rK e^{-rT} N(d2), /365", _OPT_PARAMS, options_mod.theta, required="option_chain", status="implemented_awaiting_data", markets=MARKET_DERIV, timeframes=TIMEFRAMES_DAILY),
    _spec("vega", "Vega", "options", "Sensitivity to a 1-point volatility change.", "ν = S·φ(d1)·√T / 100", _OPT_PARAMS, options_mod.vega, required="option_chain", status="implemented_awaiting_data", markets=MARKET_DERIV, timeframes=TIMEFRAMES_DAILY),
    _spec("rho", "Rho", "options", "Sensitivity to a 1% rate change.", "ρ_call = K·T·e^{-rT}·N(d2)/100", _OPT_PARAMS, options_mod.rho, required="option_chain", status="implemented_awaiting_data", markets=MARKET_DERIV, timeframes=TIMEFRAMES_DAILY),
    _spec("gamma_exposure", "Gamma Exposure (GEX)", "options", "Dealer gamma exposure by strike.", "GEX = Σ Γ·OI·100·S²·0.01", _OPT_PARAMS, options_mod.gamma_exposure, required="option_chain", status="implemented_awaiting_data", markets=MARKET_DERIV, timeframes=TIMEFRAMES_DAILY),
    _spec("delta_exposure", "Delta Exposure (DEX)", "options", "Aggregate delta-adjusted open interest.", "DEX = Σ ±Δ·OI·100", _OPT_PARAMS, options_mod.delta_exposure, required="option_chain", status="implemented_awaiting_data", markets=MARKET_DERIV, timeframes=TIMEFRAMES_DAILY),
    _spec("futures_basis", "Futures Basis", "options", "Futures price minus spot.", "basis = futures - spot", [], options_mod.futures_basis, required="futures_and_spot", status="implemented_awaiting_data", markets=MARKET_DERIV, timeframes=TIMEFRAMES_DAILY),
    _spec("funding_rate", "Funding Rate", "options", "Perpetual funding rate (crypto venues).", "provider series", [], options_mod.funding_rate, required="funding_feed", status="unsupported_data", markets=MARKET_CRYPTO, timeframes=TIMEFRAMES_DAILY, note="No perpetual funding feed is configured for Indian markets."),
    _spec("liquidation_levels", "Liquidation Levels", "options", "Exchange liquidation clusters.", "provider series", [], options_mod.liquidation_levels, required="liquidation_feed", status="unsupported_data", markets=MARKET_CRYPTO, timeframes=TIMEFRAMES_DAILY),
    _spec("oi_weighted_price", "OI Weighted Price", "options", "Open-interest weighted strike price.", "Σ(strike·OI)/ΣOI", [], options_mod.oi_weighted_price, required="option_chain", status="implemented_awaiting_data", markets=MARKET_DERIV, timeframes=TIMEFRAMES_DAILY),
]

REGISTRY: Dict[str, dict] = {spec["id"]: spec for spec in SPECS}
assert len(SPECS) == 169, f"registry must hold 169 indicators, found {len(SPECS)}"
assert len(REGISTRY) == 169, "duplicate indicator ids in registry"

CATEGORY_COUNTS: Dict[str, int] = {}
for _spec_item in SPECS:
    CATEGORY_COUNTS[_spec_item["category"]] = CATEGORY_COUNTS.get(_spec_item["category"], 0) + 1

STATUS_COUNTS: Dict[str, int] = {}
for _spec_item in SPECS:
    STATUS_COUNTS[_spec_item["status"]] = STATUS_COUNTS.get(_spec_item["status"], 0) + 1


def public_spec(spec: dict) -> dict:
    """Registry entry without the compute callable (JSON-safe)."""
    return {k: v for k, v in spec.items() if k != "compute"}


def list_specs() -> List[dict]:
    return [public_spec(s) for s in SPECS]
