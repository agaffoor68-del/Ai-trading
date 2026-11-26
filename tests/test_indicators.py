"""Unit tests for the indicator engine (stdlib unittest, no external deps).

Run:  python3 -m unittest discover -s tests -p "test_indicators.py" -v
"""

import math
import unittest

from app.services.indicators import CATEGORIES, REGISTRY, get_engine
from app.services.indicators.engine import IndicatorError, build_ctx
from app.services.indicators.options_analysis import black_scholes, implied_volatility
from app.services.indicators.series import ema, sma

ENGINE = get_engine()


def candles_from_closes(closes, volume=None, start_ts=1_700_000_000, step=86_400):
    volume = volume or [1000] * len(closes)
    out = []
    for i, close in enumerate(closes):
        out.append(
            {
                "ts": start_ts + i * step,
                "open": close,
                "high": close * 1.002,
                "low": close * 0.998,
                "close": close,
                "volume": volume[i],
            }
        )
    return out


def series_of(result, key):
    return result["series"][key]


class SeriesMathTests(unittest.TestCase):
    def test_sma_known_values(self):
        self.assertEqual(sma([1, 2, 3, 4, 5], 3), [None, None, 2.0, 3.0, 4.0])

    def test_sma_ignores_none(self):
        self.assertEqual(sma([1, None, 3, 4], 2), [None, None, None, 3.5])

    def test_ema_known_values(self):
        # period 3 -> alpha 0.5, seeded with the SMA of the first 3 values
        self.assertEqual(ema([1, 2, 3, 4, 5], 3), [None, None, 2.0, 3.0, 4.0])

    def test_ema_seed_is_sma(self):
        values = [5, 6, 7, 8, 9, 10]
        self.assertEqual(ema(values, 3)[2], 6.0)


class EngineTests(unittest.TestCase):
    def test_registry_has_169_unique_indicators(self):
        self.assertEqual(len(REGISTRY), 169)
        self.assertEqual(len(set(REGISTRY)), 169)

    def test_all_eight_categories_present(self):
        self.assertEqual(len(CATEGORIES), 8)
        counts = {}
        for spec in REGISTRY.values():
            counts[spec["category"]] = counts.get(spec["category"], 0) + 1
        self.assertEqual(
            counts,
            {"trend": 25, "momentum": 25, "volatility": 20, "volume": 25,
             "levels": 15, "structure": 20, "statistics": 20, "options": 19},
        )

    def test_metadata_is_complete(self):
        for spec in REGISTRY.values():
            for field in ("id", "name", "category", "description", "formula",
                          "required_data", "status", "chart",
                          "markets", "timeframes", "interpretation", "limitations"):
                self.assertTrue(spec.get(field), f"{spec['id']} missing {field}")
            self.assertIsInstance(spec["params"], list)
            self.assertIn(spec["status"], {
                "implemented_tested", "implemented_awaiting_data",
                "unsupported_data", "partial", "not_implemented",
            })
            for param in spec["params"]:
                self.assertIn(param["type"], {"int", "float", "str"})
                if param["type"] == "str":
                    continue
                self.assertLessEqual(param["min"], param["default"])
                self.assertGreaterEqual(param["max"], param["default"])

    def test_every_indicator_runs_on_daily_candles(self):
        closes = [100 + 5 * math.sin(i / 9) + i * 0.1 for i in range(400)]
        candles = candles_from_closes(closes, volume=[1000 + 10 * i for i in range(400)])
        failures = {}
        for sid in REGISTRY:
            result = ENGINE.calculate(sid, candles)
            if result.get("status") == "error":
                failures[sid] = result.get("note")
        self.assertEqual(failures, {})

    def test_previous_week_and_month_levels(self):
        closes = [100 + i * 0.5 for i in range(400)]
        candles = candles_from_closes(closes)
        week = ENGINE.calculate("prev_week_high_low", candles)
        month = ENGINE.calculate("prev_month_high_low", candles)
        self.assertIn("prev_week_high", week["levels"])
        self.assertIn("prev_month_high", month["levels"])

    def test_insufficient_data_is_reported(self):
        candles = candles_from_closes([1, 2, 3])
        result = ENGINE.calculate("sma", candles, {"period": 200})
        self.assertEqual(result["status"], "insufficient_data")
        self.assertTrue(all(v is None for v in series_of(result, "sma")))

    def test_unknown_indicator_raises(self):
        with self.assertRaises(IndicatorError):
            ENGINE.calculate("does_not_exist", candles_from_closes([1, 2, 3]))

    def test_invalid_params_rejected(self):
        candles = candles_from_closes([1, 2, 3, 4, 5])
        with self.assertRaises(IndicatorError):
            ENGINE.calculate("sma", candles, {"period": 0})
        with self.assertRaises(IndicatorError):
            ENGINE.calculate("sma", candles, {"period": "twenty"})

    def test_no_look_ahead(self):
        closes = [100 + 3 * math.sin(i / 5) for i in range(120)]
        short = ENGINE.calculate("rsi", candles_from_closes(closes[:60]))["series"]["rsi"]
        full = ENGINE.calculate("rsi", candles_from_closes(closes))["series"]["rsi"]
        for i in range(0, 60, 7):
            if short[i] is None:
                continue
            self.assertAlmostEqual(short[i], full[i], places=9)

    def test_missing_candle_propagates_none(self):
        candles = candles_from_closes([1, 2, 3, 4, 5, 6])
        candles[3]["close"] = None
        result = ENGINE.calculate("sma", candles, {"period": 3})
        self.assertIsNone(series_of(result, "sma")[5])

    def test_cache_flag(self):
        candles = candles_from_closes([1, 2, 3, 4, 5])
        ENGINE.clear_cache()
        first = ENGINE.calculate("ema", candles)
        second = ENGINE.calculate("ema", candles)
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(first["series"], second["series"])

    def test_batch_and_many(self):
        candles = candles_from_closes([1, 2, 3, 4, 5])
        many = ENGINE.calculate_many(["sma", "ema"], candles)
        self.assertEqual(set(many), {"sma", "ema"})
        batch = ENGINE.batch([{"symbol": "A", "candles": candles}], ["sma"])
        self.assertIn("A", batch)

    def test_ctx_build_from_tuples(self):
        ctx = build_ctx([(1, 10, 11, 9, 10.5, 100)])
        self.assertEqual(ctx.n, 1)
        self.assertEqual(ctx.close, [10.5])


