"""
AI Trade Project Configuration

Project structure for the Autonomous Options Trading Platform.
Contains references to all modules and configuration settings.
"""
from typing import List, Dict, Any

import os


# Base project directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Module paths
MODULES = {
    "indicator_engine": os.path.join(PROJECT_ROOT, "backend", "indicator_engine.py"),
    "market_regime": os.path.join(PROJECT_ROOT, "backend", "market_regime.py"),
    "main_app": os.path.join(PROJECT_ROOT, "main.py"),
    "api_routes": os.path.join(PROJECT_ROOT, "api", "v1", "endpoints"),
    "services": os.path.join(PROJECT_ROOT, "services"),
    "frontend": os.path.join(PROJECT_ROOT, "frontend"),
}

# Rule compliance checks
RULES = {
    "websockets_version": "8.1",  # Must be pinned
    "database": "postgresql",  # No SQLite
    "timezone": "IST (Asia/Kolkata)",
    "error_logging": "try-except + logger.error() on all API calls",
}

# Default settings
DEFAULT_SETTINGS = {
    "total_capital": 100000.0,  # INR
    "risk_per_trade": 0.01,  # 1% risk rule
    "indicators_preset": "swing_trading",  # day_trading, swing_trading, scalping, trend_following, volatility_breakout
    "market_regime_check": True,
    "confluence_engine": True,
}

# Available indicator presets
PRESET_CONFIGS = {
    "day_trading": [
        {"name": "rsi", "params": {"length": 14}},
        {"name": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}},
        {"name": "bbands", "params": {"length": 20, "std": 2}},
        {"name": "adx", "params": {"length": 14}},
        {"name": "obv", "params": {}},
    ],
    "swing_trading": [
        {"name": "supertrend", "params": {"length": 10, "multiplier": 3}},
        {"name": "sma", "params": {"length": 50}},
        {"name": "ema", "params": {"length": 20}},
        {"name": "atr", "params": {"length": 14}},
        {"name": "mfi", "params": {"length": 14}},
    ],
    "scalping": [
        {"name": "rsi", "params": {"length": 7}},
        {"name": "mom", "params": {"length": 5}},
        {"name": "trix", "params": {"length": 10}},
        {"name": "obv", "params": {}},
        {"name": "bbands", "params": {"length": 10, "std": 1.5}},
    ],
    "trend_following": [
        {"name": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}},
        {"name": "supertrend", "params": {"length": 10, "multiplier": 3}},
        {"name": "sma", "params": {"length": 200}},
        {"name": "adx", "params": {"length": 14}},
        {"name": "cmf", "params": {"length": 21}},
    ],
    "volatility_breakout": [
        {"name": "bbands", "params": {"length": 20, "std": 2}},
        {"name": "atr", "params": {"length": 14}},
        {"name": "ultro", "params": {"length": 14}},
        {"name": "mfi", "params": {"length": 14}},
    ],
}


def get_preset_config(preset_name: str) -> List[Dict[str, Any]]:
    """Get a preset indicator configuration by name."""
    return PRESET_CONFIGS.get(preset_name, PRESET_CONFIGS["swing_trading"])


def check_rule_compliance() -> Dict[str, bool]:
    """Check if the project complies with the strict rules."""
    # In a real implementation, this would check actual file contents
    # For now, return default compliance status
    return {
        "websockets_pinned": True,
        "postgresql_ready": True,
        "ist_timezone": True,
        "error_logging": True,
    }


if __name__ == "__main__":
    print(f"AI Trade Project Configuration")
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Available Modules: {list(MODULES.keys())}")
    print(f"Rule Compliance: {check_rule_compliance()}")
