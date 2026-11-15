"""
Fyers Token Storage Utility

Persists Fyers access token to a JSON file for persistence across restarts.
"""

import json
import logging
import os
from pathlib import Path
from datetime import datetime, timedelta, time
from typing import Optional

from app.core.datetime_utils import IST, now_ist, to_ist, utc_to_epoch

logger = logging.getLogger(__name__)

# Token storage file path
TOKEN_FILE = Path("/workspace/projects/Ai-trading/var/fyers_token.json")

def ensure_token_dir():
    """Ensure the token storage directory exists."""
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

def save_fyers_token(access_token: str, expires_in: int = 86400, refresh_token: str = "") -> bool:
    """
    Save Fyers access token to JSON file.
    
    Args:
        access_token: The Fyers access token
        expires_in: Token lifetime in seconds (default 24h)
        refresh_token: Optional refresh token
    
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        ensure_token_dir()
        
        created_at = now_ist()
        expires_at = created_at + timedelta(seconds=expires_in)
        
        token_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at.isoformat(),
            "created_at": created_at.isoformat(),
            "expires_in": expires_in,
        }
        
        with open(TOKEN_FILE, "w") as f:
            json.dump(token_data, f, indent=2)
        
        logger.info(f"Fyers token saved to {TOKEN_FILE} (expires: {expires_at.isoformat()})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save Fyers token: {e}")
        return False

def get_fyers_token() -> Optional[str]:
    """
    Get valid Fyers access token from storage.
    
    Returns:
        Access token string if valid, None if missing/expired
    """
    try:
        # First try file
        if TOKEN_FILE.exists():
            with open(TOKEN_FILE, "r") as f:
                token_data = json.load(f)
            
            access_token = token_data.get("access_token", "")
            if access_token:
                # Check expiry - Fyers tokens expire daily at 6:30 AM IST
                expires_at_str = token_data.get("expires_at")
                if expires_at_str:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    # Ensure timezone-aware
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=IST)
                    else:
                        expires_at = expires_at.astimezone(IST)
                    now = now_ist()
                    
                    # Check if token was issued before today's 6:30 AM
                    today_630 = datetime.combine(now.date(), time(6, 30, tzinfo=IST))
                    if now >= today_630 and expires_at < today_630:
                        logger.warning("Fyers access token expired at 6:30 AM IST today")
                        # Don't return None yet, try database
                    elif now >= expires_at:
                        logger.warning("Fyers access token has expired")
                        # Don't return None yet, try database
                    else:
                        logger.info(f"Fyers token loaded from {TOKEN_FILE} (valid)")
                        return access_token
                else:
                    # No expiry info, assume valid
                    logger.info(f"Fyers token loaded from {TOKEN_FILE} (no expiry info)")
                    return access_token
        
        # Fallback to database
        logger.info("Trying database for Fyers token")
        from app.api.v1.endpoints.fyers_auth import get_fyers_token_from_db
        db_token = get_fyers_token_from_db()
        if db_token:
            access_token = db_token.get("access_token", "")
            if access_token:
                # Check expiry using created_at + expires_in
                created_at_str = db_token.get("created_at")
                expires_in = db_token.get("expires_in", 86400)
                if created_at_str:
                    created_at = datetime.fromisoformat(created_at_str)
                    # Ensure timezone-aware
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=IST)
                    else:
                        created_at = created_at.astimezone(IST)
                    expires_at = created_at + timedelta(seconds=expires_in)
                    now = now_ist()
                    
                    today_630 = datetime.combine(now.date(), time(6, 30, tzinfo=IST))
                    if now >= today_630 and expires_at < today_630:
                        logger.warning("Fyers database token expired at 6:30 AM IST today")
                        return None
                    elif now >= expires_at:
                        logger.warning("Fyers database token has expired")
                        return None
                
                logger.info("Fyers token loaded from database (valid)")
                return access_token
        
        logger.warning("Fyers token not found in file or database")
        return None
        
    except Exception as e:
        logger.error(f"Failed to load Fyers token: {e}")
        return None

def clear_fyers_token() -> bool:
    """Clear the stored Fyers token."""
    try:
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()
            logger.info("Fyers token file deleted")
        return True
    except Exception as e:
        logger.error(f"Failed to clear Fyers token: {e}")
        return False

def get_fyers_token_status() -> dict:
    """Get token status for debugging."""
    try:
        # First try file
        if TOKEN_FILE.exists():
            with open(TOKEN_FILE, "r") as f:
                token_data = json.load(f)
            
            access_token = token_data.get("access_token", "")
            expires_at_str = token_data.get("expires_at")
            
            if access_token:
                # Check expiry - Fyers tokens expire daily at 6:30 AM IST
                if expires_at_str:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    # Ensure timezone-aware
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=IST)
                    else:
                        expires_at = expires_at.astimezone(IST)
                    now = now_ist()
                    
                    # Check if token was issued before today's 6:30 AM
                    today_630 = datetime.combine(now.date(), time(6, 30, tzinfo=IST))
                    if now >= today_630 and expires_at < today_630:
                        return {"exists": True, "valid": False, "message": "Token expired at 6:30 AM IST today", "expires_at": expires_at_str, "source": "file"}
                    
                    # Also check the actual expiry time
                    if now >= expires_at:
                        return {"exists": True, "valid": False, "message": "Token expired", "expires_at": expires_at_str, "source": "file"}
                
                return {
                    "exists": True, 
                    "valid": True, 
                    "message": "Token valid", 
                    "expires_at": expires_at_str,
                    "token_preview": access_token[:10] + "..." if len(access_token) > 10 else access_token,
                    "source": "file"
                }
        
        # Fallback to database
        from app.api.v1.endpoints.fyers_auth import get_fyers_token_from_db
        db_token = get_fyers_token_from_db()
        if db_token:
            access_token = db_token.get("access_token", "")
            if access_token:
                created_at_str = db_token.get("created_at")
                expires_in = db_token.get("expires_in", 86400)
                if created_at_str:
                    created_at = datetime.fromisoformat(created_at_str)
                    # Ensure timezone-aware
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=IST)
                    else:
                        created_at = created_at.astimezone(IST)
                    expires_at = created_at + timedelta(seconds=expires_in)
                    now = now_ist()
                    
                    today_630 = datetime.combine(now.date(), time(6, 30, tzinfo=IST))
                    if now >= today_630 and expires_at < today_630:
                        return {"exists": True, "valid": False, "message": "Token expired at 6:30 AM IST today", "expires_at": expires_at.isoformat(), "source": "database"}
                    elif now >= expires_at:
                        return {"exists": True, "valid": False, "message": "Token expired", "expires_at": expires_at.isoformat(), "source": "database"}
                
                return {
                    "exists": True,
                    "valid": True,
                    "message": "Token valid",
                    "expires_at": expires_at.isoformat() if created_at_str else None,
                    "token_preview": access_token[:10] + "..." if len(access_token) > 10 else access_token,
                    "source": "database"
                }
        
        return {"exists": False, "valid": False, "message": "Token not found in file or database"}
    except Exception as e:
        return {"exists": True, "valid": False, "message": f"Error reading token: {e}"}