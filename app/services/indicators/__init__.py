"""Indicator engine package.

``from app.services.indicators import get_engine, REGISTRY`` is the supported
entry point for API and service code.
"""

from .engine import Ctx, IndicatorEngine, IndicatorError, build_ctx, get_engine
from .registry import CATEGORIES, CATEGORY_COUNTS, REGISTRY, SPECS, STATUS_COUNTS, list_specs, public_spec

__all__ = [
    "Ctx",
    "IndicatorEngine",
    "IndicatorError",
    "build_ctx",
    "get_engine",
    "REGISTRY",
    "SPECS",
    "CATEGORIES",
    "CATEGORY_COUNTS",
    "STATUS_COUNTS",
    "list_specs",
    "public_spec",
]
