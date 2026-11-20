"""
Phase 1: Fyers API v3 OAuth2 Authentication Endpoints

Non-Negotiable Rule: Fyers API v3 is the ONLY data source.
This module handles the daily OAuth2 flow to generate access tokens.
"""

import logging
import traceback
import hashlib
from app.services.fyers_api import fyers_api_client
import secrets
from datetime import timedelta
from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.models import FyersToken
from app.core.auth import require_admin
from app.core.datetime_utils import now_ist
from app.services.fyers_token import save_fyers_token, clear_fyers_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["fyers-auth"])

# Fernet encryption for secrets at rest
_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = settings.TOKEN_ENCRYPTION_KEY
        if not key:
            raise RuntimeError("TOKEN_ENCRYPTION_KEY not set in environment")
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def _encrypt(data: str) -> str:
    return _get_fernet().encrypt(data.encode()).decode()


def _decrypt(data: str) -> str:
    return _get_fernet().decrypt(data.encode()).decode()


def generate_app_id_hash(client_id: str, client_secret: str) -> str:
    """Generate SHA-256 hash of 'client_id:client_secret' for Fyers appIdHash."""
    return hashlib.sha256(f"{client_id}:{client_secret}".encode()).hexdigest()


def save_fyers_token_to_db(access_token: str, expires_in: int, refresh_token: str = "", client_id: str = "", client_secret: str = "") -> bool:
    """Save Fyers access token (and OAuth credentials) to PostgreSQL for persistence across restarts."""
    try:
        encrypted_access = _encrypt(access_token)
        encrypted_refresh = _encrypt(refresh_token) if refresh_token else ""
        encrypted_client_id = _encrypt(client_id) if client_id else ""
        encrypted_client_secret = _encrypt(client_secret) if client_secret else ""
        token_record = FyersToken(
            access_token=encrypted_access,
            refresh_token=encrypted_refresh,
            client_id=encrypted_client_id,
            client_secret=encrypted_client_secret,
            expires_in=expires_in
        )
        with SessionLocal() as db:
            try:
                db.query(FyersToken).delete()
                db.add(token_record)
                db.commit()
            except Exception:
                db.rollback()
                raise
        return True
    except Exception as e:
        logger.error("DB Error saving Fyers token: %s (%s)", str(e), type(e).__name__, exc_info=True)
        return False


def get_fyers_token_from_db() -> dict:
    """Get the latest Fyers token from database (decrypted)."""
    try:
        with SessionLocal() as db:
            token = db.query(FyersToken).order_by(FyersToken.created_at.desc()).first()
        if token:
            return {
                "access_token": _decrypt(token.access_token) if token.access_token else "",
                "refresh_token": _decrypt(token.refresh_token) if token.refresh_token else "",
                "client_id": _decrypt(token.client_id) if token.client_id else "",
                "client_secret": _decrypt(token.client_secret) if token.client_secret else "",
                "expires_in": token.expires_in,
                "created_at": token.created_at.isoformat() if token.created_at else None
            }
        return {}
    except InvalidToken:
        logger.exception(
            "Fyers token decryption failed (InvalidToken): stored token is corrupt or "
            "TOKEN_ENCRYPTION_KEY does not match the key used to save it. "
            "Keep the key stable across deployments and log in to Fyers again."
        )
        return {}
    except Exception as e:
        logger.error("DB Error loading Fyers token: %s (%s)", str(e), type(e).__name__, exc_info=True)
        return {}


def restore_fyers_credentials() -> bool:
    """Restore FYERS_CLIENT_ID / FYERS_CLIENT_SECRET into settings from the stored token row.

    The OAuth callback persists credentials encrypted in PostgreSQL; on boot we
    rehydrate the in-memory settings so the WebSocket and profile API work after
    a restart without re-login. Returns True when a client_id was restored.
    """
    try:
        db_token = get_fyers_token_from_db()
        client_id = db_token.get("client_id", "")
        if not client_id:
            return False
        if not settings.FYERS_CLIENT_ID:
            settings.FYERS_CLIENT_ID = client_id
        if db_token.get("client_secret") and not settings.FYERS_CLIENT_SECRET:
            settings.FYERS_CLIENT_SECRET = db_token["client_secret"]
        logger.info("Restored Fyers client_id from database storage")
        return True
    except Exception as e:
        logger.warning("Could not restore Fyers credentials from database: %s", e)
        return False


class FyersConnectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    client_id: str = Field(min_length=1)
    client_secret: str = Field(min_length=1)


@router.post("/connect")
async def fyers_connect(
    payload: FyersConnectRequest,
    current_user=Depends(require_admin),
):
    """
    Initiate Fyers OAuth2 flow.

    Takes client_id and client_secret in a JSON body, saves them encrypted,
    creates a random state, and returns the Fyers login URL. The frontend then
    redirects the browser to Fyers. Fyers sends auth_code to /callback, where
    it is exchanged for an access token; auth_code is not accepted by /connect.

    Admin only endpoint.
    """
    try:
        client_id = payload.client_id
        client_secret = payload.client_secret

        if not client_id or not client_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="client_id and client_secret are required"
            )
        
        # Save credentials encrypted (for later use in callback)
        # Note: In production, you might want to store these in a separate credentials table
        encrypted_id = _encrypt(client_id)
        encrypted_secret = _encrypt(client_secret)
        
        # Store temporarily in database for callback validation
        db = SessionLocal()
        try:
            # Save credentials to a temp table or use existing mechanism
            # For now, we'll use the settings in-memory (they should come from env)
            pass
        finally:
            db.close()
        
        # Generate random state for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Save state to validate in callback
        db = SessionLocal()
        try:
            # Store state with expiry (5 minutes)
            # We'll use a simple approach - store in a key-value manner
            # For production, consider a proper OAuth state table
            stmt = text("""
                CREATE TABLE IF NOT EXISTS oauth_states (
                    state VARCHAR(255) PRIMARY KEY,
                    client_id_enc VARCHAR(255) NOT NULL,
                    client_secret_enc VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
                )
            """)
            db.execute(stmt)
            
            expires_at = now_ist() + timedelta(minutes=5)
            stmt = text("""
                INSERT INTO oauth_states (state, client_id_enc, client_secret_enc, expires_at)
                VALUES (:state, :client_id, :client_secret, :expires_at)
                ON CONFLICT (state) DO UPDATE SET 
                    client_id_enc = EXCLUDED.client_id_enc,
                    client_secret_enc = EXCLUDED.client_secret_enc,
                    expires_at = EXCLUDED.expires_at
            """)
            db.execute(stmt, {
                "state": state,
                "client_id": encrypted_id,
                "client_secret": encrypted_secret,
                "expires_at": expires_at
            })
            db.commit()
        finally:
            db.close()
        
        # Build Fyers authorization URL
        redirect_uri = settings.FYERS_REDIRECT_URI
        if not redirect_uri:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="FYERS_REDIRECT_URI not configured"
            )
        
        fyers_login_url = (
            f"https://api-t1.fyers.in/api/v3/generate-authcode?"
            f"client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&state={state}"
        )

        logger.info(f"Fyers auth URL generated for client: {client_id[:4]}***")
        logger.info(f"Redirect URI: {redirect_uri}")
        return {"auth_url": fyers_login_url, "state": state}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fyers connect endpoint error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error during Fyers connect")


