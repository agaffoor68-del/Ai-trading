"""
Phase 1: Fyers API v3 OAuth2 Authentication Endpoints

Non-Negotiable Rule: Fyers API v3 is the ONLY data source.
This module handles the daily OAuth2 flow to generate access tokens.
"""

import logging
import os
import traceback
import aiohttp
from fastapi import APIRouter, Request, Response

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["fyers-auth"])


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

        redirect_uri = settings.FYERS_REDIRECT_URI
        response_type = "code"
        state = os.getenv("FYERS_STATE", "trading_platform_state")

        # Fyers v3 authorization URL
        auth_url = (
            f"{settings.FYERS_API_BASE}/v3/authorize?"
            f"client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type={response_type}"
            f"&state={state}"
            f"&code_challenge={os.getenv('FYERS_CODE_CHALLENGE', '')}"
            f"&code_challenge_method=S256"
        )

        logger.info(f"Fyers auth URL generated for client: {client_id[:4]}***")
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
        token_payload = {
            "client_id": settings.FYERS_CLIENT_ID,
            "client_secret": settings.FYERS_CLIENT_SECRET,
            "redirect_uri": settings.FYERS_REDIRECT_URI,
            "grant_type": "authorization_code",
            "code": code,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{settings.FYERS_API_BASE}/v3/token",
                json=token_payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                token_response = await resp.json()
                status = resp.status

        if status != 200:
            logger.error(f"Fyers token exchange failed: {token_response}")
            return Response(
                content=f"Fyers token exchange failed: {token_response}",
                status_code=400,
            )

        access_token = token_response.get("access_token")
        if not access_token:
            logger.error("Fyers token response: no access_token returned")
            return Response(content="No access token in Fyers response", status_code=400)

        logger.info(f"Fyers OAuth2 successful for client: {settings.FYERS_CLIENT_ID[:4]}***")
        return {
            "status": "success",
            "access_token": access_token,
            "expires_in": token_response.get("expires_in", 86400),
            "token_type": token_response.get("token_type", "Bearer"),
            "message": "Store this access token securely - required for all Fyers API calls",
        }

    except aiohttp.ClientError as e:
        logger.error(f"Fyers callback network error: {str(e)}")
        logger.error(traceback.format_exc())
        return Response(content="Network error while contacting Fyers API", status_code=502)
    except Exception as e:
        logger.error(f"Fyers callback unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        return Response(content="Internal server error in Fyers callback", status_code=500)