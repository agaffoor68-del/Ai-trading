"""
Phase 1: Fyers API v3 OAuth2 Authentication Endpoints

Non-Negotiable Rule: Fyers API v3 is the ONLY data source.
This module handles the daily OAuth2 flow to generate access tokens.
"""

import logging
import os
import traceback
import hashlib
import aiohttp
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.models import FyersToken

logger = logging.getLogger(__name__)

router = APIRouter(tags=["fyers-auth"])


def generate_app_id_hash(client_id: str, client_secret: str) -> str:
    """Generate SHA-256 hash of 'client_id:client_secret' for Fyers appIdHash."""
    return hashlib.sha256(f"{client_id}:{client_secret}".encode()).hexdigest()


def save_fyers_token_to_db(access_token: str, expires_in: int, refresh_token: str = "") -> bool:
    """Save Fyers access token to PostgreSQL database for persistence across restarts."""
    try:
        db = SessionLocal()
        # Delete old tokens
        db.query(FyersToken).delete()
        # Create new token record
        token_record = FyersToken(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in
        )
        db.add(token_record)
        db.commit()
        db.close()
        return True
    except Exception as e:
        logger.error(f"Failed to save Fyers token to database: {str(e)}")
        return False


def get_fyers_token_from_db() -> dict:
    """Get the latest Fyers token from database."""
    try:
        db = SessionLocal()
        token = db.query(FyersToken).order_by(FyersToken.created_at.desc()).first()
        db.close()
        if token:
            return {
                "access_token": token.access_token,
                "refresh_token": token.refresh_token,
                "expires_in": token.expires_in,
                "created_at": token.created_at.isoformat() if token.created_at else None
            }
        return {}
    except Exception as e:
        logger.error(f"Failed to get Fyers token from database: {str(e)}")
        return {}


@router.get("/login")
async def fyers_login():
    """
    Initiate Fyers OAuth2 flow.
    Redirects user to Fyers authorization URL to generate daily access token.
    """
    try:
        client_id = settings.FYERS_CLIENT_ID
        if not client_id:
            logger.error("FYERS_CLIENT_ID environment variable not set")
            return Response(
                content="Configuration error: FYERS_CLIENT_ID missing",
                status_code=500,
            )

        # Ensure redirect_uri matches Fyers Dashboard exactly
        redirect_uri = settings.FYERS_REDIRECT_URI
        if not redirect_uri:
            logger.error("FYERS_REDIRECT_URI not configured")
            return Response(
                content="Configuration error: FYERS_REDIRECT_URI missing",
                status_code=500,
            )
        
        response_type = "code"
        state = os.getenv("FYERS_STATE", "trading_platform_state")

        # Fyers v3 authorization URL
        fyers_login_url = (
            f"{settings.FYERS_API_BASE}/v3/generate-authcode?"
            f"client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&state={state}"
        )

        logger.info(f"Fyers auth URL generated for client: {client_id[:4]}***")
        logger.info(f"Redirect URI: {redirect_uri}")
        return RedirectResponse(url=fyers_login_url)

    except Exception as e:
        logger.error(f"Fyers login endpoint error: {str(e)}")
        logger.error(traceback.format_exc())
        return Response(content="Internal server error during Fyers login", status_code=500)