@router.get("/callback")
async def fyers_callback(request: Request):
    """
    Handle Fyers OAuth2 callback.
    
    Exchanges authorization code for access token.
    Route: /api/v1/fyers/callback (matches Fyers Dashboard redirect URL)
    """
    try:
        auth_code = request.query_params.get("auth_code")
        state = request.query_params.get("state")
        
        logger.info(f"Fyers callback received - auth_code: {'present' if auth_code else 'missing'}, state: {'present' if state else 'missing'}")
        
        if not auth_code:
            logger.error("Fyers callback: auth_code missing")
            frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
            return RedirectResponse(url=f"{frontend_url}/settings?fyers=failed&reason=missing_auth_code")
        
        if not state:
            logger.error("Fyers callback: state parameter missing")
            frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
            return RedirectResponse(url=f"{frontend_url}/settings?fyers=failed&reason=missing_state")
        
        # Validate state and retrieve credentials
        db = SessionLocal()
        client_id = None
        client_secret = None
        try:
            from sqlalchemy import text
            stmt = text("""
                SELECT client_id_enc, client_secret_enc 
                FROM oauth_states 
                WHERE state = :state AND expires_at > NOW()
            """)
            result = db.execute(stmt, {"state": state}).fetchone()
            if not result:
                logger.error("Fyers callback: invalid or expired state")
                frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
                return RedirectResponse(url=f"{frontend_url}/settings?fyers=failed&reason=invalid_state")
            
            client_id = _decrypt(result[0])
            client_secret = _decrypt(result[1])
            
            # Delete used state
            stmt = text("DELETE FROM oauth_states WHERE state = :state")
            db.execute(stmt, {"state": state})
            db.commit()
        finally:
            db.close()
        
        if not client_id or not client_secret:
            logger.error("Fyers callback: failed to retrieve credentials")
            frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
            return RedirectResponse(url=f"{frontend_url}/settings?fyers=failed&reason=credential_error")
        
        # Exchange code for token using official fyers_apiv3 SDK
        try:
            from fyers_apiv3 import fyersModel
        except ImportError:
            logger.error("fyers_apiv3 SDK not installed. Please add 'fyers-apiv3' to requirements.txt")
            frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
            return RedirectResponse(url=f"{frontend_url}/settings?fyers=failed&reason=sdk_missing")
        
        # Generate correct appIdHash per Fyers spec:
        # appIdHash = SHA-256(app_id + ":" + app_secret) - EXACT match required
        app_id_hash = hashlib.sha256(f"{client_id}:{client_secret}".encode()).hexdigest()
        logger.info(f"Generated appIdHash: {app_id_hash} for app_id: {client_id[:4]}***")
        
        # Create session using official SDK with correct appIdHash
        session = fyersModel.SessionModel(
            client_id=client_id,
            secret_key=client_secret,
            redirect_uri=settings.FYERS_REDIRECT_URI,
            response_type="code",
            grant_type="authorization_code"
        )
        
        # Set the appIdHash manually (SDK may not generate it correctly)
        session.appIdHash = app_id_hash
        
        # Set the auth_code received from Fyers
        session.set_token(auth_code)
        
        # Generate token using official SDK (handles appIdHash internally)
        response = session.generate_token()
        
        logger.info("Fyers token exchange completed (code: %s)", response.get("code") if isinstance(response, dict) else None)
        
        # Check for errors in response
        if isinstance(response, dict) and response.get("code") != 200:
            fyers_error_code = response.get("code")
            fyers_error_message = response.get("message", "Unknown error")
            logger.error(f"Fyers token exchange failed - Code: {fyers_error_code}, Message: {fyers_error_message}")
            
            frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
            if fyers_error_code == -437:
                return RedirectResponse(url=f"{frontend_url}/settings?fyers=failed&reason=expired_code")
            elif fyers_error_code == -16:
                return RedirectResponse(url=f"{frontend_url}/settings?fyers=failed&reason=invalid_config")
            else:
                return RedirectResponse(url=f"{frontend_url}/settings?fyers=failed&reason={fyers_error_message}")
        
        # Extract access token from response
        access_token = None
        if isinstance(response, dict):
            # Handle different response formats from SDK
            if "access_token" in response:
                access_token = response["access_token"]
            elif "data" in response and isinstance(response["data"], dict):
                access_token = response["data"].get("access_token")
        
        if not access_token:
            logger.error("Fyers token response: no access_token returned")
            frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
            return RedirectResponse(url=f"{frontend_url}/settings?fyers=failed&reason=no_token")
        
        refresh_token = response.get("refresh_token", "") if isinstance(response, dict) else ""
        expires_in = response.get("expires_in", 86400) if isinstance(response, dict) else 86400
        
        # Save token to PostgreSQL database for persistence across restarts
        saved = save_fyers_token_to_db(access_token, expires_in, refresh_token, client_id, client_secret)
        if not saved:
            logger.error("Failed to save Fyers token to database")
            frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
            return RedirectResponse(url=f"{frontend_url}/settings?fyers=failed&reason=token_storage_error")
        
        # Also save to file for fyers_token.py utility
        if not save_fyers_token(access_token, expires_in, refresh_token):
            logger.warning("Fyers token file cache unavailable; token persisted in PostgreSQL")
        
        # Also update in-memory settings for immediate use
        settings.FYERS_ACCESS_TOKEN = access_token
        settings.FYERS_CLIENT_ID = client_id
        settings.FYERS_CLIENT_SECRET = client_secret
        logger.info("Fyers access token committed to PostgreSQL and loaded into settings")
        
        logger.info(f"Fyers OAuth2 successful for client: {client_id[:4]}***")
        frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
        return RedirectResponse(url=f"{frontend_url}/settings?fyers=connected")
    
    except aiohttp.ClientError as e:
        logger.error(f"Fyers callback network error: {str(e)}")
        logger.error(traceback.format_exc())
        frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
        return RedirectResponse(url=f"{frontend_url}/settings?fyers=failed&reason=network_error")
    except Exception as e:
        logger.error(f"Fyers callback unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        frontend_url = settings.FRONTEND_URL or "http://localhost:3000"
        return RedirectResponse(url=f"{frontend_url}/settings?fyers=failed&reason=unexpected_error")


@router.get("/token-status")
async def fyers_token_status():
    """
    Check current Fyers token status from database.
    """
    status = get_fyers_token_from_db()
    if status:
        return {"status": "success", "data": status}
    return {"status": "error", "message": "No token found"}


@router.post("/logout")
async def fyers_logout(current_user=Depends(require_admin)):
    """
    Clear Fyers token (logout).
    Admin only.
    """
    try:
        db = SessionLocal()
        db.query(FyersToken).delete()
        db.commit()
        db.close()
        settings.FYERS_ACCESS_TOKEN = None
        clear_fyers_token()
        return {"status": "success", "message": "Fyers token cleared"}
    except Exception as e:
        logger.error(f"Failed to clear Fyers token: {str(e)}")
        return {"status": "error", "message": "Failed to clear token"}


@router.get("/status")
async def fyers_status():
    """
    Validate Fyers token by calling Fyers profile API.
    Returns real connection status with token expiry info.
    """
    from app.services.fyers_token import get_fyers_token, get_fyers_token_status
    
    # Get token from storage
    token = get_fyers_token()
    
    if not token:
        return {
            "connected": False,
            "valid": False,
            "message": "No Fyers token found. Please login.",
            "token_expires_at": None,
            "profile": None
        }
    
    # Check token expiry (Fyers tokens expire at 6:30 AM IST daily)
    try:
        token_status = get_fyers_token_status()
        
        if not token_status.get("valid", False):
            return {
                "connected": False,
                "valid": False,
                "message": token_status.get("message", "Token expired"),
                "token_expires_at": token_status.get("expires_at"),
                "profile": None
            }
    except Exception as e:
        logger.warning(f"Could not check token expiry: {e}")
    
    # Validate token by calling Fyers profile API
    try:
        # Use the fyers_api_client to make a profile call
        profile = await _get_fyers_profile(token)
        
        if profile:
            return {
                "connected": True,
                "valid": True,
                "message": "Fyers connected and token valid",
                "token_expires_at": token_status.get("expires_at") if 'token_status' in locals() else None,
                "profile": {
                    "name": profile.get("name"),
                    "email": profile.get("email"),
                    "client_id": profile.get("fy_id") or profile.get("client_id"),
                    "pan": profile.get("pan"),
                }
            }
        else:
            return {
                "connected": False,
                "valid": False,
                "message": "Token validation failed - invalid response from Fyers",
                "token_expires_at": None,
                "profile": None
            }
    except Exception as e:
        logger.error(f"Fyers profile validation failed: {e}")
        return {
            "connected": False,
            "valid": False,
            "message": f"Token validation error: {str(e)}",
            "token_expires_at": None,
            "profile": None
        }


async def _get_fyers_profile(access_token: str) -> dict:
    """Call the shared, Redis-cached Fyers profile client."""
    return await fyers_api_client.get_profile(access_token)