class IndicatorValueTests(unittest.TestCase):
    """Hand-computed reference values (no third-party library involved)."""

    def test_sma_indicator(self):
        candles = candles_from_closes([1, 2, 3, 4, 5])
        self.assertEqual(series_of(ENGINE.calculate("sma", candles, {"period": 3}), "sma"),
                         [None, None, 2.0, 3.0, 4.0])

    def test_rsi_all_gains_is_100(self):
        candles = candles_from_closes([1, 2, 3, 4, 5, 6, 7, 8])
        rsi_values = series_of(ENGINE.calculate("rsi", candles, {"period": 3}), "rsi")
        self.assertAlmostEqual(rsi_values[-1], 100.0)

    def test_rsi_all_losses_is_0(self):
        candles = candles_from_closes([8, 7, 6, 5, 4, 3, 2, 1])
        rsi_values = series_of(ENGINE.calculate("rsi", candles, {"period": 3}), "rsi")
        self.assertAlmostEqual(rsi_values[-1], 0.0)

    def test_macd_constant_price_is_zero(self):
        candles = candles_from_closes([100] * 60)
        macd = series_of(ENGINE.calculate("macd", candles), "macd")
        self.assertAlmostEqual(macd[-1], 0.0)

    def test_bollinger_constant_price_has_zero_width(self):
        candles = candles_from_closes([100] * 30)
        result = ENGINE.calculate("bollinger", candles)
        self.assertAlmostEqual(result["levels"]["upper"][-1], 100.0)
        self.assertAlmostEqual(result["levels"]["lower"][-1], 100.0)

    def test_stochastic_close_at_high_is_100(self):
        candles = candles_from_closes([10, 11, 12, 13, 14])
        for candle in candles:
            candle["close"] = candle["high"]
        k = series_of(ENGINE.calculate("stochastic", candles, {"period": 3, "smooth_k": 1, "period_d": 1}), "k")
        self.assertAlmostEqual(k[-1], 100.0)

    def test_vwap_is_volume_weighted(self):
        candles = [
            {"ts": 1_700_000_000, "open": 10, "high": 10, "low": 10, "close": 10, "volume": 100},
            {"ts": 1_700_000_060, "open": 20, "high": 20, "low": 20, "close": 20, "volume": 300},
        ]
        vwap = series_of(ENGINE.calculate("vwap", candles), "vwap")
        self.assertAlmostEqual(vwap[-1], (10 * 100 + 20 * 300) / 400)

    def test_obv_accumulates_signed_volume(self):
        candles = [
            {"ts": 1, "open": 10, "high": 10, "low": 10, "close": 10, "volume": 100},
            {"ts": 2, "open": 10, "high": 11, "low": 10, "close": 11, "volume": 200},
            {"ts": 3, "open": 11, "high": 11, "low": 9, "close": 9, "volume": 50},
        ]
        obv = series_of(ENGINE.calculate("obv", candles), "obv")
        self.assertEqual(obv, [100.0, 300.0, 250.0])

    def test_atr_constant_range(self):
        candles = candles_from_closes([100] * 10)
        for candle in candles:
            candle["high"] = 101
            candle["low"] = 99
        atr_values = series_of(ENGINE.calculate("atr", candles, {"period": 3}), "atr")
        self.assertAlmostEqual(atr_values[-1], 2.0)

    def test_supertrend_direction_flips(self):
        closes = [100] * 30 + [110] * 30
        candles = candles_from_closes(closes)
        result = ENGINE.calculate("supertrend", candles)
        self.assertIn(1, [v for v in series_of(result, "direction") if v is not None])

    def test_fair_value_gap_detection(self):
        candles = [
            {"ts": 1, "open": 10, "high": 11, "low": 9, "close": 10, "volume": 10},
            {"ts": 2, "open": 10, "high": 10.5, "low": 9.5, "close": 10, "volume": 10},
            {"ts": 3, "open": 12, "high": 13, "low": 11.5, "close": 12.5, "volume": 10},
        ]
        result = ENGINE.calculate("fair_value_gaps", candles)
        gaps = result["meta"]["gaps"]
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["type"], "bullish")
        self.assertAlmostEqual(gaps[0]["low"], 11.0)
        self.assertAlmostEqual(gaps[0]["high"], 11.5)

    def test_inside_bar_detection(self):
        candles = [
            {"ts": 1, "open": 10, "high": 12, "low": 8, "close": 11, "volume": 10},
            {"ts": 2, "open": 11, "high": 11.5, "low": 9, "close": 10, "volume": 10},
        ]
        result = ENGINE.calculate("inside_bar", candles)
        self.assertEqual(series_of(result, "inside_bar")[1], 1)

    def test_zscore_of_constant_series_is_none(self):
        candles = candles_from_closes([100] * 30)
        z = series_of(ENGINE.calculate("z_score", candles), "z_score")
        self.assertIsNone(z[-1])

    def test_kalman_tracks_price(self):
        candles = candles_from_closes([100, 101, 102, 103, 104])
        k = series_of(ENGINE.calculate("kalman_filter", candles), "kalman")
        # the filter lags a linear ramp but must move monotonically towards it
        self.assertGreater(k[-1], 100.0)
        self.assertLess(k[-1], 104.0)
        self.assertGreater(k[-1], k[0])

    def test_max_pain_simple_chain(self):
        spot = 100.0
        chain = {
            "spot": spot,
            "expiry": "2026-01-01",
            "strikes": [
                {"strike": 90, "call": {"oi": 100, "iv": 0.2, "ltp": 12},
                 "put": {"oi": 10, "iv": 0.2, "ltp": 2}},
                {"strike": 100, "call": {"oi": 10, "iv": 0.2, "ltp": 2},
                 "put": {"oi": 100, "iv": 0.2, "ltp": 2}},
            ],
        }
        candles = candles_from_closes([100, 100, 100])
        result = ENGINE.calculate("max_pain", candles, None, {"option_chain": chain})
        # pain(90) = 10*10 = 100 ; pain(100) = 100*10 = 1000 -> max pain 90
        self.assertEqual(result["meta"]["max_pain"], 90)

    def test_put_call_ratio(self):
        chain = {"spot": 100.0, "strikes": [
            {"strike": 100, "call": {"oi": 200}, "put": {"oi": 300}},
        ]}
        result = ENGINE.calculate("put_call_ratio", candles_from_closes([100, 100]), None,
                                  {"option_chain": chain})
        self.assertAlmostEqual(result["meta"]["pcr"], 1.5)

    def test_black_scholes_put_call_parity(self):
        spot, strike, t, r, sigma = 100.0, 100.0, 0.25, 0.06, 0.2
        call, _ = black_scholes(spot, strike, t, r, sigma, "call")
        put, _ = black_scholes(spot, strike, t, r, sigma, "put")
        parity = call - put - (spot - strike * math.exp(-r * t))
        self.assertAlmostEqual(parity, 0.0, places=6)

    def test_greeks_sane_bounds(self):
        _price, g = black_scholes(100, 100, 0.25, 0.06, 0.2, "call")
        self.assertGreater(g["delta"], 0.4)
        self.assertLess(g["delta"], 0.7)
        self.assertGreater(g["gamma"], 0.0)
        self.assertGreater(g["vega"], 0.0)

    def test_implied_volatility_round_trip(self):
        price, _ = black_scholes(100, 100, 0.25, 0.06, 0.2, "call")
        self.assertAlmostEqual(implied_volatility(price, 100, 100, 0.25, 0.06, "call"), 0.2, places=3)

    def test_options_report_unavailable_without_chain(self):
        result = ENGINE.calculate("delta", candles_from_closes([100, 101]))
        self.assertEqual(result["status"], "data_unavailable")
        self.assertIn("data_unavailable", result["note"])

    def test_vix_scalar_extras(self):
        result = ENGINE.calculate("vix", candles_from_closes([100, 101]), None, {"vix": 13.5})
        self.assertAlmostEqual(series_of(result, "vix")[-1], 13.5)

    def test_benchmark_required_for_beta(self):
        without = ENGINE.calculate("beta", candles_from_closes([100, 101, 102]))
        self.assertEqual(without["status"], "data_unavailable")
        candles = candles_from_closes([100, 101, 102, 103, 104, 105, 106, 107])
        with_bench = ENGINE.calculate(
            "beta", candles, {"period": 3},
            {"benchmark": [c["close"] * 1.01 for c in candles]},
        )
        self.assertEqual(with_bench["status"], "implemented")


if __name__ == "__main__":
    unittest.main()
