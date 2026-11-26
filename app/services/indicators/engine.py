"""Indicator calculation engine.

Public API
----------
``IndicatorEngine.calculate(indicator_id, candles, params=None, extras=None)``
``IndicatorEngine.calculate_many(ids, candles, params=None, extras=None)``
``IndicatorEngine.batch(symbols_and_candles, ids, ...)``

Design notes
------------
* Pure Python, no pandas/numpy: identical results on the phone, in CI and on
  the production host.
* Look-ahead safety: every primitive only reads ``values[: i + 1]``; structure
  pivots need a right window, so a signal at bar *i* is only emitted once bar
  ``i + right`` exists.
* Missing / invalid candles are tolerated.  A series that cannot be produced
  yields ``status="insufficient_data"`` with a human-readable reason instead of
  fabricated numbers.
* Repainting indicators are flagged in the registry (``repaint=True``) and the
  flag is echoed in every response so the UI can warn the user.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from . import levels as levels_mod
from . import momentum as momentum_mod
from . import options_analysis as options_mod
from . import statistics as statistics_mod
from . import structure as structure_mod
from . import trend as trend_mod
from . import volatility as volatility_mod
from . import volume as volume_mod
from .series import to_float

Number = Optional[float]


@dataclass
class Ctx:
    """Bar arrays handed to indicator functions (all the same length)."""

    ts: List[int] = field(default_factory=list)
    open: List[Number] = field(default_factory=list)
    high: List[Number] = field(default_factory=list)
    low: List[Number] = field(default_factory=list)
    close: List[Number] = field(default_factory=list)
    volume: List[Number] = field(default_factory=list)
    extras: Dict[str, Any] = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.close)


class IndicatorError(ValueError):
    """Raised for an unknown indicator id or invalid parameters."""


def _as_list(value: Any) -> Any:
    """Keep list series as lists; scalar levels (e.g. a Fibonacci price) stay scalar."""
    if isinstance(value, (list, tuple)):
        return list(value)
    return value


def build_ctx(candles: Sequence[Any], extras: Optional[Dict[str, Any]] = None) -> Ctx:
    """Normalise candle input (dicts, objects or tuples) into a :class:`Ctx`."""
    ts: List[int] = []
    open_: List[Number] = []
    high: List[Number] = []
    low: List[Number] = []
    close: List[Number] = []
    volume: List[Number] = []
    for index, candle in enumerate(candles or []):
        if isinstance(candle, dict):
            get = candle.get
        elif isinstance(candle, (tuple, list)):
            values = list(candle) + [None] * 6
            get = lambda k, i=values: (  # noqa: E731 - tiny local accessor
                {"ts": values[0], "open": values[1], "high": values[2],
                 "low": values[3], "close": values[4], "volume": values[5]}.get(k)
            )
        else:
            get = lambda k, c=candle: getattr(c, k, None)  # noqa: E731
        ts.append(int(get("ts") or get("timestamp") or index))
        open_.append(to_float(get("open")))
        high.append(to_float(get("high")))
        low.append(to_float(get("low")))
        close.append(to_float(get("close")))
        volume.append(to_float(get("volume")))
    return Ctx(ts=ts, open=open_, high=high, low=low, close=close, volume=volume, extras=extras or {})


class IndicatorEngine:
    """Registry-driven calculator with a small per-instance cache."""

    def __init__(self, registry: Optional[Dict[str, dict]] = None):
        from .registry import REGISTRY

        self.registry = registry if registry is not None else REGISTRY
        self._cache: Dict[str, dict] = {}

    # ---------------------------------------------------------------- helpers
    def get(self, indicator_id: str) -> dict:
        spec = self.registry.get(indicator_id)
        if spec is None:
            raise IndicatorError(f"Unknown indicator id: {indicator_id}")
        return spec

    def clear_cache(self) -> None:
        self._cache.clear()

    @staticmethod
    def _cache_key(indicator_id: str, candles: Sequence[Any], params: dict, extras_keys: Sequence[str]) -> str:
        last = candles[-1] if candles else None
        if isinstance(last, dict):
            marker = (last.get("ts"), last.get("close"))
        else:
            marker = (getattr(last, "ts", None), getattr(last, "close", None))
        return f"{indicator_id}|{len(candles)}|{marker}|{sorted(params.items())}|{sorted(extras_keys)}"

    # ---------------------------------------------------------------- public
    def calculate(
        self,
        indicator_id: str,
        candles: Sequence[Any],
        params: Optional[dict] = None,
        extras: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> dict:
        spec = self.get(indicator_id)
        ctx = build_ctx(candles, extras)
        merged = self.validate_params(spec["id"], params or {})
        key = self._cache_key(indicator_id, candles, merged, list((extras or {}).keys()))
        if use_cache and key in self._cache:
            cached = dict(self._cache[key])
            cached["cached"] = True
            return cached

        result = self._invoke(spec, ctx, merged)
        result["indicator"] = {
            "id": spec["id"],
            "name": spec["name"],
            "category": spec["category"],
            "params": merged,
            "repaint": spec.get("repaint", False),
            "status": spec.get("status"),
            "bars": ctx.n,
        }
        result.setdefault("note", None)
        result.setdefault("meta", {})
        result["cached"] = False
        if use_cache:
            self._cache[key] = {k: v for k, v in result.items() if k != "cached"}
        return result

    def calculate_many(
        self,
        indicator_ids: Iterable[str],
        candles: Sequence[Any],
        params: Optional[dict] = None,
        extras: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, dict]:
        out: Dict[str, dict] = {}
        for indicator_id in indicator_ids:
            try:
                out[indicator_id] = self.calculate(indicator_id, candles, params, extras)
            except IndicatorError as exc:
                out[indicator_id] = {"error": str(exc), "status": "not_implemented"}
        return out

    def batch(
        self,
        items: Sequence[dict],
        indicator_ids: Iterable[str],
        params: Optional[dict] = None,
    ) -> Dict[str, Dict[str, dict]]:
        """``items`` = [{"symbol": "NIFTY", "candles": [...]}, ...]."""
        out: Dict[str, Dict[str, dict]] = {}
        for item in items:
            symbol = item.get("symbol") or "UNKNOWN"
            out[symbol] = self.calculate_many(
                indicator_ids,
                item.get("candles") or [],
                {**(params or {}), **(item.get("params") or {})},
                item.get("extras"),
            )
        return out

    # ---------------------------------------------------------------- internals
    @staticmethod
    def _merge_params(spec: dict, params: dict) -> dict:
        merged = {p["name"]: p["default"] for p in spec.get("params", [])}
        for key, value in (params or {}).items():
            if key in merged and value is not None:
                merged[key] = value
        return merged

    def _invoke(self, spec: dict, ctx: Ctx, params: dict) -> dict:
        fn = spec.get("compute")
        if fn is None:
            return {"series": {}, "levels": {}, "status": spec.get("status", "not_implemented"),
                    "note": spec.get("note") or "Calculation not implemented yet."}
        if ctx.n == 0:
            return {"series": {}, "levels": {}, "status": "insufficient_data",
                    "note": "No candles supplied."}
        try:
            raw = fn(ctx, params) or {}
        except (ZeroDivisionError, ValueError, OverflowError, TypeError) as exc:
            return {"series": {}, "levels": {}, "status": "error",
                    "note": f"Calculation failed: {exc}"}
        series = {k: _as_list(v) for k, v in (raw.get("series") or {}).items()}
        levels = {k: _as_list(v) for k, v in (raw.get("levels") or {}).items()}
        meta = raw.get("meta") or {}
        note = raw.get("note")
        status = "implemented"
        has_values = bool(levels) or bool(meta) or any(
            isinstance(v, (list, tuple)) and any(item is not None for item in v)
            for v in series.values()
        )
        if note == "data_unavailable":
            status = "data_unavailable"
        elif not has_values:
            status = "insufficient_data"
            note = note or "Not enough valid history for this indicator."
        return {"series": series, "levels": levels, "meta": meta, "note": note, "status": status}

    # ---------------------------------------------------------------- validation
    def validate_params(self, indicator_id: str, params: dict) -> dict:
        """Return the cleaned params, raising ``IndicatorError`` when invalid."""
        spec = self.get(indicator_id)
        merged = self._merge_params(spec, params or {})
        for definition in spec.get("params", []):
            value = merged.get(definition["name"])
            if value is None:
                continue
            if definition.get("type") == "int":
                if not isinstance(value, int) or isinstance(value, bool):
                    raise IndicatorError(f"{indicator_id}.{definition['name']} must be an integer")
            elif definition.get("type") == "float":
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    raise IndicatorError(f"{indicator_id}.{definition['name']} must be a number")
            if definition.get("min") is not None and value < definition["min"]:
                raise IndicatorError(f"{indicator_id}.{definition['name']} must be >= {definition['min']}")
            if definition.get("max") is not None and value > definition["max"]:
                raise IndicatorError(f"{indicator_id}.{definition['name']} must be <= {definition['max']}")
        return merged


_ENGINE: Optional[IndicatorEngine] = None


def get_engine() -> IndicatorEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = IndicatorEngine()
    return _ENGINE
