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
from fastapi import APIRouter, Request, Response

from app.core.config import settings
from app.services.fyers_token import save_fyers_token, get_fyers_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["fyers-auth"])


def generate_app_id_hash(client_id: str, client_secret: str) -> str:
    """Generate SHA-256 hash of 'client_id:client_secret' for Fyers appIdHash."""
    return hashlib.sha256(f"{client_id}:{client_secret}".encode()).hexdigest()


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
        auth_url = (
            f"{settings.FYERS_API_BASE}/v3/generate-authcode?"
            f"client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&state={state}"
        )

        logger.info(f"Fyers auth URL generated for client: {client_id[:4]}***")
        logger.info(f"Redirect URI: {redirect_uri}")
        return {
            "authorization_url": auth_url,
            "state": state,
            "client_id": client_id[:4] + "***",
            "message": "Complete the OAuth2 flow and exchange the code for an access token",
        }

    except Exception as e:
        logger.error(f"Fyers login endpoint error: {str(e)}")
        logger.error(traceback.format_exc())
        return Response(content="Internal server error during Fyers login", status_code=500)


@router.get("/callback")
async def fyers_callback(request: Request):
    """
    Handle Fyers OAuth2 callback.
    Exchanges authorization code for access token.
    Route: /api/v1/fyers/callback (matches Fyers Dashboard redirect URL)
    """
    try:
        # Fyers sends query params, not form data
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        
        logger.info(f"Fyers callback received - code: {'present' if code else 'missing'}, state: {'present' if state else 'missing'}")

        if not code:
            logger.error("Fyers callback: authorization code missing")
            return Response(content="Authorization code missing", status_code=400)

        if not state:
            logger.error("Fyers callback: state parameter missing")
            return Response(content="State parameter missing", status_code=400)

        # Exchange authorization code for access token
        # Use exact redirect_uri from Fyers Dashboard
        redirect_uri = "https://ai-trading-9qoa.onrender.com/api/v1/fyers/callback"
        
        # Generate appIdHash as per Fyers v3 API spec
        app_id = settings.FYERS_CLIENT_ID
        app_secret = settings.FYERS_CLIENT_SECRET
        app_id_hash = generate_app_id_hash(app_id, app_secret)
        
        logger.info(f"Fyers Client ID (full): {app_id}")
        logger.info(f"Fyers Client ID suffix: {app_id[-4:] if len(app_id) > 4 else 'N/A'}")
        logger.info(f"Generated appIdHash: {app_id_hash}")
        logger.info(f"appIdHash (first 20): {app_id_hash[:20]}...")
        
        token_payload = {
            "grant_type": "authorization_code",
            "appIdHash": app_id_hash,
            "code": code,
        }
        
        logger.info(f"Sending token exchange to Fyers: {settings.FYERS_API_BASE}/v3/validate-authcode")
        logger.info(f"Payload: grant_type=authorization_code, appIdHash={app_id_hash[:20]}..., code={code[:10]}...")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{settings.FYERS_API_BASE}/v3/validate-authcode",
                json=token_payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                token_response = await resp.json()
                status = resp.status
                raw_response = await resp.text()

        logger.info(f"Raw Fyers response: {raw_response}")

        if status != 200:
            logger.error(f"Fyers token exchange failed: {token_response}")
            
            # Check for specific -437 error: invalid auth code (single-use, expires quickly)
            if token_response.get("code") == -437:
                html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Fyers Login Failed</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
        .error-box { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; padding: 20px; border-radius: 8; max-width: 500px; margin: 0 auto; }
        .button { display: inline-block; margin-top: 20px; padding: 10px 20px; background: #dc3545; color: white; text-decoration: none; border-radius: 4; }
    </style>
</head>
<body>
    <div class="error-box">
        <h2>Fyers Login Failed</h2>
        <p>Auth code expired or already used. Please generate a new login link and try again immediately.</p>
        <a href="/api/v1/fyers/login" class="button">Generate New Login Link</a>
    </div>
</body>
</html>"""
                return Response(content=html_content, status_code=400, media_type="text/html")

        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token", "")
        expires_in = token_response.get("expires_in", 86400)
        
        if not access_token:
            logger.error("Fyers token response: no access_token returned")
            return Response(content="No access token in Fyers response", status_code=400)

        # Save token to persistent storage (JSON file)
        saved = save_fyers_token(access_token, expires_in, refresh_token)
        if not saved:
            logger.error("Failed to save Fyers token to storage")
        
        # Also update in-memory settings for immediate use
        settings.FYERS_ACCESS_TOKEN = access_token
        logger.info(f"Fyers access token saved to storage and settings (length: {len(access_token)})")

        logger.info(f"Fyers OAuth2 successful for client: {settings.FYERS_CLIENT_ID[:4]}***")
        return {
            "status": "success",
            "access_token": access_token,
            "expires_in": expires_in,
            "token_type": token_response.get("token_type", "Bearer"),
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


@router.get("/token-status")
async def fyers_token_status():
    """
    Check current Fyers token status.
    """
    from app.services.fyers_token import get_fyers_token_status
    
    status = get_fyers_token_status()
    return status


@router.post("/logout")
async def fyers_logout():
    """
    Clear Fyers token (logout).
    """
    from app.services.fyers_token import clear_fyers_token
    
    cleared = clear_fyers_token()
    if cleared:
        settings.FYERS_ACCESS_TOKEN = ""
        return {"status": "success", "message": "Fyers token cleared"}
    
    return {"status": "error", "message": "Failed to clear token"}