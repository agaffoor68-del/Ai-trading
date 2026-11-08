"""
Options Trading Platform - Main FastAPI Application

Re-exports the app from app.main for compatibility with both
"main:app" and "app.main:app" uvicorn entry points.
"""

from app.main import app  # noqa: F401

__all__ = ["app"]
