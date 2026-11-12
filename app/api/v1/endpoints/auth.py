"""
Phase 2: Authentication Endpoints

Login and user registration endpoints.
"""

import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.auth import (
    authenticate_user,
    create_access_token,
    hash_password,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.core.database import get_db
from app.core.models import User
from app.services.fyers_token import get_fyers_token_status
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


class BrokerStatusResponse(BaseModel):
    fyers: dict
    kotak: dict


@router.get("/broker-status", response_model=BrokerStatusResponse)
async def get_broker_status():
    """
    Get connection status for both Fyers and Kotak brokers.
    """
    # Check Fyers token status
    fyers_status = get_fyers_token_status()
    fyers_connected = fyers_status.get("valid", False)
    
    # Check Kotak session status
    # For now, check if Kotak credentials are configured
    kotak_connected = bool(settings.KOTAK_CONSUMER_KEY and settings.KOTAK_CONSUMER_SECRET)
    
    return {
        "fyers": {"connected": fyers_connected},
        "kotak": {"connected": kotak_connected},
    }


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: dict


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Authenticate user and return JWT access token.
    Accepts username (email) and password in form body.
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role.value, "user_id": user.id},
        expires_delta=access_token_expires,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role.value,
            "is_active": user.is_active,
        },
    }


@router.post("/register")
async def register(
    user_data: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Register a new user with email and password.
    Default role is USER.
    """
    # Check if user already exists
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    new_user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        role="USER",
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"New user registered: {user_data.email}")

    return {
        "message": "User registered successfully",
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "role": new_user.role.value,
            "is_active": new_user.is_active,
        },
    }


@router.get("/me")
async def get_current_user_info(current_user: User = Depends(lambda: None)):
    """
    Get current authenticated user info.
    Note: This endpoint requires the auth dependency to be properly wired.
    """
    # This is a placeholder; actual dependency injection happens via get_current_user
    return {"message": "Use /api/v1/auth/login to get token, then pass it in Authorization header"}
