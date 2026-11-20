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

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal, Instrument, init_db
from app.core.models import User, Subscription, FyersToken  # noqa: F401 - register models with Base.metadata
from app.core.time_sync import time_syncer
from app.core.auth import seed_admin_user
from app.api.v1.endpoints.fyers_auth import router as fyers_router
from app.api.v1.endpoints.market import router as market_router
from app.api.v1.endpoints.auth import router as auth_router, get_current_user_info, MeResponse
from app.api.v1.endpoints.admin import router as admin_router
from app.services.symbol_master import SymbolMasterDownloader
from app.services.redis_ws import redis_tick_store
from app.services.fyers_websocket import start_fyers_websocket, stop_fyers_websocket, get_fyers_ws_status
from app.services.fyers_token import get_fyers_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

app = FastAPI(
    title="Autonomous Options Trading Platform - Phase 2",
    version="2.0.0",
    description="Authentication & Admin System - Fyers API v3 ONLY for data, Kotak Neo for execution",
)


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException):
    """Normalize Fyers auth failures for the market quotes and candles APIs."""
    market_token_routes = {"/api/v1/market/quotes", "/api/v1/market/candles"}
    if request.url.path in market_token_routes and exc.status_code == 401:
        detail = exc.detail
        if isinstance(detail, dict):
            code = detail.get("code")
            message = str(detail.get("message", detail.get("error", "")))
        else:
            code, message = None, str(detail)
        normalized_message = message.lower()
        is_fyers_token_error = (
            code in {"FYERS_NOT_CONNECTED", "FYERS_TOKEN_EXPIRED"}
            or ("fyers" in normalized_message and any(word in normalized_message for word in ("token", "authenticated", "expired", "invalid")))
        )
        if is_fyers_token_error:
            return JSONResponse(status_code=401, content={"error": "Fyers token expired", "code": 401}, headers=exc.headers)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)


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
    expose_headers=["*", "Authorization", "Content-Type"],
)

