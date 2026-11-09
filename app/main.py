"""
Phase 2: Core FastAPI Application

Non-Negotiable Rules:
1. DATA SOURCE: Fyers API v3 ONLY (historical, quotes, WebSocket)
2. EXECUTION: Kotak Neo ONLY (Phase 2)
3. AI: Grok API ONLY for financial news (Phase 3)
4. TIMEZONE: IST (Asia/Kolkata) ONLY
5. WEBSOCKETS: websockets==8.1 + wsproto (Render crash prevention)
6. DATABASE: PostgreSQL ONLY (No SQLite)
"""

import os
import logging
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, SessionLocal, Base, Instrument, init_db
from app.core.models import User, Subscription  # noqa: F401 - register models with Base.metadata
from app.core.time_sync import time_syncer
from app.core.auth import seed_admin_user
from app.api.v1.endpoints.fyers_auth import router as fyers_router
from app.api.v1.endpoints.market import router as market_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.admin import router as admin_router
from app.services.symbol_master import SymbolMasterDownloader

import aiohttp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

app = FastAPI(
    title="Autonomous Options Trading Platform - Phase 2",
    version="2.0.0",
    description="Authentication & Admin System - Fyers API v3 ONLY for data, Kotak Neo for execution",
)

origins = [
    "https://ai-trading-9fkt.vercel.app",
    "http://localhost:3000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fyers_router, prefix="/api/v1/fyers", tags=["fyers-auth"])
app.include_router(market_router, prefix="/api/v1/market", tags=["market-data"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])


@app.get("/", tags=["root"])
async def root():
    return {
        "message": "Autonomous Options Trading Platform - Phase 2",
        "version": "2.0.0",
        "status": "running",
        "phase": 2,
        "modules": ["core_setup", "fyers_auth", "redis_cache", "auth", "admin"],
        "data_source": "Fyers API v3 ONLY",
        "execution": "Kotak Neo (Phase 2)",
        "ai": "Grok API (Phase 3)",
        "database": "PostgreSQL",
        "timezone": "IST (Asia/Kolkata)",
    }


@app.get("/health", tags=["root"])
async def health_check():
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        return {
            "status": "healthy",
            "database": "connected",
            "timezone": "IST",
            "ntp_synced": time_syncer.is_synced,
        }
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return {"status": "unhealthy", "database": "disconnected"}, 500


@app.on_event("startup")
async def startup_event():
    logger.info(">>> Phase 2: Core Setup Starting Up <<<")

    # 1. Initialize PostgreSQL database (creates all tables including User, Subscription)
    try:
        init_db()
        logger.info("PostgreSQL tables initialized")
    except Exception as e:
        logger.error(f"Database init error: {str(e)}")

    # 2. Seed default admin user (agaffoor68@gmail.com / Abdul@222)
    try:
        seed_admin_user()
    except Exception as e:
        logger.error(f"Admin seeder error: {str(e)}")

    # 3. Sync time with NTP (institutional-grade timekeeping)
    try:
        result = await time_syncer.sync()
        if result.synced:
            logger.info(
                f"NTP synced: {result.server} | offset={result.offset_seconds}s | "
                f"drift={result.drift_seconds}s"
            )
        else:
            logger.warning(f"NTP sync failed: {result.error}")
    except Exception as e:
        logger.error(f"NTP sync error: {str(e)}")

    # 4. Download and sync Fyers Symbol Master (NSE_CM.csv, NSE_FO.csv)
    try:
        logger.info("Starting Fyers Symbol Master download...")
        downloader = SymbolMasterDownloader()
        total_instruments = await downloader.load_all()
        await downloader.close()
        logger.info(f"Fyers Symbol Master sync complete: {total_instruments} instruments loaded")
    except Exception as e:
        logger.error(f"Fyers Symbol Master download error: {str(e)}")

    # 5. Log instrument count
    db = SessionLocal()
    try:
        count = db.query(Instrument).count()
        logger.info(f"Symbol master: {count} instruments loaded in PostgreSQL")
    except Exception as e:
        logger.error(f"Error counting instruments: {str(e)}")
    finally:
        db.close()

    logger.info(">>> Phase 2 Startup Complete <<<")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info(">>> Phase 2 Shutting Down <<<")


@app.get("/info", tags=["debug"])
async def app_info():
    return {
        "app_name": "Autonomous Options Trading Platform",
        "version": "2.0.0",
        "phase": 2,
        "backend": "FastAPI + Python",
        "database": "PostgreSQL (No SQLite)",
        "data_source": "Fyers API v3 ONLY",
        "execution": "Kotak Neo (Phase 2)",
        "ai": "Grok API (Phase 3)",
        "timezone": "IST (Asia/Kolkata)",
        "websockets": "websockets==8.1 + wsproto",
        "ntp_synced": time_syncer.is_synced,
        "auth": "JWT + passlib (bcrypt)",
        "admin_seeder": "agaffoor68@gmail.com",
    }
