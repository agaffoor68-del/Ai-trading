"""
Phase 2: Authentication Module

JWT-based authentication with passlib password hashing.
Includes admin seeder that creates the default admin user on startup.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.core.models import User, Subscription, UserRole, SubscriptionPlan

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token extraction from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# JWT settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-jwt-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT access token. Returns payload or None if invalid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def authenticate_user(db, email: str, password: str) -> User | None:
    """Authenticate a user by email and password. Returns User or None."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def get_current_user(token: str = Depends(oauth2_scheme), db=Depends(get_db)) -> User:
    """Dependency to get the current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency that requires the current user to have ADMIN role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def require_active_subscription(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that blocks non-subscribed users from accessing AI or Execution endpoints.
    Admins are exempt from this check.
    """
    # Admins bypass subscription check
    if current_user.role == UserRole.ADMIN:
        return current_user

    subscription = current_user.subscription
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required to access this feature",
        )

    if not subscription.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Subscription is not active",
        )

    now = datetime.now(IST)
    if subscription.end_date and subscription.end_date < now:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Subscription has expired",
        )

    return current_user


def seed_admin_user() -> None:
    """
    Initial Admin Seeder.
    On startup, check if the admin exists. If not, create one with:
    - Email: agaffoor68@gmail.com
    - Password: Abdul@222
    - Role: ADMIN
    """
    db = SessionLocal()
    try:
        admin_email = "agaffoor68@gmail.com"
        admin_password = "Abdul@222"

        existing_admin = (
            db.query(User)
            .filter(User.email == admin_email)
            .first()
        )

        if existing_admin:
            logger.info(f"Admin user already exists: {admin_email}")
            return

        admin_user = User(
            email=admin_email,
            hashed_password=hash_password(admin_password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        # Grant admin a lifetime subscription (Pro plan, far future end date)
        far_future = datetime.now(IST) + timedelta(days=365 * 100)
        admin_subscription = Subscription(
            user_id=admin_user.id,
            plan_type=SubscriptionPlan.PRO,
            start_date=datetime.now(IST),
            end_date=far_future,
            is_active=True,
        )
        db.add(admin_subscription)
        db.commit()

        logger.info(f"Admin user seeded: {admin_email} with Pro subscription")
    except Exception as e:
        logger.error(f"Admin seeder error: {str(e)}")
        db.rollback()
    finally:
        db.close()
