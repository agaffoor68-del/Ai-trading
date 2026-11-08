"""
Indicator Engine Module

100+ Technical Indicators using pandas_ta for institutional options trading platform.
Categories: Trend, Momentum, Volatility, Volume, Cycle
Features: Dynamic calculation, Market Regime Detection, Confluence Engine
"""
import pandas as pd
import pandas_ta as ta
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = pd.options.mode.chained_assignment = None

# ============================================================================
# 1. INDICATOR REGISTRY (Part 1: Trend)
# ============================================================================

INDICATOR_REGISTRY: Dict[str, Dict[str, Any]] = {
    "supertrend": {
        "func": ta.supertrend,
        "params": {"default": {"length": 10, "multiplier": 3}},
        "output_cols": ["SUPERT_10_3.0", "SUPERTl_10_3.0"],
        "output_names": {"SUPERT_10_3.0": "supertrend", "SUPERTl_10_3.0": "supertrend_line"},
        "category": "trend",
    },
    "sma": {
        "func": ta.sma,
        "params": {"default": {"length": 20}},
        "output_cols": ["SMA_20"],
        "output_names": {"SMA_20": "sma"},
        "category": "trend",
    },
    "ema": {
        "func": ta.ema,
        "params": {"default": {"length": 12}},
        "output_cols": ["EMA_12"],
        "output_names": {"EMA_12": "ema"},
        "category": "trend",
    },
    "wma": {
        "func": ta.wma,
        "params": {"default": {"length": 20}},
        "output_cols": ["WMA_20"],
        "output_names": {"WMA_20": "wma"},
        "category": "trend",
    },
    "macd": {
        "func": ta.macd,
        "params": {"default": {"fast": 12, "slow": 26, "signal": 9}},
        "output_cols": ["MACD_12_26_9", "MACDh_12_26_9", "MACDs_12_26_9"],
        "output_names": {
            "MACD_12_26_9": "macd_line",
            "MACDh_12_26_9": "macd_histogram",
            "MACDs_12_26_9": "macd_signal",
        },
        "category": "trend",
    },
    "trix": {
        "func": ta.trix,
        "params": {"default": {"length": 14}},
        "output_cols": ["TRIX_14"],
        "output_names": {"TRIX_14": "trix"},
        "category": "trend",
    },
    "psar": {
        "func": ta.psar,
        "params": {"default": {"high": "High", "low": "Low"}},
        "output_cols": ["PSAR", "PSARl", "PSARaf"],
        "output_names": {
            "PSAR": "parabolic_sar",
            "PSARl": "parabolic_sar_low",
            "PSARaf": "parabolic_sar_acceleration",
        },
        "category": "trend",
    },
}