app.include_router(fyers_router, prefix="/api/v1/fyers", tags=["fyers-auth"])
app.include_router(market_router, prefix="/api/v1/market", tags=["market-data"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.add_api_route("/api/auth/me", get_current_user_info, methods=["GET"], response_model=MeResponse, tags=["auth"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])


@app.get("/", tags=["root"])
@app.head("/", tags=["root"])
async def root():
    return {
        "message": "Autonomous Options Trading Platform - Phase 2", "version": "2.0.0", "status": "running", "phase": 2,
        "modules": ["core_setup", "fyers_auth", "redis_cache", "fyers_websocket", "auth", "admin"],
        "data_source": "Fyers API v3 ONLY", "execution": "Kotak Neo (Phase 2)", "ai": "Grok API (Phase 3)",
        "database": "PostgreSQL", "timezone": "IST (Asia/Kolkata)",
    }


@app.get("/health", tags=["root"])
@app.head("/health", tags=["root"])
async def health_check():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        redis_connected = redis_tick_store.is_connected()
        return {"status": "healthy", "database": "connected", "redis_connected": redis_connected, "timezone": "IST", "ntp_synced": time_syncer.is_synced}
    except Exception as e:
        logger.error("Health check error: %s", e)
        return {"status": "unhealthy", "database": "disconnected", "redis_connected": False}, 500


fyers_ws_manager = None
symbol_sync_task: asyncio.Task | None = None


def _should_sync_symbols() -> bool:
    """Check if symbol master needs sync (not loaded today)."""
    try:
        db = SessionLocal()
        try:
            today = date.today()
            count = db.query(Instrument).filter(Instrument.is_active == 1, Instrument.created_at >= today).count()
            return count == 0
        finally:
            db.close()
    except Exception:
        return True


async def sync_symbols_and_start_websocket():
    global fyers_ws_manager
    try:
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
        client_id = settings.FYERS_CLIENT_ID
        if not client_id:
            try:
                from app.api.v1.endpoints.fyers_auth import restore_fyers_credentials
                if restore_fyers_credentials():
                    client_id = settings.FYERS_CLIENT_ID
            except Exception as error:
                logger.warning("Could not restore Fyers credentials: %s", error)
        if not client_id:
            logger.warning("FYERS_CLIENT_ID not configured - WebSocket not started")
            return
        db = SessionLocal()
        try:
            symbols = db.query(Instrument.symbol).filter(Instrument.is_active == 1, Instrument.instrument_type.in_(["0", "10", "13", "INDEX", "EQ", "EQUITY"])).limit(50).all()
            symbol_list = [row[0] for row in symbols]
        finally:
            db.close()
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
    """Get current Fyers and Kotak connection status."""
    from app.services.fyers_token import get_fyers_token, get_fyers_token_status
    from app.services.fyers_api import fyers_api_client
    token = get_fyers_token()
    fyers_connected = fyers_valid = False
    fyers_message = "No Fyers token found"
    if token:
        try:
            token_status = get_fyers_token_status()
            if token_status.get("valid", False):
                profile = await fyers_api_client.get_profile(token)
                if profile:
                    fyers_connected = fyers_valid = True
                    fyers_message = "Fyers connected and token valid"
                else:
                    fyers_message = "Token validation failed"
            else:
                fyers_message = token_status.get("message", "Token expired")
        except Exception as error:
            fyers_message = f"Token validation error: {error}"
    kotak_configured = bool(settings.KOTAK_CONSUMER_KEY and settings.KOTAK_CONSUMER_SECRET)
    kotak_connected = False
    kotak_message = "Configured (session not verified)" if kotak_configured else "Not configured"
    from app.core.market_calendar import MarketCalendar
    from app.core.datetime_utils import now_ist
    market_cal = MarketCalendar()
    now = now_ist()
    market_status = {"is_open": market_cal.is_market_open(now), "is_trading_day": market_cal.is_trading_day(now.date()), "time_to_close_minutes": market_cal.time_to_close(now)}
    return {
        "fyers": {"connected": fyers_connected, "valid": fyers_valid, "message": fyers_message},
        "kotak": {"configured": kotak_configured, "connected": kotak_connected, "message": kotak_message},
        "market": market_status,
    }


@app.get("/api/market/status", tags=["market-data"])
async def market_status():
    """Get current market status."""
    from app.core.market_calendar import MarketCalendar
    from app.core.datetime_utils import now_ist
    market_cal = MarketCalendar()
    now = now_ist()
    return {"is_open": market_cal.is_market_open(now), "is_trading_day": market_cal.is_trading_day(now.date()), "time_to_close_minutes": market_cal.time_to_close(now), "timezone": "Asia/Kolkata"}


@app.on_event("startup")
async def startup_event():
    logger.info(">>> Phase 2: Core Setup Starting Up <<<")
    init_db()
    logger.info("PostgreSQL tables initialized (including fyers_tokens)")
    try:
        seed_admin_user()
    except Exception as error:
        logger.error("Admin seeder error: %s", error)
    try:
        result = await time_syncer.sync()
        if result.synced:
            logger.info("NTP synced: %s | offset=%ss | drift=%ss", result.server, result.offset_seconds, result.drift_seconds)
        else:
            logger.warning("NTP sync failed: %s", result.error)
    except Exception as error:
        logger.error("NTP sync error: %s", error)
    try:
        logger.info("Starting Redis connection manager...")
        await redis_tick_store.start()
        if redis_tick_store.is_connected():
            logger.info("Redis connected successfully")
        else:
            logger.warning("Redis not connected at startup - will retry in background")
    except Exception as error:
        logger.error("Failed to start Redis manager: %s", error)
    try:
        try:
            from app.api.v1.endpoints.fyers_auth import restore_fyers_credentials
            restore_fyers_credentials()
        except Exception as error:
            logger.warning("Could not restore Fyers credentials at startup: %s", error)
        token = get_fyers_token()
        if token:
            logger.info("Fyers token loaded from PostgreSQL (length: %s)", len(token))
            try:
                from app.services.fyers_api import fyers_api_client
                profile = await fyers_api_client.get_profile(token)
                if profile:
                    logger.info("Fyers token validated - User: %s", profile.get("name", "Unknown"))
                else:
                    logger.warning("Fyers token validation failed - profile API returned no data")
            except Exception as error:
                logger.warning("Fyers token validation error: %s", error)
        else:
            logger.warning("No Fyers token found - market data will be unavailable until login")
    except Exception as error:
        logger.error("Fyers token load error: %s", error)
    global symbol_sync_task
    symbol_sync_task = asyncio.create_task(sync_symbols_and_start_websocket(), name="fyers-symbol-sync-and-websocket")
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
    await stop_fyers_websocket()
    logger.info("Fyers WebSocket manager stopped")
    try:
        await redis_tick_store.stop()
        logger.info("Redis connection manager stopped")
    except Exception as error:
        logger.error("Error stopping Redis manager: %s", error)


@app.get("/info", tags=["debug"])
async def app_info():
    return {
        "app_name": "Autonomous Options Trading Platform", "version": "2.0.0", "phase": 2,
        "backend": "FastAPI + Python", "database": "PostgreSQL (No SQLite)", "data_source": "Fyers API v3 ONLY",
        "execution": "Kotak Neo (Phase 2)", "ai": "Grok API (Phase 3)", "timezone": "IST (Asia/Kolkata)",
        "websockets": "websockets client with additional_headers + wsproto server", "ntp_synced": time_syncer.is_synced,
        "auth": "JWT + passlib (bcrypt)", "admin_seeder": "agaffoor68@gmail.com",
    }
