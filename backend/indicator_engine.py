# Indicator Engine Header
import pandas as pd
import pandas_ta as ta
print("File created")

# Indicator Registry Part 1 - Trend
INDICATOR_REGISTRY = {
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
    # Momentum Indicators
    "rsi": {
        "func": ta.rsi,
        "params": {"default": {"length": 14}},
        "output_cols": ["RSI_14"],
        "output_names": {"RSI_14": "rsi"},
        "category": "momentum",
    },
    "mom": {
        "func": ta.mom,
        "params": {"default": {"length": 10}},
        "output_cols": ["MOM_10"],
        "output_names": {"MOM_10": "momentum"},
        "category": "momentum",
    },
    "roc": {
        "func": ta.roc,
        "params": {"default": {"length": 10}},
        "output_cols": ["ROC_10"],
        "output_names": {"ROC_10": "roc"},
        "category": "momentum",
    },
    # Volatility Indicators
    "bbands": {
        "func": ta.bbands,
        "params": {"default": {"length": 20, "std": 2}},
        "output_cols": ["BBL_20_2.0", "BBM_20_2.0", "BBU_20_2.0"],
        "output_names": {
            "BBL_20_2.0": "bb_lower",
            "BBM_20_2.0": "bb_middle",
            "BBU_20_2.0": "bb_upper",
        },
        "category": "volatility",
    },
    "atr": {
        "func": ta.atr,
        "params": {"default": {"length": 14}},
        "output_cols": ["ATR_14"],
        "output_names": {"ATR_14": "atr"},
        "category": "volatility",
    },
    # Volume Indicators
    "obv": {
        "func": ta.obv,
        "params": {"default": {}},
        "output_cols": ["OBV"],
        "output_names": {"OBV": "obv"},
        "category": "volume",
    },
    "cmf": {
        "func": ta.cmf,
        "params": {"default": {"length": 20}},
        "output_cols": ["CMF_20"],
        "output_names": {"CMF_20": "cmf"},
        "category": "volume",
    },
}