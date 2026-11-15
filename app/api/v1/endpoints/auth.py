"""
Phase 2: Authentication Endpoints

Login, logout, user info, and registration endpoints.
"""

import logging
import os
import time
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.core.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.core.database import get_db
from app.core.models import User
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])
IST = ZoneInfo("Asia/Kolkata")

# Rate limiting storage (in production, use Redis)
_login_attempts = {}


class UserRegisterRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: dict


class MeResponse(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    subscription: dict | None = None


def _check_rate_limit(ip: str, max_attempts: int = 5, window_seconds: int = 300) -> bool:
    """Check if IP has exceeded login attempts. Returns True if allowed."""
    now = time.time()
    if ip not in _login_attempts:
        _login_attempts[ip] = []
    
    # Remove old attempts outside window
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < window_seconds]
    
    if len(_login_attempts[ip]) >= 5:
        return False
    
    _login_attempts[ip].append(now)
    return True


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Authenticate user and return JWT access token in httpOnly cookie.
    Accepts username (email) and password in form body.
    """
    client_ip = request.client.host if request.client else "unknown"
    
    # Rate limiting
    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )
    
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        # Generic error - don't reveal if email exists
        logger.warning(f"Failed login attempt for {form_data.username} from {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
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

    # Set httpOnly cookie
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    cookie_options = {
        "httponly": True,
        "secure": True,  # Always true for HTTPS (Vercel/Render)
        "samesite": "lax",
        "max_age": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "path": "/",
    }
    response.set_cookie(key="access_token", value=access_token, **cookie_options)

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


@router.post("/logout")
async def logout(response: Response):
    """Logout user by clearing the access token cookie."""
    response.delete_cookie(key="access_token", path="/", secure=True, samesite="lax")
    return {"message": "Logged out successfully"}


@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user info.
    Returns user info with role, subscription, and subscription details.
    """
    subscription_info = None
    if current_user.subscription:
        sub = current_user.subscription
        subscription_info = {
            "plan_type": sub.plan_type.value,
            "start_date": sub.start_date.isoformat() if sub.start_date else None,
            "end_date": sub.end_date.isoformat() if sub.end_date else None,
            "is_active": sub.is_active,
        }
    
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role.value,
        "is_active": current_user.is_active,
        "subscription": subscription_info,
    }


@router.post("/register")
async def register(
    user_data: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Register a new user with email and password.
    Only admins can create users. Public signup is disabled.
    """
    # Check if public registration is disabled
    if not settings.ALLOW_PUBLIC_SIGNUP:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled. Contact admin to create account.",
        )
    
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


# Admin password reset endpoint (protected by RESET_ADMIN_PASSWORD flag)
@router.post("/admin/reset-password")
async def reset_admin_password(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    One-time admin password reset.
    Requires RESET_ADMIN_PASSWORD=1 environment variable.
    Updates the existing admin's password hash from ADMIN_PASSWORD env var.
    """
    if not os.getenv("RESET_ADMIN_PASSWORD") == "1":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin password reset not enabled",
        )
    
    admin_email = settings.ADMIN_EMAIL
    new_password = settings.ADMIN_PASSWORD
    
    if not admin_email or not new_password:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_EMAIL or ADMIN_PASSWORD not configured",
        )
    
    admin_user = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin user not found",
        )
    
    # Update password
    admin_user.hashed_password = hash_password(settings.ADMIN_PASSWORD)
    db.commit()
    
    logger.info(f"Admin password reset for {admin_email}")
    
    # Tell user to remove the flag
    return {
        "message": "Admin password reset successfully. Please remove RESET_ADMIN_PASSWORD=1 from environment.",
        "email": admin_email,
    }


# Admin-only: create user (for admin panel)
@router.post("/admin/users")
async def admin_create_user(
    user_data: UserRegisterRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin-only endpoint to create users."""
    # Check if user already exists
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    new_user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        role="USER",
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"Admin created user: {user_data.email}")

    return {
        "message": "User created successfully",
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "role": new_user.role.value,
            "is_active": new_user.is_active,
        },
    }