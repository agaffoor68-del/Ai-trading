"""Development smoke check: run every registered indicator on synthetic data.

Usage:  python3 tests/smoke_indicators.py
Not part of the unit-test suite (it is a manual diagnostic).
"""

import math
import random
import sys

sys.path.insert(0, ".")

from app.services.indicators import CATEGORY_COUNTS, REGISTRY, STATUS_COUNTS, get_engine  # noqa: E402


def build_candles(n: int = 320, seed: int = 7):
    random.seed(seed)
    candles = []
    price = 100.0
    for i in range(n):
        o = price
        c = o * (1 + random.uniform(-0.01, 0.01))
        h = max(o, c) * (1 + random.uniform(0, 0.005))
        low = min(o, c) * (1 - random.uniform(0, 0.005))
        candles.append(
            {"ts": 1700000000 + i * 60, "open": o, "high": h, "low": low, "close": c,
             "volume": random.randint(500, 5000)}
        )
        price = c
    return candles


def build_extras(candles):
    spot = candles[-1]["close"]
    chain = {
        "expiry": "2026-01-29",
        "spot": spot,
        "strikes": [
            {
                "strike": round(spot) + k * 50,
                "call": {"oi": 1000 + 100 * k, "change_oi": 50 - k, "iv": 0.12 + 0.001 * k,
                         "ltp": 100 + k, "bid": 99, "ask": 101, "delta": 0.5},
                "put": {"oi": 1200 + 80 * k, "change_oi": -20 + k, "iv": 0.13 + 0.001 * k,
                        "ltp": 90 + k, "bid": 89, "ask": 91, "delta": -0.5},
            }
            for k in range(-5, 6)
        ],
    }
    closes = [c["close"] for c in candles]
    return {
        "option_chain": chain,
        "spot": spot,
        "futures_price": spot * 1.002,
        "iv_history": [0.10 + 0.002 * i for i in range(60)],
        "benchmark": [c * (1 + 0.0001 * math.sin(i / 7)) for i, c in enumerate(closes)],
        "vix": 13.5,
        "india_vix": 12.1,
        "funding_rate": 0.0001,
        "liquidation_levels": [spot * 0.95, spot * 1.05],
        "volume_delta": [random.randint(-500, 500) for _ in closes],
        "buy_volume": [1000 + i for i in range(len(closes))],
        "sell_volume": [900 + i for i in range(len(closes))],
    }


def main() -> int:
    candles = build_candles()
    extras = build_extras(candles)
    engine = get_engine()
    failures = []
    empty = []
    for sid in REGISTRY:
        try:
            result = engine.calculate(sid, candles, None, extras)
            series = result.get("series") or {}
            levels = result.get("levels") or {}
            count = sum(len(v) for v in series.values() if isinstance(v, list))
            count += sum(len(v) for v in levels.values() if isinstance(v, list))
            count += sum(1 for v in levels.values() if not isinstance(v, list))
            count += len(result.get("meta") or {})
            if count == 0 and not result.get("meta"):
                empty.append((sid, result.get("status"), result.get("note")))
            if result.get("status") == "error":
                failures.append((sid, result.get("note")))
        except Exception as exc:  # noqa: BLE001
            failures.append((sid, f"{type(exc).__name__}: {exc}"))
    print("indicators:", len(REGISTRY))
    print("categories:", CATEGORY_COUNTS)
    print("statuses:", STATUS_COUNTS)
    print("failures:", len(failures))
    for item in failures:
        print("  FAIL", item)
    print("empty:", len(empty))
    for item in empty[:20]:
        print("  EMPTY", item)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