@router.get("/callback")
async def fyers_callback(request: Request):
    """
    Handle Fyers OAuth2 callback using official fyers_apiv3 SDK.
    Exchanges authorization code for access token.
    Route: /api/v1/fyers/callback (matches Fyers Dashboard redirect URL)
    """
    try:
        # Fyers sends query params, not form data
        # Fyers sends: ?s=ok&code=200&auth_code=eyJhbGci...
        # We need to extract auth_code, not code
        auth_code = request.query_params.get("auth_code")
        state = request.query_params.get("state")
        
        logger.info(f"Fyers callback received - auth_code: {'present' if auth_code else 'missing'}, state: {'present' if state else 'missing'}")
        
        if not auth_code:
            logger.error("Fyers callback: auth_code missing")
            # Auto-redirect to login if auth_code is missing
            return RedirectResponse(url="/api/v1/fyers/login")

        if not state:
            logger.error("Fyers callback: state parameter missing")
            # Auto-redirect to login if state is missing
            return RedirectResponse(url="/api/v1/fyers/login")
        
        # Use official fyers_apiv3 SDK for token exchange
        try:
            from fyers_apiv3 import fyersModel
        except ImportError:
            logger.error("fyers_apiv3 SDK not installed. Please add 'fyers-apiv3' to requirements.txt")
            raise HTTPException(status_code=500, detail="Fyers SDK missing")
        
        # Generate correct appIdHash per Fyers spec:
        # appIdHash = SHA-256(client_id + ":" + secret_key)
        # Ensure client_id has -100 suffix and both values are stripped
        app_id = settings.FYERS_CLIENT_ID.strip()
        secret = settings.FYERS_CLIENT_SECRET.strip()
        if not app_id.endswith("-100"):
            app_id = app_id + "-100"
        app_id_hash = hashlib.sha256(f"{app_id}:{secret}".encode()).hexdigest()
        logger.info(f"Generated appIdHash: {app_id_hash[:20]}... for app_id: {app_id[:4]}***")
        
        # Create session using official SDK with correct appIdHash
        session = fyersModel.SessionModel(
            client_id=app_id,  # Use app_id with -100 suffix
            secret_key=secret,
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
        
        logger.info(f"Fyers token response: {response}")
        
        # Check for errors in response
        if isinstance(response, dict) and response.get("code") != 200:
            fyers_error_code = response.get("code")
            fyers_error_message = response.get("message", "Unknown error")
            logger.error(f"Fyers token exchange failed - Code: {fyers_error_code}, Message: {fyers_error_message}")
            
            # Handle specific error codes
            if fyers_error_code == -437:
                return _fyers_error_page(
                    "Session Expired",
                    "Auth code expired or already used. Please generate a new login link and try again immediately.",
                    "⚠️"
                )
            elif fyers_error_code == -16:
                return _fyers_error_page(
                    "Invalid Configuration",
                    "App ID hash is invalid. Please check your Fyers Client ID and Secret.",
                    "❌"
                )
            else:
                return _fyers_error_page(
                    "Login Failed",
                    f"Error: {fyers_error_message} (Code: {fyers_error_code})",
                    "❌"
                )
        
        # Extract access token from response
        access_token = None
        if isinstance(response, dict):
            # Handle different response formats from SDK
            if "access_token" in response:
                access_token = response["access_token"]
            elif "data" in response and isinstance(response["data"], dict):
                access_token = response["data"].get("access_token")
        
        if not access_token:
            logger.error(f"Fyers token response: no access_token returned. Response: {response}")
            return _fyers_error_page(
                "Login Failed",
                "No access token in Fyers response. Please try again.",
                "❌"
            )
        
        refresh_token = response.get("refresh_token", "") if isinstance(response, dict) else ""
        expires_in = response.get("expires_in", 86400) if isinstance(response, dict) else 86400
        
        # Save token to PostgreSQL database for persistence across restarts
        saved = save_fyers_token_to_db(access_token, expires_in, refresh_token)
        if not saved:
            logger.error("Failed to save Fyers token to database")
        
        # Also update in-memory settings for immediate use
        settings.FYERS_ACCESS_TOKEN = access_token
        logger.info(f"Fyers access token saved to database and settings (length: {len(access_token)})")
        
        logger.info(f"Fyers OAuth2 successful for client: {settings.FYERS_CLIENT_ID[:4]}***")
        return {
            "status": "success",
            "access_token": access_token,
            "expires_in": expires_in,
            "token_type": response.get("token_type", "Bearer") if isinstance(response, dict) else "Bearer",
            "message": "Access token saved. Fyers API is now authenticated.",
        }
    
    except aiohttp.ClientError as e:
        logger.error(f"Fyers callback network error: {str(e)}")
        logger.error(traceback.format_exc())
        return Response(content="Network error while contacting Fyers API", status_code=502)
    except Exception as e:
        logger.error(f"Fyers callback unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        return Response(content="Internal server error in Fyers callback", status_code=500)


def _fyers_error_page(title: str, message: str, icon: str) -> Response:
    """Generate a user-friendly HTML error page with auto-redirect."""
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Fyers Login - {title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #0a0a0a; color: #fff; }}
        .error-box {{ background: #1a1a1a; border: 1px solid #ff6b35; color: #fff; padding: 30px; border-radius: 12px; max-width: 500px; margin: 0 auto; box-shadow: 0 0 20px rgba(255, 107, 53, 0.2); }}
        .button {{ display: inline-block; margin-top: 20px; padding: 12px 24px; background: linear-gradient(135deg, #ff6b35, #f7931a); color: #000; text-decoration: none; border-radius: 8px; font-weight: 600; }}
    </style>
    <script>
        setTimeout(() => {{
            window.location.href = '/api/v1/fyers/login';
        }}, 5000);
    </script>
</head>
<body>
    <div class="error-box">
        <h2>{icon} {title}</h2>
        <p>{message}</p>
        <p style="font-size: 0.9em; color: #888; margin-top: 10px;">Redirecting automatically in 5 seconds...</p>
        <a href="/api/v1/fyers/login" class="button">Try Again</a>
    </div>
</body>
</html>"""
    return Response(content=html_content, status_code=400, media_type="text/html")


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
async def fyers_logout():
    """
    Clear Fyers token (logout).
    """
    try:
        db = SessionLocal()
        db.query(FyersToken).delete()
        db.commit()
        db.close()
        settings.FYERS_ACCESS_TOKEN = ""
        return {"status": "success", "message": "Fyers token cleared"}
    except Exception as e:
        logger.error(f"Failed to clear Fyers token: {str(e)}")
        return {"status": "error", "message": "Failed to clear token"}
