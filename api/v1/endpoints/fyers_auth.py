"""
Fyers OAuth2 Authentication Endpoints Module 1

Provides Fyers OAuth2 flow for access token generation.
Endpoints: /login, /callback
"""

import logging
import os
import aiohttp
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/fyers", tags=["fyers-auth"])


@router.get("/login")
async def fyers_login():
    """
    Initiate Fyers OAuth2 flow.
    Redirects user to Fyers authorization URL.
    """
    try:
        client_id = os.getenv("FYERS_CLIENT_ID")
        if not client_id:
            logger.error("FYERS_CLIENT_ID environment variable not set")
            return Response(content="Configuration error: FYERS_CLIENT_ID missing", status_code=500)

        redirect_uri = os.getenv("FYERS_REDIRECT_URI", "http://localhost:8000/api/v1/fiers/callback")
        response_type = "code"
        state = os.getenv("FYERS_STATE", "trading_platform_state")

        # Fyers v3 authorization URL
        auth_url = (
            f"https://api.fyers.in/v3/authorize?"
            f"client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type={response_type}"
            f"&state={state}"
            f"&code_challenge={os.getenv('FYERS_CODE_CHALLENGE', '')}"
            f"&code_challenge_method=S256"
        )

        logger.info(f"Fyers auth URL generated for client: {client_id[:4]}***")
        return RedirectResponse(url=auth_url)

    except Exception as e:
        logger.error(f"Fyers login endpoint error: {str(e)}")
        return Response(content="Internal server error during Fyers login", status_code=500)


@router.post("/callback")
async def fyers_callback(request: Request):
    """
    Handle Fyers OAuth2 callback.
    Exchanges authorization code for access token.
    """
    try:
        # Parse the callback query parameters
        form_data = await request.form()
        code = form_data.get("code")
        state = form_data.get("state")

        if not code:
            logger.error("Fyers callback: authorization code missing")
            return Response(content="Authorization code missing", status_code=400)

        if not state:
            logger.error("Fyers callback: state parameter missing")
            return Response(content="State parameter missing", status_code=400)

        # Exchange authorization code for access token
        token_payload = {
            "client_id": os.getenv("FYERS_CLIENT_ID"),
            "client_secret": os.getenv("FYERS_CLIENT_SECRET"),
            "redirect_uri": os.getenv("FYERS_REDIRECT_URI", "http://localhost:8000/api/v1/fiers/callback"),
            "grant_type": "authorization_code",
            "code": code,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.fyers.in/v3/token",
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

        # TODO: Store access_token securely (encrypted in DB, Redis, etc.)
        # TODO: Refresh token handling for next day's session

        logger.info(f"Fyers OAuth2 successful. Token acquired for client: {os.getenv('FYERS_CLIENT_ID', '')[:4]}***")
        return {
            "status": "success",
            "access_token": access_token,
            "expires_in": token_response.get("expires_in", 86400),
            "token_type": token_response.get("token_type", "Bearer"),
        }

    except aiohttp.ClientError as e:
        logger.error(f"Fyers callback network error: {str(e)}")
        return Response(content="Network error while contacting Fyers API", status_code=502)
    except Exception as e:
        logger.error(f"Fyers callback unexpected error: {str(e)}")
        return Response(content="Internal server error in Fyers callback", status_code=500)