"""
Phase 2: Authentication Dependencies

Re-exports auth dependencies for clean imports across the application.
"""

from app.core.auth import (
    get_current_user,
    require_admin,
    require_active_subscription,
    authenticate_user,
    create_access_token,
    hash_password,
    verify_password,
    get_db,
    oauth2_scheme,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

__all__ = [
    "get_current_user",
    "require_admin",
    "require_active_subscription",
    "authenticate_user",
    "create_access_token",
    "hash_password",
    "verify_password",
    "get_db",
    "oauth2_scheme",
    "SECRET_KEY",
    "ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
]
