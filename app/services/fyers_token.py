"""
Fyers Token Storage Utility

Persists Fyers access token to a JSON file for persistence across restarts.
"""

import json
import logging
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

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
        
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        token_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.now().isoformat(),
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
        if not TOKEN_FILE.exists():
            logger.warning("Fyers token file does not exist")
            return None
        
        with open(TOKEN_FILE, "r") as f:
            token_data = json.load(f)
        
        access_token = token_data.get("access_token", "")
        if not access_token:
            logger.warning("Fyers token file exists but access_token is empty")
            return None
        
        # Check expiry
        expires_at_str = token_data.get("expires_at")
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str)
            if datetime.now() >= expires_at:
                logger.warning("Fyers access token has expired")
                return None
        
        logger.info(f"Fyers token loaded from {TOKEN_FILE} (valid)")
        return access_token
        
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
        if not TOKEN_FILE.exists():
            return {"exists": False, "valid": False, "message": "Token file not found"}
        
        with open(TOKEN_FILE, "r") as f:
            token_data = json.load(f)
        
        access_token = token_data.get("access_token", "")
        expires_at_str = token_data.get("expires_at")
        
        if not access_token:
            return {"exists": True, "valid": False, "message": "Token file exists but empty"}
        
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str)
            if datetime.now() >= expires_at:
                return {"exists": True, "valid": False, "message": "Token expired", "expires_at": expires_at_str}
        
        return {
            "exists": True, 
            "valid": True, 
            "message": "Token valid", 
            "expires_at": expires_at_str,
            "token_preview": access_token[:10] + "..." if len(access_token) > 10 else access_token
        }
    except Exception as e:
        return {"exists": True, "valid": False, "message": f"Error reading token: {e}"}