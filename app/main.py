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

import logging
import asyncio
from datetime import date
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal, Instrument, init_db
from app.core.models import User, Subscription  # noqa: F401 - register models with Base.metadata
from app.core.time_sync import time_syncer
from app.core.auth import seed_admin_user
from app.api.v1.endpoints.fyers_auth import router as fyers_router
from app.api.v1.endpoints.market import router as market_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.admin import router as admin_router
from app.services.symbol_master import SymbolMasterDownloader
from app.services.redis_ws import redis_tick_store
from app.services.fyers_websocket import start_fyers_websocket, stop_fyers_websocket, get_fyers_ws_status
from app.services.fyers_token import get_fyers_token


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
    "https://ai-trading-9qoa.onrender.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex="https://.*\\.vercel\\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fyers_router, prefix="/api/v1/fyers", tags=["fyers-auth"])
app.include_router(market_router, prefix="/api/v1/market", tags=["market-data"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])


@app.get("/", tags=["root"])
@app.head("/", tags=["root"])
async def root():
    return {
        "message": "Autonomous Options Trading Platform - Phase 2",
        "version": "2.0.0",
        "status": "running",
        "phase": 2,
        "modules": ["core_setup", "fyers_auth", "redis_cache", "fyers_websocket", "auth", "admin"],
        "data_source": "Fyers API v3 ONLY",
        "execution": "Kotak Neo (Phase 2)",
        "ai": "Grok API (Phase 3)",
        "database": "PostgreSQL",
        "timezone": "IST (Asia/Kolkata)",
    }


@app.get("/health", tags=["root"])
@app.head("/health", tags=["root"])
async def health_check():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        redis_connected = redis_tick_store.is_connected()
        return {
            "status": "healthy",
            "database": "connected",
            "redis_connected": redis_connected,
            "timezone": "IST",
            "ntp_synced": time_syncer.is_synced,
        }
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return {"status": "unhealthy", "database": "disconnected", "redis_connected": False}, 500


# Global Fyers WebSocket manager (replaces old fyers_ws)
fyers_ws_manager = None
symbol_sync_task: asyncio.Task | None = None


def _should_sync_symbols() -> bool:
    """Check if symbol master needs sync (not loaded today)."""
    try:
        db = SessionLocal()
        try:
            # Check if we have instruments loaded today
            today = date.today()
            count = db.query(Instrument).filter(
                Instrument.is_active == 1,
                Instrument.created_at >= today
            ).count()
            return count == 0
        finally:
            db.close()
    except Exception:
        return True  # If check fails, try to sync


async def sync_symbols_and_start_websocket():
    global fyers_ws_manager

    try:
        # Skip if already loaded today
        if not _should_sync_symbols():
            logger.info("Symbol master already loaded today, skipping sync")
        else:
            logger.info("Starting Fyers Symbol Master download in background...")
            downloader = SymbolMasterDownloader()
            try:
                total_instruments = await downloader.load_all()
                logger.info("Fyers Symbol Master sync complete: %s instruments loaded", total_instruments)
            finally:
                await downloader.close()
    except Exception:
        logger.exception("Fyers Symbol Master background sync failed")

    try:
        token = get_fyers_token()
        if not token:
            logger.warning("No Fyers token - WebSocket not started. Will start after login.")
            return

        # Get client_id from settings
        client_id = settings.FYERS_CLIENT_ID
        if not client_id:
            logger.warning("FYERS_CLIENT_ID not configured - WebSocket not started")
            return

        db = SessionLocal()
        try:
            symbols = db.query(Instrument.symbol).filter(
                Instrument.is_active == 1,
                Instrument.instrument_type.in_(["10", "13", "INDEX", "EQ", "EQUITY"]),
            ).limit(50).all()
            symbol_list = [row[0] for row in symbols]
        finally:
            db.close()

        # Start WebSocket manager with official SDK
        success = await start_fyers_websocket(client_id, token, symbol_list)
        if success:
            logger.info("Fyers WebSocket manager started (official SDK)")
        else:
            logger.warning("Fyers WebSocket manager failed to start - check token validity")
            
    except Exception:
        logger.exception("Fyers WebSocket startup error")


@app.get("/api/fyers/ws-status", tags=["market-data"])
@app.head("/api/fyers/ws-status", tags=["market-data"])
async def fyers_ws_status():
    ws_status = get_fyers_ws_status()
    ws_status["redis_connected"] = redis_tick_store.is_connected()
    return ws_status


