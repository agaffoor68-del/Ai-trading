"""Fyers access-token retrieval backed exclusively by PostgreSQL."""

import logging
from datetime import datetime, time, timedelta, timezone
from typing import Optional

from app.core.datetime_utils import IST, now_ist, to_utc

logger = logging.getLogger(__name__)


def _as_utc(value: datetime) -> datetime:
    """Normalize SQLAlchemy timestamps to UTC (naive DB timestamps are IST)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=IST)
    return value.astimezone(timezone.utc)


def _read_db_token() -> dict:
    # Lazy import avoids a module cycle: the OAuth module owns encryption and
    # the SQLAlchemy model operations, while this module handles expiry checks.
    from app.api.v1.endpoints.fyers_auth import get_fyers_token_from_db
    return get_fyers_token_from_db()


def _token_expiry(token_data: dict) -> Optional[datetime]:
    created_at = token_data.get("created_at")
    if not created_at:
        return None
    try:
        created = datetime.fromisoformat(created_at)
        return _as_utc(created) + timedelta(seconds=int(token_data.get("expires_in") or 86400))
    except (TypeError, ValueError):
        logger.error("Invalid Fyers token expiry metadata in PostgreSQL")
        return datetime.min.replace(tzinfo=timezone.utc)


def _is_expired(token_data: dict) -> bool:
    expires_at = _token_expiry(token_data)
    if expires_at is None:
        # Legacy token rows without creation time are treated as valid; Fyers
        # API validation remains the final authority for those credentials.
        return False
    current = to_utc(now_ist())
    today_630_ist = datetime.combine(now_ist().date(), time(6, 30), tzinfo=IST)
    daily_expiry = today_630_ist.astimezone(timezone.utc)
    return current >= expires_at or (current >= daily_expiry and expires_at < daily_expiry)


def save_fyers_token(access_token: str, expires_in: int = 86400, refresh_token: str = "") -> bool:
    """Verify a token just persisted by the OAuth callback in PostgreSQL.

    Kept as a compatibility hook for the callback; this function performs no
    separate write and never stores tokens in local files.
    """
    try:
        token_data = _read_db_token()
        if token_data.get("access_token") != access_token:
            logger.error("Fyers token verification failed after PostgreSQL commit")
            return False
        logger.info(f"Fyers token saved to DB: {access_token[:10]}...")
        return True
    except Exception:
        logger.exception("Could not verify Fyers token in PostgreSQL")
        return False


def get_fyers_token() -> Optional[str]:
    """Return the non-expired Fyers access token stored in PostgreSQL, if any."""
    try:
        token_data = _read_db_token()
        access_token = token_data.get("access_token")
        if not access_token:
            logger.info("Fyers token not found in PostgreSQL")
            return None
        if _is_expired(token_data):
            logger.info("Fyers token expired or missing in PostgreSQL")
            return None
        return access_token
    except Exception:
        logger.exception("Failed to load Fyers token from PostgreSQL")
        return None


def clear_fyers_token() -> bool:
    """Delete persisted Fyers credentials from PostgreSQL."""
    try:
        from app.core.database import SessionLocal
        from app.core.models import FyersToken
        with SessionLocal() as db:
            db.query(FyersToken).delete()
            db.commit()
        return True
    except Exception:
        logger.exception("Failed to clear Fyers token from PostgreSQL")
        return False


def get_fyers_token_status() -> dict:
    """Return PostgreSQL token validity metadata for status/debug endpoints."""
    try:
        token_data = _read_db_token()
        access_token = token_data.get("access_token")
        if not access_token:
            return {"exists": False, "valid": False, "message": "Token not found in PostgreSQL", "source": "database"}
        expires_at = _token_expiry(token_data)
        if _is_expired(token_data):
            return {
                "exists": True,
                "valid": False,
                "message": "Token expired",
                "expires_at": expires_at.isoformat() if expires_at else None,
                "source": "database",
            }
        return {
            "exists": True,
            "valid": True,
            "message": "Token valid",
            "expires_at": expires_at.isoformat() if expires_at else None,
            "token_preview": access_token[:10] + "..." if len(access_token) > 10 else access_token,
            "source": "database",
        }
    except Exception as error:
        logger.exception("Failed to read Fyers token status from PostgreSQL")
        return {"exists": False, "valid": False, "message": f"Database token lookup failed: {error}", "source": "database"}
