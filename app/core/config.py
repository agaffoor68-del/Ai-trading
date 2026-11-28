"""
Application configuration using pydantic-settings (pydantic v1 compatible).

Loads environment variables from .env file with type validation and
graceful handling of missing optional keys.

Non-negotiable rules:
- Fyers API v3 is the ONLY data source
- Kotak Neo is the ONLY execution broker
- xAI Grok is the ONLY AI for financial news
- PostgreSQL only (no SQLite)
- All timestamps in IST (Asia/Kolkata)
"""

import os
from pathlib import Path
from typing import List, Optional

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


class Settings:
    """Settings class compatible with pydantic v1."""
    
    def __init__(self):
        # 1. GENERAL SETTINGS
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
        self.DEBUG = os.getenv("DEBUG", "true").lower() in ("1", "true", "yes")
        
        # 2. SECURITY & AUTH
        self.SECRET_KEY = os.getenv("SECRET_KEY", "generate_a_random_secure_string_here")
        self.JWT_SECRET = os.getenv("JWT_SECRET", "generate_another_random_secure_string_here")
        self.JWT_TTL_MINUTES = int(os.getenv("JWT_TTL_MINUTES", "720"))
        self.ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "agaffoor68@gmail.com")
        self.ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Abdul@222")
        
        # 3. DATABASE & CACHE
        # Use SQLite for local development, PostgreSQL for production
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./alphatrade_dev.db")
        self.REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        # 4. FYERS API v3 (Market Data - ONLY data source)
        self.FYERS_CLIENT_ID = os.getenv("FYERS_CLIENT_ID")
        self.FYERS_CLIENT_SECRET = os.getenv("FYERS_CLIENT_SECRET")
        self.FYERS_REDIRECT_URI = os.getenv("FYERS_REDIRECT_URI")
        self.FYERS_ACCESS_TOKEN = os.getenv("FYERS_ACCESS_TOKEN")
        self.FYERS_REFRESH_TOKEN = os.getenv("FYERS_REFRESH_TOKEN")
        self.FYERS_API_BASE = os.getenv("FYERS_API_BASE", "https://api-t1.fyers.in/api")
        self.FYERS_SYMBOL_MASTER_BASE = os.getenv("FYERS_SYMBOL_MASTER_BASE", "https://public.fyers.in/sym_details/")
        
        # 5. KOTAK NEO (Execution - ONLY broker for order placement)
        self.KOTAK_CONSUMER_KEY = os.getenv("KOTAK_CONSUMER_KEY")
        self.KOTAK_CONSUMER_SECRET = os.getenv("KOTAK_CONSUMER_SECRET")
        self.KOTAK_TOTP_SECRET = os.getenv("KOTAK_TOTP_SECRET")
        self.KOTAK_MOBILE_NUMBER = os.getenv("KOTAK_MOBILE_NUMBER")
        self.KOTAK_MPIN = os.getenv("KOTAK_MPIN")
        self.KOTAK_UCC = os.getenv("KOTAK_UCC")
        self.KOTAK_ENVIRONMENT = os.getenv("KOTAK_ENVIRONMENT")
        
        # 6. xAI GROK (AI Brain - financial news analysis ONLY)
        self.XAI_API_KEY = os.getenv("XAI_API_KEY")
        self.XAI_MODEL = os.getenv("XAI_MODEL")
        
        # 7. URLS & CORS (CRITICAL FOR DEPLOYMENT)
        self.BACKEND_URL = os.getenv("BACKEND_URL")
        self.FRONTEND_URL = os.getenv("FRONTEND_URL")
        self.ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS")
        
        # 8. FEATURE GATES
        self.ENABLE_LIVE_TRADING = os.getenv("ENABLE_LIVE_TRADING", "false").lower() in ("1", "true", "yes")
        self.ENABLE_PAPER_TRADING = os.getenv("ENABLE_PAPER_TRADING", "true").lower() in ("1", "true", "yes")
        self.ENABLE_ALGO_EXECUTION = os.getenv("ENABLE_ALGO_EXECUTION", "false").lower() in ("1", "true", "yes")
        self.ALLOW_PUBLIC_SIGNUP = os.getenv("ALLOW_PUBLIC_SIGNUP", "false").lower() in ("1", "true", "yes")
        
        # 8b. AI BRAIN
        self.BRAIN_ENABLED = os.getenv("BRAIN_ENABLED", "true").lower() in ("1", "true", "yes")
        self.BRAIN_NEWS_INGEST_ENABLED = os.getenv("BRAIN_NEWS_INGEST_ENABLED", "true").lower() in ("1", "true", "yes")
        self.BRAIN_MONITOR_ENABLED = os.getenv("BRAIN_MONITOR_ENABLED", "true").lower() in ("1", "true", "yes")
        self.BRAIN_RECONCILE_ENABLED = os.getenv("BRAIN_RECONCILE_ENABLED", "true").lower() in ("1", "true", "yes")
        self.BRAIN_STRATEGY_LEARNING_ENABLED = os.getenv("BRAIN_STRATEGY_LEARNING_ENABLED", "false").lower() in ("1", "true", "yes")
        self.BRAIN_MAX_QUOTE_AGE_SECONDS = int(os.getenv("BRAIN_MAX_QUOTE_AGE_SECONDS", "90"))
        self.LIVE_BROKER_ADAPTER_ENABLED = os.getenv("LIVE_BROKER_ADAPTER_ENABLED", "false").lower() in ("1", "true", "yes")
        
        # 9. NOTIFICATIONS (OPTIONAL)
        self.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        self.TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
        
        # 10. ENCRYPTION
        self.TOKEN_ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY")
        
        # APPLICATION SETTINGS
        self.APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
        self.APP_PORT = int(os.getenv("APP_PORT", "8000"))
        self.TZ = os.getenv("TZ", "Asia/Kolkata")

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into a list for CORSMiddleware."""
        if not self.ALLOWED_ORIGINS:
            return []
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


# Singleton settings instance
settings = Settings()


def get_settings() -> Settings:
    """Return the settings singleton."""
    return settings

    # -------------------------------------------------------------------------
    # 1. GENERAL SETTINGS
    # -------------------------------------------------------------------------
    ENVIRONMENT: str = Field(
        default="development",
        description="Application environment: development, staging, production",
    )
    DEBUG: bool = Field(
        default=True,
        description="Enable debug mode",
    )

    # -------------------------------------------------------------------------
    # 2. SECURITY & AUTH
    # -------------------------------------------------------------------------
    SECRET_KEY: str = Field(
        default="generate_a_random_secure_string_here",
        description="Secret key for session/cookie signing",
    )
    JWT_SECRET: str = Field(
        default="generate_another_random_secure_string_here",
        description="JWT signing secret",
    )
    JWT_TTL_MINUTES: int = Field(
        default=720,
        description="JWT token TTL in minutes",
    )
    ADMIN_EMAIL: str = Field(
        default="agaffoor68@gmail.com",
        description="Default admin email",
    )
    ADMIN_PASSWORD: str = Field(
        default="Abdul@222",
        description="Default admin password",
    )

    # -------------------------------------------------------------------------
    # 3. DATABASE & CACHE
    # -------------------------------------------------------------------------
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://user:password@localhost:5432/alphatrade",
        description="PostgreSQL connection string",
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # -------------------------------------------------------------------------
    # 4. FYERS API v3 (Market Data - ONLY data source)
    # -------------------------------------------------------------------------
    # FYERS_CLIENT_ID is persisted in the fyers_tokens table after OAuth and
    # restored into settings at startup (see restore_fyers_credentials). It is
    # declared explicitly here so WebSocket startup never sees an undefined key.
    FYERS_CLIENT_ID: Optional[str] = Field(
        default=None,
        description="Fyers API client ID (app ID, e.g. ABCDEFG-100)",
    )
    FYERS_CLIENT_SECRET: Optional[str] = Field(
        default=None,
        description="Fyers API secret key",
    )
    FYERS_REDIRECT_URI: Optional[str] = Field(
        default=None,
        description="Fyers OAuth2 redirect URI",
    )
    FYERS_ACCESS_TOKEN: Optional[str] = Field(
        default=None,
        description="Fyers API access token (auto-updated after OAuth)",
    )
    FYERS_REFRESH_TOKEN: Optional[str] = Field(
        default=None,
        description="Fyers API refresh token (if available)",
    )
    FYERS_API_BASE: str = Field(
        default="https://api-t1.fyers.in/api",
        description="Fyers API base URL (v3)",
    )
    FYERS_SYMBOL_MASTER_BASE: str = Field(
        default="https://public.fyers.in/sym_details/",
        description="Base URL for Fyers Symbol Master CSV files",
    )

    # -------------------------------------------------------------------------
    # 5. KOTAK NEO (Execution - ONLY broker for order placement)
    # -------------------------------------------------------------------------
    KOTAK_CONSUMER_KEY: Optional[str] = Field(
        default=None,
        description="Kotak Neo consumer key",
    )
    KOTAK_CONSUMER_SECRET: Optional[str] = Field(
        default=None,
        description="Kotak Neo consumer secret",
    )
    KOTAK_TOTP_SECRET: Optional[str] = Field(
        default=None,
        description="Kotak Neo TOTP secret",
    )
    KOTAK_MOBILE_NUMBER: Optional[str] = Field(
        default=None,
        description="Kotak Neo mobile number",
    )
    KOTAK_MPIN: Optional[str] = Field(
        default=None,
        description="Kotak Neo MPIN",
    )
    KOTAK_UCC: Optional[str] = Field(
        default=None,
        description="Kotak Neo UCC",
    )
    KOTAK_ENVIRONMENT: Optional[str] = Field(
        default=None,
        description="Kotak Neo environment: prod or sandbox",
    )

    # -------------------------------------------------------------------------
    # 6. xAI GROK (AI Brain - financial news analysis ONLY)
    # -------------------------------------------------------------------------
    XAI_API_KEY: Optional[str] = Field(
        default=None,
        description="xAI Grok API key (starts with xai-)",
    )
    XAI_MODEL: Optional[str] = Field(
        default=None,
        description="xAI Grok model name",
    )

    # -------------------------------------------------------------------------
    # 7. URLS & CORS (CRITICAL FOR DEPLOYMENT)
    # -------------------------------------------------------------------------
    BACKEND_URL: Optional[str] = Field(
        default=None,
        description="Backend base URL",
    )
    FRONTEND_URL: Optional[str] = Field(
        default=None,
        description="Frontend base URL",
    )
    ALLOWED_ORIGINS: Optional[str] = Field(
        default=None,
        description="CORS allowed origins (comma-separated)",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into a list for CORSMiddleware."""
        if not self.ALLOWED_ORIGINS:
            return []
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    # -------------------------------------------------------------------------
    # 8. FEATURE GATES
    # -------------------------------------------------------------------------
    ENABLE_LIVE_TRADING: bool = Field(
        default=False,
        description="Enable live trading (DANGEROUS - only in production)",
    )
    ENABLE_PAPER_TRADING: bool = Field(
        default=True,
        description="Enable paper trading mode",
    )
    ENABLE_ALGO_EXECUTION: bool = Field(
        default=False,
        description="Enable algorithmic execution",
    )
    ALLOW_PUBLIC_SIGNUP: bool = Field(
        default=False,
        description="Allow public user registration (disabled - only admin creates users)",
    )

    # -------------------------------------------------------------------------
    # 8b. AI BRAIN (Grok autonomous decision engine)
    # -------------------------------------------------------------------------
    # The Brain is read-only with respect to risk configuration: these flags
    # cannot widen limits, they only enable/disable background automation.
    BRAIN_ENABLED: bool = Field(
        default=True,
        description="Master switch for the AI Brain API and decision pipeline",
    )
    BRAIN_NEWS_INGEST_ENABLED: bool = Field(
        default=True,
        description="Background job: refresh India + global news feeds",
    )
    BRAIN_MONITOR_ENABLED: bool = Field(
        default=True,
        description="Background job: monitor open positions and risk usage",
    )
    BRAIN_RECONCILE_ENABLED: bool = Field(
        default=True,
        description="Background job: reconcile local orders with broker positions",
    )
    BRAIN_STRATEGY_LEARNING_ENABLED: bool = Field(
        default=False,
        description="Background job: validate candidate strategy versions (off by default)",
    )
    BRAIN_MAX_QUOTE_AGE_SECONDS: int = Field(
        default=90,
        description="Quotes older than this make the decision engine return NO_TRADE",
    )
    # Live order submission stays impossible until a verified adapter exists.
    # Setting this true without an adapter still results in a rejection.
    LIVE_BROKER_ADAPTER_ENABLED: bool = Field(
        default=False,
        description="Enable live broker submission (requires a verified adapter)",
    )

    # -------------------------------------------------------------------------
    # 9. NOTIFICATIONS (OPTIONAL)
    # -------------------------------------------------------------------------
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(
        default=None,
        description="Telegram bot token",
    )
    TELEGRAM_CHAT_ID: Optional[str] = Field(
        default=None,
        description="Telegram chat ID",
    )

    # -------------------------------------------------------------------------
    # 10. ENCRYPTION
    # -------------------------------------------------------------------------
    TOKEN_ENCRYPTION_KEY: Optional[str] = Field(
        default=None,
        description="Fernet encryption key for secrets (32 url-safe base64 bytes)",
    )

    # -------------------------------------------------------------------------
    # APPLICATION SETTINGS
    # -------------------------------------------------------------------------
    APP_HOST: str = Field(default="0.0.0.0", description="Application host")
    APP_PORT: int = Field(default=8000, description="Application port")

    # Timezone (IST only)
    TZ: str = Field(default="Asia/Kolkata", description="Application timezone")


# Singleton settings instance
settings = Settings()


def get_settings() -> Settings:
    """Return the settings singleton."""
    return settings