@app.get("/api/fyers/status", tags=["fyers-auth"])
async def fyers_status():
    """
    Get Fyers and Kotak connection status.
    
    Returns:
    {
        "fyers": {"connected": true, "valid": true, "message": "..."},
        "kotak": {"configured": true, "connected": true, "message": "..."},
        "market": {"is_open": true, "is_trading_day": true, ...}
    }
    """
    # Get Fyers status
    from app.services.fyers_token import get_fyers_token, get_fyers_token_status
    from app.services.fyers_api import fyers_api_client
    
    token = get_fyers_token()
    fyers_connected = False
    fyers_valid = False
    fyers_message = "No Fyers token found"
    
    if token:
        try:
            token_status = get_fyers_token_status()
            if token_status.get("valid", False):
                # Validate with profile API
                profile = await fyers_api_client.get_profile(token)
                if profile:
                    fyers_connected = True
                    fyers_valid = True
                    fyers_message = "Fyers connected and token valid"
                else:
                    fyers_message = "Token validation failed"
            else:
                fyers_message = token_status.get("message", "Token expired")
        except Exception as e:
            fyers_message = f"Token validation error: {str(e)}"
    
    # Get Kotak status (safe, never throws)
    kotak_configured = bool(settings.KOTAK_CONSUMER_KEY and settings.KOTAK_CONSUMER_SECRET)
    kotak_connected = False
    kotak_message = "Not configured"
    if kotak_configured:
        try:
            # Just check if credentials exist, don't actually connect
            kotak_connected = True
            kotak_message = "Configured"
        except Exception:
            kotak_message = "Configuration error"
    
    # Get market status
    from app.core.market_calendar import MarketCalendar
    from app.core.datetime_utils import now_ist
    market_cal = MarketCalendar()
    now = now_ist()
    market_status = {
        "is_open": market_cal.is_market_open(now),
        "is_trading_day": market_cal.is_trading_day(now.date()),
        "time_to_close_minutes": market_cal.time_to_close(now),
    }
    
    return {
        "fyers": {
            "connected": fyers_connected,
            "valid": fyers_valid,
            "message": fyers_message,
        },
        "kotak": {
            "configured": kotak_configured,
            "connected": kotak_connected,
            "message": kotak_message,
        },
        "market": market_status,
    }


@app.get("/api/market/status", tags=["market-data"])
async def market_status():
    """Get current market status (alias for /api/fyers/status market portion)."""
    from app.core.market_calendar import MarketCalendar
    from app.core.datetime_utils import now_ist
    market_cal = MarketCalendar()
    now = now_ist()
    return {
        "is_open": market_cal.is_market_open(now),
        "is_trading_day": market_cal.is_trading_day(now.date()),
        "time_to_close_minutes": market_cal.time_to_close(now),
        "timezone": "Asia/Kolkata",
    }


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

    # 4. Start Redis connection manager (non-fatal, background retry)
    try:
        logger.info("Starting Redis connection manager...")
        await redis_tick_store.start()
        if redis_tick_store.is_connected():
            logger.info("Redis connected successfully")
        else:
            logger.warning("Redis not connected at startup - will retry in background")
    except Exception as e:
        logger.error("Failed to start Redis manager: %s", e)
        # Don't raise - keep server running

    # 5. Validate/Load Fyers token
    try:
        token = get_fyers_token()
        if token:
            logger.info(f"Fyers token loaded from storage (length: {len(token)})")
            # Validate token with Fyers profile API
            try:
                from app.services.fyers_api import fyers_api_client
                profile = await fyers_api_client.get_profile(token)
                if profile:
                    logger.info(f"Fyers token validated - User: {profile.get('name', 'Unknown')}")
                else:
                    logger.warning("Fyers token validation failed - token may be expired")
            except Exception as e:
                logger.warning(f"Fyers token validation error: {str(e)}")
        else:
            logger.warning("No Fyers token found - market data will be unavailable until login")
    except Exception as e:
        logger.error(f"Fyers token load error: {str(e)}")

    # 6. Load the large symbol master after the HTTP server has started.
    global symbol_sync_task
    symbol_sync_task = asyncio.create_task(
        sync_symbols_and_start_websocket(), name="fyers-symbol-sync-and-websocket"
    )

    logger.info(">>> Phase 2 Startup Complete; symbol sync running in background <<<")


@app.on_event("shutdown")
async def shutdown_event():
    global fyers_ws_manager, symbol_sync_task
    logger.info(">>> Phase 2 Shutting Down <<<")

    if symbol_sync_task and not symbol_sync_task.done():
        symbol_sync_task.cancel()
        try:
            await symbol_sync_task
        except asyncio.CancelledError:
            pass

    # Close Fyers WebSocket manager
    await stop_fyers_websocket()
    logger.info("Fyers WebSocket manager stopped")
    
    # Close Redis connection
    try:
        await redis_tick_store.stop()
        logger.info("Redis connection manager stopped")
    except Exception as e:
        logger.error(f"Error stopping Redis manager: {e}")


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
        "websockets": "websockets client with additional_headers + wsproto server",
        "ntp_synced": time_syncer.is_synced,
        "auth": "JWT + passlib (bcrypt)",
        "admin_seeder": "agaffoor68@gmail.com",
    }
