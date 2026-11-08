"""
Market Regime Detection Module

Detects market regime using ADX and ATR indicators.
Returns: "TRENDING", "SIDEWAYS", or "VOLATILE"
"""
import pandas as pd
import pandas_ta as ta
from typing import Optional

logger = logging.getLogger(__name__)


def detect_market_regime(
    df: pd.DataFrame,
    adx_length: int = 14,
    atr_length: int = 14,
    atr_period: int = 10,
) -> str:
    """
    Detect market regime using ADX and ATR.

    Args:
        df: DataFrame with OHLCV data
        adx_length: Period for ADX calculation
        atr_length: Period for ATR calculation
        atr_period: Reference period for ATR spike detection

    Returns:
        One of: "TRENDING", "SIDEWAYS", "VOLATILE"
    """
    if df.empty or len(df) < adx_length + atr_period:
        return "SIDEWAYS"

    try:
        # Calculate ADX
        adx_df = ta.adx(length=adx_length)
        adx_col = [c for c in adx_df.columns if "ADX" in c.upper()][0] if adx_df.columns else None

        if adx_col and adx_col in df.columns:
            current_adx = df[adx_col].iloc[-1]
        else:
            current_adx = 20  # Default neutral

        # Calculate ATR
        atr_df = ta.atr(length=atr_length)
        atr_col = [c for c in atr_df.columns if "ATR" in c.upper()][0] if atr_df.columns else None

        if atr_col and atr_col in df.columns:
            current_atr = df[atr_col].iloc[-1]
            avg_atr = df[atr_col].rolling(window=atr_period).mean().iloc[-1]
            atr_ratio = current_atr / avg_atr if avg_atr > 0 else 1
        else:
            current_atr = 0
            avg_atr = 0
            atr_ratio = 1

        # Regime logic
        if current_adx > 25:
            # Strong ADX = trending market
            high_52w = df["high"].rolling(window=260).max().iloc[-1]
            low_52w = df["low"].rolling(window=260).min().iloc[-1]
            price_range = high_52w - low_52w if high_52w > low_52w else 1
            price_change_pct = (
                (df["close"].iloc[-1] - df["close"].iloc[-20]) / df["close"].iloc[-20] * 100
            ) if len(df) >= 20 else 0

            if abs(price_change_pct) > 1.5 or price_range > 0:
                return "TRENDING"
            else:
                # ADX > 25 but price not moving much = transition
                return "TRENDING" if current_adx > 30 else "SIDEWAYS"

        elif current_adx < 20:
            # Weak ADX = sideways market
            if atr_ratio > 1.5:
                # Low ADX but high ATR = volatile consolidation
                return "VOLATILE"
            return "SIDEWAYS"

        else:
            # 20 <= ADX <= 25 = transition zone
            if atr_ratio > 2.0:
                return "VOLATILE"
            # Check price action for direction
            recent_high = df["high"].iloc[-5:].max()
            recent_low = df["low"].iloc[-5:].min()
            if recent_high - recent_low > (df["close"].iloc[-1] * 0.02):
                return "TRENDING"
            return "SIDEWAYS"

    except Exception as e:
        logger.error(f"Error detecting market regime: {str(e)}")
        return "SIDEWAYS"  # Safe default


# Pre-defined regime thresholds
REGIME_THRESHOLDS = {
    "ADX_TRENDING": 25,
    "ADX_SIDEWAYS": 20,
    "ATR_VOLATILE_RATIO": 1.5,
    "ATR_EXTREME_RATIO": 2.0,
}


def get_regime_info(regime: str) -> dict:
    """Get human-readable information about a regime."""
    info = {
        "TRENDING": {
            "description": "Strong directional move, trend-following strategies work well",
            "risk_adjustment": 1.0,
            "signal_focus": ["trend_following", "breakout", "pullback"],
        },
        "SIDEWAYS": {
            "description": "Range-bound market, mean-reversion strategies work well",
            "risk_adjustment": 0.8,
            "signal_focus": ["range_trading", "mean_reversion", "oscillator"],
        },
        "VOLATILE": {
            "description": "High volatility, low ADX - risky for normal strategies",
            "risk_adjustment": 0.5,
            "signal_focus": ["options_straddles", "breakout_with_caution", "risk_management"],
        },
    }
    return info.get(regime, {})